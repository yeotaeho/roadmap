# C-1 코치 채팅 코어 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** AI 코치 채팅 수직슬라이스 — 내부 데이터 tool 6종을 가진 Sonnet 기반 LangGraph tool-calling 에이전트를 SSE로 서빙하고, 최소 CoachView로 /coach 탭을 라이브 전환한다.

**Architecture:** consult 엔진 패턴(StateGraph·체크포인터·SSE·롤링 요약)을 `ai_coach` 도메인에 이식하되, plan/extract 노드 대신 tool-calling agent 노드(`prepare → agent → persist`)를 쓴다. tool은 기존 Gold/자기모델 데이터를 감싸는 read-only 래퍼이며, 자기모델 접근은 `read_for_coach()` 단일 관문으로 §9 읽기 계약을 강제한다.

**Tech Stack:** FastAPI · LangGraph(StateGraph, AsyncPostgresSaver) · langchain-anthropic(ChatAnthropic, claude-sonnet-5) · SQLAlchemy 2.0 text() · pgvector(halfvec 3072) · Next.js/React 19

**스펙:** `docs/superpowers/specs/2026-07-05-ai-coach-roadmap-agent-design.md` (C-1 범위만. 웹 tool=C-2, 딥 에이전트=R-1은 별도 계획)

## Global Constraints

- 새 소스 파일 첫 줄: 한 줄 한국어 주석으로 역할 명시 (config 제외). 한국어 문장 종결은 `.` `?` `!` 만.
- 테스트 컨벤션: **pytest 아님.** `backend/scripts/<name>_test.py` 단독 실행 스크립트 — `sys.path.insert` + `check(name, cond)` PASS/FAIL 패턴 (`backend/scripts/consult_context_test.py` 참조). 실행: `cd backend && python scripts/xxx_test.py`, 종료코드 0=전부 PASS.
- tool 전부 read-only. Bronze 테이블 직접 조회 금지. `consult_messages` 원문·`is_sensitive=true` 근거는 어떤 경로로도 노출 금지.
- 코치 LLM: `claude-sonnet-5` (settings 기본값). 롤링 요약은 기존 `resolve_user_llm`(Gemini 2.5 Flash) 재사용 — 비용 절약.
- SSE 이벤트 타입: `delta` / `tool_call` / `tool_result` / `error` / `done` (스펙 §5).
- 임베딩 모델 `text-embedding-3-large`(3072) 고정 — 쿼리 임베딩도 동일 모델.
- 마이그레이션: 수동 작성 스타일, down_revision 체인은 현재 head `51f3d7e2ef01`부터. 수동 DDL 금지.
- 커밋: 태스크당 1커밋, semantic prefix. 각 커밋 후 CLAUDE.md 이중 리뷰(code-reviewer → /codex:review)는 실행 세션 워크플로에 따른다.
- 교차 도메인 접근: ai_coach → user_intelligence는 서비스(`ConsultMemoryService`) 경유만. 체크포인터는 `domain.user_intelligence.spokes.infra.consult_graph.get_checkpointer` 공유 import(프로세스 싱글턴이므로 이동 금지).

---

### Task 1: 의존성 + 설정 + 코치 LLM 리졸버

**Files:**
- Modify: `backend/requirements.txt`
- Modify: `backend/core/config/settings.py` (LLM 필드 블록에 2필드 추가)
- Modify: `backend/core/llm/provider.py` (`resolve_coach_llm` 추가)
- Test: `backend/scripts/coach_llm_resolve_test.py`

**Interfaces:**
- Produces: `resolve_coach_llm(settings) -> tuple[str, str]` — `(api_key, model)` 반환, 키 없으면 `RuntimeError` (fail-loud, `resolve_user_llm`과 동일 철학). settings 필드 `anthropic_api_key: Optional[str]`, `coach_llm_model: str = "claude-sonnet-5"`.

- [ ] **Step 1: 실패하는 테스트 작성**

`backend/scripts/coach_llm_resolve_test.py`:

```python
# 코치 LLM 리졸버(fail-loud) 순수 단위 테스트(무DB·무네트워크)

from __future__ import annotations

import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SCHEDULER_ENABLED", "false")

from core.llm.provider import resolve_coach_llm

PASS = 0
FAIL = 0


def check(n: str, c: bool, e: str = "") -> None:
    global PASS, FAIL
    if c:
        PASS += 1
        print(f"[PASS] {n}")
    else:
        FAIL += 1
        print(f"[FAIL] {n} {e}")


def run() -> int:
    s = SimpleNamespace(anthropic_api_key="sk-ant-test", coach_llm_model="claude-sonnet-5")
    key, model = resolve_coach_llm(s)
    check("키·모델 반환", key == "sk-ant-test" and model == "claude-sonnet-5")

    s2 = SimpleNamespace(anthropic_api_key=None, coach_llm_model="claude-sonnet-5")
    try:
        resolve_coach_llm(s2)
        check("키 없으면 fail-loud", False, "예외 미발생")
    except RuntimeError as e:
        check("키 없으면 fail-loud", "ANTHROPIC_API_KEY" in str(e))

    s3 = SimpleNamespace(anthropic_api_key="k", coach_llm_model="")
    _, model3 = resolve_coach_llm(s3)
    check("모델 미지정 시 기본값", model3 == "claude-sonnet-5")

    print(f"\n합계: PASS {PASS} / FAIL {FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(run())
```

- [ ] **Step 2: 실패 확인**

Run: `cd backend && python scripts/coach_llm_resolve_test.py`
Expected: `ImportError: cannot import name 'resolve_coach_llm'`

- [ ] **Step 3: 구현**

`backend/requirements.txt` 끝에 추가:

```
langchain-anthropic>=0.3.0
```

`backend/core/config/settings.py` — 기존 LLM 필드 블록(`gemini_api_key` 근처)에 추가:

```python
    # AI 코치 LLM (Claude Sonnet — tool-calling)
    anthropic_api_key: Optional[str] = Field(default=None, validation_alias="ANTHROPIC_API_KEY")
    coach_llm_model: str = Field(default="claude-sonnet-5", validation_alias="COACH_LLM_MODEL")
```

`backend/core/llm/provider.py` 끝에 추가:

```python
def resolve_coach_llm(settings) -> tuple[str, str]:
    """코치(Anthropic) LLM 해석 — (api_key, model). 키 없으면 fail-loud(폴백 없음)."""
    api_key = getattr(settings, "anthropic_api_key", None)
    if not api_key:
        raise RuntimeError("코치 LLM 설정 오류 — ANTHROPIC_API_KEY 가 필요합니다.")
    model = getattr(settings, "coach_llm_model", None) or "claude-sonnet-5"
    return api_key, model
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd backend && python scripts/coach_llm_resolve_test.py`
Expected: PASS 3 / FAIL 0, exit 0

- [ ] **Step 5: 의존성 설치 확인**

Run: `cd backend && pip install -r requirements.txt`
Expected: `langchain-anthropic` 설치 성공 (기존 langgraph>=1.1·langchain-core와 충돌 없음). 이어서 `python -c "from langchain_anthropic import ChatAnthropic; print('ok')"` → `ok`

- [ ] **Step 6: 커밋**

```bash
git add backend/requirements.txt backend/core/config/settings.py backend/core/llm/provider.py backend/scripts/coach_llm_resolve_test.py
git commit -m "feat(coach): Anthropic 코치 LLM 설정·리졸버(fail-loud) + langchain-anthropic 의존성"
```

---

### Task 2: coach 세션 테이블 — 마이그레이션 + ORM + 레포지토리

**Files:**
- Create: `backend/domain/ai_coach/models/bases/coach_session.py`
- Create: `backend/domain/ai_coach/models/bases/coach_message.py`
- Modify: `backend/domain/ai_coach/models/bases/__init__.py` (모델 export — alembic 메타데이터 등록. 다른 도메인 `models/bases/__init__.py`와 같은 방식으로 두 클래스를 import)
- Create: `backend/alembic/versions/a3c9e5f7b2d1_add_coach_session_tables.py`
- Create: `backend/domain/ai_coach/hub/repositories/coach_session_repository.py`
- Test: `backend/scripts/coach_session_models_import_test.py`

**Interfaces:**
- Consumes: 없음 (독립).
- Produces: `CoachSessionRepository(session: AsyncSession)` — 메서드: `create_session(user_id) -> str`, `get_latest_active_session(user_id) -> str | None`, `get_session(session_id) -> dict | None` (키: user_id·status·context_summary·summarized_until), `add_message(session_id, role, content) -> None`, `fetch_messages(session_id) -> list[dict]` (키: role·content), `count_messages(session_id) -> int`, `update_summary(session_id, summary, summarized_until) -> None`, `end_session(session_id) -> None`. 전부 consult_session_repository와 동일 시맨틱 — 테이블만 coach_*.
- 주의: consult와 달리 `extracted_until`/`extracted_at` 컬럼 없음 (코치는 자기모델 추출 안 함 — YAGNI).

- [ ] **Step 1: 실패하는 테스트 작성**

`backend/scripts/coach_session_models_import_test.py`:

```python
# 코치 세션·메시지 ORM 임포트·스키마 단위 테스트(무DB)

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SCHEDULER_ENABLED", "false")

from domain.ai_coach.models.bases.coach_message import CoachMessage
from domain.ai_coach.models.bases.coach_session import CoachSession

PASS = 0
FAIL = 0


def check(n: str, c: bool, e: str = "") -> None:
    global PASS, FAIL
    if c:
        PASS += 1
        print(f"[PASS] {n}")
    else:
        FAIL += 1
        print(f"[FAIL] {n} {e}")


def run() -> int:
    check("세션 테이블명", CoachSession.__tablename__ == "coach_sessions")
    check("메시지 테이블명", CoachMessage.__tablename__ == "coach_messages")
    scols = {c.name for c in CoachSession.__table__.columns}
    check(
        "세션 컬럼",
        {"id", "user_id", "status", "started_at", "ended_at", "title", "context_summary", "summarized_until", "created_at"} <= scols,
    )
    check("추출 컬럼 없음(YAGNI)", "extracted_until" not in scols and "extracted_at" not in scols)
    mcols = {c.name for c in CoachMessage.__table__.columns}
    check("메시지 컬럼", {"id", "session_id", "role", "content", "created_at"} <= mcols)
    fk = list(CoachMessage.__table__.columns["session_id"].foreign_keys)[0]
    check("메시지 FK → coach_sessions", "coach_sessions" in str(fk.target_fullname))

    print(f"\n합계: PASS {PASS} / FAIL {FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(run())
```

- [ ] **Step 2: 실패 확인**

Run: `cd backend && python scripts/coach_session_models_import_test.py`
Expected: `ModuleNotFoundError: No module named 'domain.ai_coach.models.bases.coach_session'`

- [ ] **Step 3: ORM 모델 작성**

`backend/domain/ai_coach/models/bases/coach_session.py`:

```python
# 코치 대화 세션 ORM — 상태·롤링 요약 커서 보유(자기모델 추출 없음)

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class CoachSession(Base):
    __tablename__ = "coach_sessions"
    __table_args__ = {"comment": "AI 코치 대화 세션 — 재개 가능·롤링 요약"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False, server_default="active")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    title: Mapped[str | None] = mapped_column(String(120), nullable=True)
    context_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    summarized_until: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=True)
```

`backend/domain/ai_coach/models/bases/coach_message.py`:

```python
# 코치 대화 메시지 ORM — append-only 턴 로그

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class CoachMessage(Base):
    __tablename__ = "coach_messages"
    __table_args__ = {"comment": "AI 코치 턴별 메시지(append-only)"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("coach_sessions.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(10), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=True)
```

`backend/domain/ai_coach/models/bases/__init__.py` — 기존 내용(빈 파일)에 추가:

```python
# ai_coach ORM 모델 집합 — alembic 메타데이터 등록용 re-export

from domain.ai_coach.models.bases.coach_message import CoachMessage
from domain.ai_coach.models.bases.coach_session import CoachSession

__all__ = ["CoachSession", "CoachMessage"]
```

주의: `backend/alembic/env.py`가 도메인 모델 패키지를 import해 메타데이터를 모으는 방식이라면(파일 확인) ai_coach.models.bases import 라인이 거기 필요할 수 있다 — consult 모델이 등록되는 방식과 동일하게 맞춘다.

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd backend && python scripts/coach_session_models_import_test.py`
Expected: PASS 6 / FAIL 0

- [ ] **Step 5: 마이그레이션 작성**

`backend/alembic/versions/a3c9e5f7b2d1_add_coach_session_tables.py`:

```python
# 코치 세션·메시지 테이블 신설 (consult 구조 미러 — 추출 컬럼 제외)

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "a3c9e5f7b2d1"
down_revision = "51f3d7e2ef01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "coach_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(10), nullable=False, server_default="active"),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("title", sa.String(120), nullable=True),
        sa.Column("context_summary", sa.Text(), nullable=True),
        sa.Column("summarized_until", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        comment="AI 코치 대화 세션 — 재개 가능·롤링 요약",
    )
    op.create_index("ix_coach_sessions_user_id", "coach_sessions", ["user_id"])
    op.create_table(
        "coach_messages",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("coach_sessions.id"), nullable=False),
        sa.Column("role", sa.String(10), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        comment="AI 코치 턴별 메시지(append-only)",
    )
    op.create_index("ix_coach_messages_session_id", "coach_messages", ["session_id"])


def downgrade() -> None:
    op.drop_index("ix_coach_messages_session_id", table_name="coach_messages")
    op.drop_table("coach_messages")
    op.drop_index("ix_coach_sessions_user_id", table_name="coach_sessions")
    op.drop_table("coach_sessions")
```

작성 전 `cd backend && alembic heads` 로 현재 head가 `51f3d7e2ef01`인지 확인 — 다르면 down_revision을 실제 head로 교체.

- [ ] **Step 6: 마이그레이션 적용**

Run: `cd backend && alembic upgrade head`
Expected: `Running upgrade 51f3d7e2ef01 -> a3c9e5f7b2d1` 성공. 확인: `alembic current` → `a3c9e5f7b2d1 (head)`

- [ ] **Step 7: 레포지토리 작성**

`backend/domain/ai_coach/hub/repositories/coach_session_repository.py` — `consult_session_repository.py`와 동일 시맨틱, 테이블만 교체. text() SQL 스타일 유지:

```python
# 코치 세션·메시지 DB 접근 — 생성·재개·메시지 append·롤링 요약 커서

from __future__ import annotations

import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

_CREATE = text("INSERT INTO coach_sessions (id, user_id) VALUES (:id, :uid)")
_LATEST_ACTIVE = text(
    "SELECT id FROM coach_sessions WHERE user_id = :uid AND status = 'active' "
    "ORDER BY created_at DESC LIMIT 1"
)
_GET = text(
    "SELECT user_id, status, context_summary, summarized_until FROM coach_sessions WHERE id = :sid"
)
_ADD_MSG = text(
    "INSERT INTO coach_messages (session_id, role, content) VALUES (:sid, :role, :content)"
)
_FETCH_MSGS = text(
    "SELECT role, content FROM coach_messages WHERE session_id = :sid ORDER BY id ASC"
)
_COUNT_MSGS = text("SELECT COUNT(*) FROM coach_messages WHERE session_id = :sid")
_UPDATE_SUMMARY = text(
    "UPDATE coach_sessions SET context_summary = :summary, summarized_until = :until WHERE id = :sid"
)
_END = text(
    "UPDATE coach_sessions SET status = 'ended', ended_at = now() WHERE id = :sid AND status != 'ended'"
)


class CoachSessionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_session(self, user_id: str) -> str:
        sid = str(uuid.uuid4())
        await self.session.execute(_CREATE, {"id": sid, "uid": user_id})
        await self.session.commit()
        return sid

    async def get_latest_active_session(self, user_id: str) -> str | None:
        row = (await self.session.execute(_LATEST_ACTIVE, {"uid": user_id})).first()
        return str(row[0]) if row else None

    async def get_session(self, session_id: str) -> dict | None:
        row = (await self.session.execute(_GET, {"sid": session_id})).mappings().first()
        if row is None:
            return None
        return {
            "user_id": str(row["user_id"]),
            "status": row["status"],
            "context_summary": row["context_summary"],
            "summarized_until": row["summarized_until"],
        }

    async def add_message(self, session_id: str, role: str, content: str) -> None:
        await self.session.execute(_ADD_MSG, {"sid": session_id, "role": role, "content": content})
        await self.session.commit()

    async def fetch_messages(self, session_id: str) -> list[dict]:
        rows = (await self.session.execute(_FETCH_MSGS, {"sid": session_id})).mappings().all()
        return [{"role": r["role"], "content": r["content"]} for r in rows]

    async def count_messages(self, session_id: str) -> int:
        return (await self.session.execute(_COUNT_MSGS, {"sid": session_id})).scalar() or 0

    async def update_summary(self, session_id: str, summary: str, summarized_until: int) -> None:
        await self.session.execute(
            _UPDATE_SUMMARY, {"sid": session_id, "summary": summary, "until": summarized_until}
        )
        await self.session.commit()

    async def end_session(self, session_id: str) -> None:
        await self.session.execute(_END, {"sid": session_id})
        await self.session.commit()
```

구현 시 `consult_session_repository.py` 원본을 열어 SQL·커밋 방식이 실제로 위와 같은지 대조하고, 다르면 원본 방식을 따른다(파라미터명·mappings 사용 등).

- [ ] **Step 8: 임포트 스모크**

Run: `cd backend && python -c "from domain.ai_coach.hub.repositories.coach_session_repository import CoachSessionRepository; print('ok')"`
Expected: `ok`

- [ ] **Step 9: 커밋**

```bash
git add backend/domain/ai_coach/models backend/alembic/versions/a3c9e5f7b2d1_add_coach_session_tables.py backend/domain/ai_coach/hub/repositories/coach_session_repository.py backend/scripts/coach_session_models_import_test.py
git commit -m "feat(coach): 코치 세션·메시지 테이블 신설 — ORM·마이그레이션·레포지토리"
```

---

### Task 3: read_for_coach — §9 읽기 계약 구현

**Files:**
- Create: `backend/domain/user_intelligence/hub/services/consult_memory_service.py`
- Modify: `backend/domain/user_intelligence/hub/repositories/consult_session_repository.py` (`fetch_recent_summaries` 추가)
- Test: `backend/scripts/consult_memory_read_test.py`

**Interfaces:**
- Consumes: `SelfModelService.get_self_model_structured(user_id) -> dict` (camelCase 키: riasec·bigFive·narrativeSummary·axisConfidence·axisSource), `SelfModelService.fetch_evidence(user_id, include_sensitive=False) -> list[dict]` (키: dimension·polarity·content·confidence·is_sensitive·source).
- Produces:
  - `shape_for_coach(model, evidence, summaries) -> dict` — 순수 함수. 반환 `{"selfModel": dict, "evidence": [{"dimension","content"}...최대 8개, confidence 내림차순], "recentConsultSummaries": [str...최대 3개]}`.
  - `ConsultMemoryService(session).read_for_coach(user_id) -> dict` — 위 shape 반환. **include_sensitive를 절대 True로 호출하지 않는다.**
  - `ConsultSessionRepository.fetch_recent_summaries(user_id, limit=3) -> list[str]`.

- [ ] **Step 1: 실패하는 테스트 작성**

`backend/scripts/consult_memory_read_test.py`:

```python
# 코치 읽기 계약(read_for_coach) 셰이핑 순수 단위 테스트(무DB) — 민감정보 차단 확인

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SCHEDULER_ENABLED", "false")

from domain.user_intelligence.hub.services.consult_memory_service import shape_for_coach

PASS = 0
FAIL = 0


def check(n: str, c: bool, e: str = "") -> None:
    global PASS, FAIL
    if c:
        PASS += 1
        print(f"[PASS] {n}")
    else:
        FAIL += 1
        print(f"[FAIL] {n} {e}")


def run() -> int:
    model = {"riasec": {"top_codes": ["I", "A"]}, "bigFive": None, "narrativeSummary": "탐구형."}
    evidence = [
        {"dimension": "like", "content": f"근거{i}", "confidence": 0.5 + i * 0.05, "is_sensitive": False}
        for i in range(10)
    ]
    out = shape_for_coach(model, evidence, ["요약1", "요약2", "요약3", "요약4"])
    check("selfModel 그대로", out["selfModel"] == model)
    check("근거 최대 8개", len(out["evidence"]) == 8)
    check("confidence 내림차순", out["evidence"][0]["content"] == "근거9")
    check("근거 필드 축소(dimension·content만)", set(out["evidence"][0].keys()) == {"dimension", "content"})
    check("요약 최대 3개", len(out["recentConsultSummaries"]) == 3)

    # 방어선: 민감 행이 섞여 들어와도 셰이핑 단계에서 한 번 더 걸러낸다.
    leaked = [{"dimension": "constraint", "content": "민감", "confidence": 0.9, "is_sensitive": True}]
    out2 = shape_for_coach(model, leaked, [])
    check("민감 근거 2차 차단", out2["evidence"] == [])

    out3 = shape_for_coach(None, [], [])
    check("빈 입력 안전", out3["selfModel"] is None and out3["evidence"] == [])

    print(f"\n합계: PASS {PASS} / FAIL {FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(run())
```

- [ ] **Step 2: 실패 확인**

Run: `cd backend && python scripts/consult_memory_read_test.py`
Expected: `ModuleNotFoundError: ... consult_memory_service`

- [ ] **Step 3: 구현**

`backend/domain/user_intelligence/hub/repositories/consult_session_repository.py`에 메서드 추가 (클래스 내부, 기존 스타일에 맞춰 모듈 상단에 SQL 상수 선언):

```python
_RECENT_SUMMARIES = text(
    "SELECT context_summary FROM consult_sessions "
    "WHERE user_id = :uid AND context_summary IS NOT NULL "
    "ORDER BY created_at DESC LIMIT :n"
)

    async def fetch_recent_summaries(self, user_id: str, limit: int = 3) -> list[str]:
        rows = (await self.session.execute(_RECENT_SUMMARIES, {"uid": user_id, "n": limit})).all()
        return [r[0] for r in rows]
```

`backend/domain/user_intelligence/hub/services/consult_memory_service.py`:

```python
# 코치 읽기 계약(AGENT_ROADMAP §9) 단일 관문 — 정제층만 노출, 대화 원문·민감 근거 차단

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from domain.user_intelligence.hub.repositories.consult_session_repository import ConsultSessionRepository
from domain.user_intelligence.hub.services.self_model_service import SelfModelService

_MAX_EVIDENCE = 8
_MAX_SUMMARIES = 3


def shape_for_coach(model: dict | None, evidence: list[dict], summaries: list[str]) -> dict:
    """자기모델·근거·상담 요약 → 코치 주입용 축약 스냅샷. 민감 근거는 2차 차단(심층 방어)."""
    safe = [e for e in (evidence or []) if not e.get("is_sensitive")]
    safe.sort(key=lambda e: e.get("confidence") or 0, reverse=True)
    return {
        "selfModel": model,
        "evidence": [{"dimension": e.get("dimension"), "content": e.get("content")} for e in safe[:_MAX_EVIDENCE]],
        "recentConsultSummaries": list(summaries or [])[:_MAX_SUMMARIES],
    }


class ConsultMemoryService:
    """코치가 user_intelligence 를 읽는 유일한 경로 — consult_messages 원문은 여기서도 조회하지 않는다."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def read_for_coach(self, user_id: str) -> dict:
        svc = SelfModelService(self.session)
        model = await svc.get_self_model_structured(user_id)
        evidence = await svc.fetch_evidence(user_id, include_sensitive=False)
        summaries = await ConsultSessionRepository(self.session).fetch_recent_summaries(user_id, _MAX_SUMMARIES)
        return shape_for_coach(model, evidence, summaries)
```

구현 시 `SelfModelService.fetch_evidence` 시그니처를 실제 파일에서 대조 — 메서드가 서비스가 아니라 repository에만 있으면 `SelfModelRepository.fetch_evidence(user_id, include_sensitive=False)`로 교체한다.

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd backend && python scripts/consult_memory_read_test.py`
Expected: PASS 7 / FAIL 0

- [ ] **Step 5: 커밋**

```bash
git add backend/domain/user_intelligence/hub/services/consult_memory_service.py backend/domain/user_intelligence/hub/repositories/consult_session_repository.py backend/scripts/consult_memory_read_test.py
git commit -m "feat(consult): read_for_coach 읽기 계약 구현 — 정제층 스냅샷·민감 근거 이중 차단"
```

---

### Task 4: 코치 인사이트 레포지토리 + 내부 tool 6종

**Files:**
- Create: `backend/domain/ai_coach/hub/repositories/coach_insight_repository.py`
- Create: `backend/domain/ai_coach/spokes/agents/tools/__init__.py` (빈 파일 + 헤더 주석)
- Create: `backend/domain/ai_coach/spokes/agents/tools/internal_tools.py`
- Test: `backend/scripts/coach_tools_test.py`

**Interfaces:**
- Consumes: `ConsultMemoryService.read_for_coach(user_id)` (Task 3), settings의 `openai_api_key`·`llm_embed_model`.
- Produces:
  - `CoachInsightRepository(session)` — `pulse_trends(sector_slug|None) -> dict`, `gap_issues(sector_slug|None, issue_id|None) -> dict`, `chance_matches(user_id, opportunity_type|None) -> dict`, `sync_snapshot(user_id) -> dict`, `search_documents(query_vec: list[float], sector_slug|None) -> list[dict]`.
  - `build_internal_tools(user_id: str) -> list` — LangChain StructuredTool 6개: `get_pulse_trends`, `get_gap_issues`, `get_chance_matches`, `get_sync_snapshot`, `get_user_profile`, `search_insights`.
  - `TOOL_LABELS: dict[str, str]` — tool명 → UI 표시 라벨(예: "시장 트렌드 조회").
- 원칙: Gold·자기모델 정제층만. 반환은 요약 JSON(dict) — 행당 필드 최소화.

- [ ] **Step 1: 실패하는 테스트 작성**

`backend/scripts/coach_tools_test.py`:

```python
# 코치 내부 tool 팩토리 단위 테스트(무DB·무네트워크) — 스키마·라벨·read-only 계약

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SCHEDULER_ENABLED", "false")

from domain.ai_coach.spokes.agents.tools.internal_tools import TOOL_LABELS, build_internal_tools

PASS = 0
FAIL = 0


def check(n: str, c: bool, e: str = "") -> None:
    global PASS, FAIL
    if c:
        PASS += 1
        print(f"[PASS] {n}")
    else:
        FAIL += 1
        print(f"[FAIL] {n} {e}")


def run() -> int:
    tools = build_internal_tools("00000000-0000-0000-0000-000000000000")
    names = {t.name for t in tools}
    expected = {
        "get_pulse_trends", "get_gap_issues", "get_chance_matches",
        "get_sync_snapshot", "get_user_profile", "search_insights",
    }
    check("tool 6종", names == expected, str(names))
    check("전부 설명 보유", all((t.description or "").strip() for t in tools))
    check("전부 비동기", all(t.coroutine is not None for t in tools))
    check("라벨 전수", set(TOOL_LABELS.keys()) == expected)
    check("라벨 한국어", all(any("가" <= ch <= "힣" for ch in v) for v in TOOL_LABELS.values()))

    # user_id 는 클로저로 고정 — LLM 이 넘길 수 있는 인자에 user_id 가 없어야 한다(권한 상승 차단).
    for t in tools:
        schema = t.args_schema.model_json_schema() if t.args_schema else {"properties": {}}
        check(f"{t.name} 인자에 user_id 없음", "user_id" not in schema.get("properties", {}))

    print(f"\n합계: PASS {PASS} / FAIL {FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(run())
```

- [ ] **Step 2: 실패 확인**

Run: `cd backend && python scripts/coach_tools_test.py`
Expected: `ModuleNotFoundError: ... internal_tools`

- [ ] **Step 3: 레포지토리 구현**

`backend/domain/ai_coach/hub/repositories/coach_insight_repository.py`:

```python
# 코치 tool 전용 Gold 조회 — 토큰 절약형 축약 반환(read-only)

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

_PULSE_LATEST = text(
    "SELECT DISTINCT ON (sector_slug) sector_slug, score, momentum_pct, status_badge, recorded_date "
    "FROM pulse_metrics_log "
    "WHERE (CAST(:sector AS varchar) IS NULL OR sector_slug = :sector) "
    "ORDER BY sector_slug, recorded_date DESC"
)
_GAP_LIST = text(
    "SELECT id, sector_slug, problem_summary, chance_summary, published_date "
    "FROM gap_issues "
    "WHERE is_active = true AND (CAST(:sector AS varchar) IS NULL OR sector_slug = :sector) "
    "ORDER BY published_date DESC LIMIT 8"
)
_GAP_DETAIL = text(
    "SELECT id, sector_slug, problem_summary, chance_summary, detail_summary, next_actions "
    "FROM gap_issues WHERE id = :iid"
)
_CHANCE_LIST = text(
    "SELECT o.id, o.sector_slug, o.title, o.opportunity_type, o.host_name, o.benefit_summary, "
    "       o.d_day_date, m.match_score, m.match_reason "
    "FROM chance_opportunities o "
    "LEFT JOIN user_chance_matches m ON m.opportunity_id = o.id AND m.user_id = :uid "
    "WHERE o.is_active = true AND (CAST(:otype AS varchar) IS NULL OR o.opportunity_type = :otype) "
    "ORDER BY m.match_score DESC NULLS LAST, o.d_day_date ASC NULLS LAST LIMIT 8"
)
_SYNC_LATEST = text(
    "SELECT DISTINCT ON (sector_slug) sector_slug, score, badge, explanation, recorded_date "
    "FROM sync_scores_daily WHERE user_id = :uid "
    "ORDER BY sector_slug, recorded_date DESC"
)
_DOC_SEARCH = text(
    "SELECT source_table, source_id, content_text, sector_slug, "
    "       (embedding <=> CAST(:vec AS halfvec(3072))) AS distance "
    "FROM document_embeddings "
    "WHERE (CAST(:sector AS varchar) IS NULL OR sector_slug = :sector) "
    "  AND created_at >= now() - interval '90 days' "
    "ORDER BY embedding <=> CAST(:vec AS halfvec(3072)) LIMIT 24"
)

_MAX_DISTANCE = 0.75  # cosine distance 컷 — 초과분은 잡음으로 간주.


class CoachInsightRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def pulse_trends(self, sector_slug: str | None) -> dict:
        rows = (await self.session.execute(_PULSE_LATEST, {"sector": sector_slug})).mappings().all()
        items = sorted(rows, key=lambda r: r["score"] or 0, reverse=True)
        return {
            "sectors": [
                {
                    "sector": r["sector_slug"],
                    "score": r["score"],
                    "momentumPct": float(r["momentum_pct"]) if r["momentum_pct"] is not None else None,
                    "badge": r["status_badge"],
                    "date": str(r["recorded_date"]),
                }
                for r in items
            ]
        }

    async def gap_issues(self, sector_slug: str | None, issue_id: int | None) -> dict:
        if issue_id is not None:
            row = (await self.session.execute(_GAP_DETAIL, {"iid": issue_id})).mappings().first()
            if row is None:
                return {"issue": None}
            return {
                "issue": {
                    "id": row["id"],
                    "sector": row["sector_slug"],
                    "problem": row["problem_summary"],
                    "chance": row["chance_summary"],
                    "detail": row["detail_summary"],
                    "nextActions": row["next_actions"],
                }
            }
        rows = (await self.session.execute(_GAP_LIST, {"sector": sector_slug})).mappings().all()
        return {
            "issues": [
                {
                    "id": r["id"],
                    "sector": r["sector_slug"],
                    "problem": r["problem_summary"],
                    "chance": r["chance_summary"],
                    "date": str(r["published_date"]),
                }
                for r in rows
            ]
        }

    async def chance_matches(self, user_id: str, opportunity_type: str | None) -> dict:
        rows = (
            await self.session.execute(_CHANCE_LIST, {"uid": user_id, "otype": opportunity_type})
        ).mappings().all()
        return {
            "opportunities": [
                {
                    "id": r["id"],
                    "sector": r["sector_slug"],
                    "title": r["title"],
                    "type": r["opportunity_type"],
                    "host": r["host_name"],
                    "benefit": r["benefit_summary"],
                    "dDay": str(r["d_day_date"]) if r["d_day_date"] else None,
                    "matchScore": r["match_score"],
                    "matchReason": r["match_reason"],
                }
                for r in rows
            ]
        }

    async def sync_snapshot(self, user_id: str) -> dict:
        rows = (await self.session.execute(_SYNC_LATEST, {"uid": user_id})).mappings().all()
        items = sorted(rows, key=lambda r: r["score"] or 0, reverse=True)
        return {
            "scores": [
                {"sector": r["sector_slug"], "score": r["score"], "badge": r["badge"], "why": r["explanation"]}
                for r in items
            ]
        }

    async def search_documents(self, query_vec: list[float], sector_slug: str | None) -> list[dict]:
        vec = "[" + ",".join(f"{v:.6f}" for v in query_vec) + "]"
        rows = (
            await self.session.execute(_DOC_SEARCH, {"vec": vec, "sector": sector_slug})
        ).mappings().all()
        seen: set[tuple] = set()
        out: list[dict] = []
        for r in rows:
            key = (r["source_table"], r["source_id"])
            if key in seen or (r["distance"] is not None and float(r["distance"]) > _MAX_DISTANCE):
                continue
            seen.add(key)
            out.append(
                {
                    "sourceTable": r["source_table"],
                    "sourceId": r["source_id"],
                    "sector": r["sector_slug"],
                    "text": (r["content_text"] or "")[:400],
                }
            )
            if len(out) >= 8:
                break
        return out
```

- [ ] **Step 4: tool 팩토리 구현**

`backend/domain/ai_coach/spokes/agents/tools/__init__.py`:

```python
# 코치 에이전트 tool 패키지 — 내부 조회(read-only) 래퍼 모음
```

`backend/domain/ai_coach/spokes/agents/tools/internal_tools.py`:

```python
# 코치 내부 조회 tool 6종 — 기존 Gold·자기모델 정제층의 read-only LangChain tool 래퍼

from __future__ import annotations

from langchain_core.tools import tool

from core.database import AsyncSessionLocal

TOOL_LABELS: dict[str, str] = {
    "get_pulse_trends": "시장 트렌드 조회",
    "get_gap_issues": "미해결 기회 조회",
    "get_chance_matches": "맞춤 공고 조회",
    "get_sync_snapshot": "섹터 적합도 조회",
    "get_user_profile": "사용자 성향 조회",
    "search_insights": "인사이트 의미 검색",
}


async def _embed_query(query: str) -> list[float]:
    """쿼리 임베딩 — 저장 임베딩과 동일 모델(text-embedding-3-large) 강제."""
    from openai import AsyncOpenAI

    from core.config.settings import get_settings

    settings = get_settings()
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    res = await client.embeddings.create(model=settings.llm_embed_model, input=query)
    return res.data[0].embedding


def build_internal_tools(user_id: str) -> list:
    """user_id 를 클로저로 고정한 tool 목록 — LLM 인자로 user_id 를 받지 않는다(권한 상승 차단)."""
    from domain.ai_coach.hub.repositories.coach_insight_repository import CoachInsightRepository

    @tool
    async def get_pulse_trends(sector_slug: str | None = None) -> dict:
        """12개 산업 섹터의 최신 트렌드 점수·모멘텀·배지를 조회한다. sector_slug 를 주면 해당 섹터만."""
        async with AsyncSessionLocal() as db:
            return await CoachInsightRepository(db).pulse_trends(sector_slug)

    @tool
    async def get_gap_issues(sector_slug: str | None = None, issue_id: int | None = None) -> dict:
        """시장의 미해결 문제·청년 기회(Gap 이슈)를 조회한다. issue_id 를 주면 상세·실행 제안까지."""
        async with AsyncSessionLocal() as db:
            return await CoachInsightRepository(db).gap_issues(sector_slug, issue_id)

    @tool
    async def get_chance_matches(opportunity_type: str | None = None) -> dict:
        """사용자 맞춤 공고(채용 JOB·부트캠프 BOOTCAMP·공모전 CONTEST·지원사업 GRANT)와 매칭 점수를 조회한다."""
        async with AsyncSessionLocal() as db:
            return await CoachInsightRepository(db).chance_matches(user_id, opportunity_type)

    @tool
    async def get_sync_snapshot() -> dict:
        """사용자의 섹터별 최신 적합도(Sync) 점수·설명을 조회한다."""
        async with AsyncSessionLocal() as db:
            return await CoachInsightRepository(db).sync_snapshot(user_id)

    @tool
    async def get_user_profile() -> dict:
        """사용자 자기모델(RIASEC·Big Five·서사)과 비민감 근거, 최근 상담 요약을 조회한다."""
        from domain.user_intelligence.hub.services.consult_memory_service import ConsultMemoryService

        async with AsyncSessionLocal() as db:
            return await ConsultMemoryService(db).read_for_coach(user_id)

    @tool
    async def search_insights(query: str, sector_slug: str | None = None) -> dict:
        """구조화 tool 로 답이 안 나오는 개방형 질문일 때, 인사이트 문서를 의미 검색한다(최근 90일)."""
        vec = await _embed_query(query)
        async with AsyncSessionLocal() as db:
            docs = await CoachInsightRepository(db).search_documents(vec, sector_slug)
        return {"documents": docs}

    return [get_pulse_trends, get_gap_issues, get_chance_matches, get_sync_snapshot, get_user_profile, search_insights]
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `cd backend && python scripts/coach_tools_test.py`
Expected: PASS 11 / FAIL 0 (6종 + 라벨 2 + 스키마 6개 중 user_id 부재 검사 포함 — check 호출 수 기준 PASS 11)

- [ ] **Step 6: 커밋**

```bash
git add backend/domain/ai_coach/hub/repositories/coach_insight_repository.py backend/domain/ai_coach/spokes/agents backend/scripts/coach_tools_test.py
git commit -m "feat(coach): 내부 조회 tool 6종 + 코치 인사이트 레포 — read-only·user_id 클로저 고정"
```

---

### Task 5: coach_graph + CoachService + 플랫폼 컨텍스트

**Files:**
- Create: `backend/domain/ai_coach/docs/platform_context.md`
- Create: `backend/domain/ai_coach/spokes/infra/coach_graph.py`
- Create: `backend/domain/ai_coach/hub/services/coach_service.py`
- Test: `backend/scripts/coach_graph_test.py`

**Interfaces:**
- Consumes: Task 2 `CoachSessionRepository`, Task 4 `build_internal_tools`/`TOOL_LABELS`, Task 1 `resolve_coach_llm`, 기존 `get_checkpointer`(consult_graph)·`consult_context.split_history`·`LlmClient.summarize_conversation`·`resolve_user_llm`.
- Produces:
  - `build_coach_graph(service, checkpointer=None)` — `prepare → agent → persist` 컴파일 그래프. custom 스트림 이벤트: `{"type":"delta","content"}` `{"type":"tool_call","name","label"}` `{"type":"tool_result","name"}` `{"type":"error","message"}`.
  - `CoachService(session)` — `get_or_create_session(user_id) -> str`, `verify_owner(user_id, session_id) -> str`, `get_messages`, `end_session`, `stream_sse(user_id, session_id, message) -> AsyncGenerator[str]`(SSE 문자열, 마지막 `done`).
  - 테스트 주입점: `service._chat_model()`(bind_tools 가능 객체 반환), `service._build_tools(user_id)`, `service._summarizer`.

- [ ] **Step 1: platform_context.md 작성**

`backend/domain/ai_coach/docs/platform_context.md`:

```markdown
# 플랫폼 컨텍스트 — 코치 시스템 프롬프트 주입용

Roadmap 은 진로 막연함을 느끼는 청년(10대 후반~30대 초반)에게 선행 행동 지표(투자 흐름·특허·검색량)
분석으로 객관적 인사이트와 성장 로드맵을 주는 AI 내비게이션 플랫폼이다.

## 탭 구조 (사용자에게 안내할 때 사용)
- **Pulse** — 12개 산업 섹터의 일별 트렌드 점수·모멘텀·경제 브리핑. 데이터: 투자 뉴스·시장 시세·특허/논문·검색량.
- **Gap** — 시장의 미해결 문제와 청년이 파고들 기회. 근거 기사·보고서 링크 포함.
- **Sync** — 사용자와 섹터의 적합도 일별 점수(프로필·성향 임베딩 기반).
- **Chance** — 채용·부트캠프·공모전·지원사업 공고와 사용자별 매칭 점수.
- **Roadmap** — AI 생성 퀘스트 트리 + 월별 성장 아카이브.
- **상담실(/consult)** — 성향(RIASEC·Big Five) 자기이해 대화. 성향 파악은 상담실 담당이다.
- **코치(/coach)** — 지금 이 대화. 데이터 근거로 진로 방향·기회·실행을 함께 판단한다.

## 데이터 신뢰 규칙
- 점수(트렌드·적합도·매칭)는 0~100. 배지는 상태 요약이다.
- 모든 판단은 tool 로 조회한 실데이터를 근거로 하고, 근거 없는 수치를 만들어내지 않는다.
```

- [ ] **Step 2: 실패하는 테스트 작성**

`backend/scripts/coach_graph_test.py`:

```python
# 코치 그래프(prepare→agent→persist) 단위 테스트 — 가짜 LLM·가짜 tool 로 이벤트 시퀀스 검증(무DB·무네트워크)

from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SCHEDULER_ENABLED", "false")

from langchain_core.messages import AIMessageChunk
from langchain_core.tools import tool

from domain.ai_coach.spokes.infra.coach_graph import build_coach_graph

PASS = 0
FAIL = 0


def check(n: str, c: bool, e: str = "") -> None:
    global PASS, FAIL
    if c:
        PASS += 1
        print(f"[PASS] {n}")
    else:
        FAIL += 1
        print(f"[FAIL] {n} {e}")


@tool
async def get_pulse_trends(sector_slug: str | None = None) -> dict:
    """가짜 트렌드 tool."""
    return {"sectors": [{"sector": "ai-software", "score": 88}]}


class FakeModel:
    """1회차엔 tool_call, 2회차엔 텍스트 스트림을 내는 가짜 ChatModel."""

    def __init__(self):
        self.round = 0

    def bind_tools(self, tools):
        return self

    async def astream(self, messages):
        self.round += 1
        if self.round == 1:
            chunk = AIMessageChunk(content="")
            chunk.tool_calls = [{"name": "get_pulse_trends", "args": {}, "id": "tc1", "type": "tool_call"}]
            yield chunk
        else:
            yield AIMessageChunk(content="AI 섹터가 ")
            yield AIMessageChunk(content="강세예요.")


class FakeService:
    def __init__(self):
        self.persisted: list[tuple] = []
        self.model = FakeModel()

    async def _maybe_summarize(self, session_id):
        return None

    async def _load_history(self, session_id):
        return []

    async def _load_context_system(self, user_id):
        return "SYS"

    def _chat_model(self):
        return self.model

    def _build_tools(self, user_id):
        return [get_pulse_trends]

    async def _persist_assistant(self, session_id, content):
        self.persisted.append((session_id, content))


async def main() -> int:
    svc = FakeService()
    graph = build_coach_graph(svc, checkpointer=None)
    events = []
    state = {"user_id": "u1", "session_id": "s1", "message": "요즘 뜨는 분야?"}
    async for chunk in graph.astream(state, {"configurable": {"thread_id": "s1"}}, stream_mode="custom"):
        events.append(chunk)

    types = [e.get("type") for e in events]
    check("tool_call 이벤트", "tool_call" in types)
    check("tool_result 이벤트", "tool_result" in types)
    check("delta 이벤트", types.count("delta") == 2)
    check("tool_call 이 delta 보다 먼저", types.index("tool_call") < types.index("delta"))
    tc = next(e for e in events if e.get("type") == "tool_call")
    check("tool_call 라벨 포함", bool(tc.get("label")))
    check("persist 1회·전체 응답", svc.persisted == [("s1", "AI 섹터가 강세예요.")])

    print(f"\n합계: PASS {PASS} / FAIL {FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
```

- [ ] **Step 3: 실패 확인**

Run: `cd backend && python scripts/coach_graph_test.py`
Expected: `ModuleNotFoundError: ... coach_graph`

- [ ] **Step 4: coach_graph 구현**

`backend/domain/ai_coach/spokes/infra/coach_graph.py`:

```python
# 코치 대화 LangGraph 런타임 — prepare→agent(tool 루프)→persist. 델타·tool 이벤트를 custom 스트림으로 방출.

from __future__ import annotations

import json
import logging
from typing import Any, TypedDict

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph

from domain.ai_coach.spokes.agents.tools.internal_tools import TOOL_LABELS

logger = logging.getLogger(__name__)

_MAX_TOOL_ROUNDS = 4  # tool 호출 루프 상한 — 폭주 방지(스펙 §5).


class CoachState(TypedDict, total=False):
    user_id: str
    session_id: str
    message: str
    summary: str | None
    recent: list[dict]
    system_content: str
    response: str
    error: str | None


def _chunk_text(chunk: Any) -> str:
    """AIMessageChunk.content(str | block list) → 순수 텍스트. Anthropic 은 블록 리스트를 준다."""
    content = getattr(chunk, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"
        )
    return ""


def _to_lc_messages(system: str, summary: str | None, recent: list[dict], message: str) -> list:
    """시스템+요약블록+최근 히스토리+현재 메시지 → LangChain 메시지 리스트."""
    out: list = [SystemMessage(content=system)]
    if summary:
        out.append(SystemMessage(content=f"[이전 대화 요약]\n{summary}"))
    for m in recent:
        role = m.get("role")
        content = m.get("content") or ""
        out.append(HumanMessage(content=content) if role == "user" else AIMessage(content=content))
    out.append(HumanMessage(content=message))
    return out


def build_coach_graph(service: Any, checkpointer: Any | None = None):
    """서비스 심을 노드로 엮은 코치 그래프 컴파일 — 노드는 service 속성을 호출 시점에 읽는다(테스트 주입 호환)."""

    async def prepare(state: CoachState) -> dict:
        summary = await service._maybe_summarize(state["session_id"])
        recent = await service._load_history(state["session_id"])
        system_content = await service._load_context_system(state["user_id"])
        return {"summary": summary, "recent": recent, "system_content": system_content}

    async def agent(state: CoachState) -> dict:
        writer = get_stream_writer()
        tools = service._build_tools(state["user_id"])
        tool_map = {t.name: t for t in tools}
        llm = service._chat_model().bind_tools(tools)
        messages = _to_lc_messages(
            state["system_content"], state.get("summary"), state["recent"], state["message"]
        )
        acc = ""
        try:
            for _ in range(_MAX_TOOL_ROUNDS + 1):
                final = None
                async for chunk in llm.astream(messages):
                    text = _chunk_text(chunk)
                    if text:
                        acc += text
                        writer({"type": "delta", "content": text})
                    final = chunk if final is None else final + chunk
                calls = list(getattr(final, "tool_calls", None) or [])
                if not calls:
                    break
                messages.append(final)
                for tc in calls:
                    name = tc.get("name")
                    writer({"type": "tool_call", "name": name, "label": TOOL_LABELS.get(name, name)})
                    tool_obj = tool_map.get(name)
                    if tool_obj is None:
                        result: Any = {"error": f"알 수 없는 tool: {name}"}
                    else:
                        try:
                            result = await tool_obj.ainvoke(tc.get("args") or {})
                        except Exception as te:  # tool 실패는 대화를 끊지 않는다 — 에러를 관찰로 되돌린다.
                            logger.warning(f"코치 tool 실패({name}): {te}")
                            result = {"error": str(te)}
                    writer({"type": "tool_result", "name": name})
                    messages.append(
                        ToolMessage(
                            content=json.dumps(result, ensure_ascii=False, default=str),
                            tool_call_id=tc.get("id") or "",
                        )
                    )
        except Exception as e:  # 스트림 도중 실패 — 에러 이벤트로 알리고 부분 응답은 보존.
            writer({"type": "error", "message": str(e)})
            return {"response": acc, "error": str(e)}
        return {"response": acc, "error": None}

    async def persist(state: CoachState) -> dict:
        if state.get("response"):
            await service._persist_assistant(state["session_id"], state["response"])
        return {}

    g = StateGraph(CoachState)
    g.add_node("prepare", prepare)
    g.add_node("agent", agent)
    g.add_node("persist", persist)
    g.add_edge(START, "prepare")
    g.add_edge("prepare", "agent")
    g.add_edge("agent", "persist")
    g.add_edge("persist", END)
    return g.compile(checkpointer=checkpointer)
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `cd backend && python scripts/coach_graph_test.py`
Expected: PASS 6 / FAIL 0. (FakeModel의 `chunk.tool_calls =` 직접 대입이 pydantic 제약으로 실패하면 `AIMessageChunk(content="", tool_calls=[...])` 생성자 방식 또는 `tool_call_chunks` 사용으로 테스트 쪽을 조정한다 — 프로덕션 코드가 아닌 fake 조립 문제.)

- [ ] **Step 6: CoachService 구현**

`backend/domain/ai_coach/hub/services/coach_service.py`:

```python
# AI 코치 서비스 — 세션 영속·롤링 요약 + Sonnet tool-calling 에이전트 SSE 스트리밍

from __future__ import annotations

import json
import logging
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from core.config.settings import get_settings
from core.database import AsyncSessionLocal
from core.llm.client import LlmClient
from core.llm.provider import resolve_coach_llm, resolve_user_llm
from domain.ai_coach.hub.repositories.coach_session_repository import CoachSessionRepository
from domain.ai_coach.spokes.agents.tools.internal_tools import build_internal_tools
from domain.ai_coach.spokes.infra.coach_graph import build_coach_graph
from domain.user_intelligence.hub.services import consult_context
from domain.user_intelligence.spokes.infra.consult_graph import disable_checkpointer, get_checkpointer

logger = logging.getLogger(__name__)

_WINDOW_N = 20
_THRESHOLD_T = 24

_PLATFORM_CONTEXT = (Path(__file__).resolve().parents[2] / "docs" / "platform_context.md").read_text(
    encoding="utf-8"
)

_COACH_SYSTEM_PROMPT = """당신은 Roadmap 플랫폼의 AI 진로 코치다. 상담실이 파악한 사용자의 성향과
플랫폼이 수집·정제한 시장 데이터를 근거로, 사용자의 진로 방향·기회·실행 방법을 함께 판단한다.

[원칙]
1. 근거 우선 — 시장·기회·적합도·성향 판단은 반드시 tool 로 실데이터를 조회한 뒤 말한다. 수치를 지어내지 않는다.
2. tool 라우팅 — 트렌드는 get_pulse_trends, 미해결 기회는 get_gap_issues, 공고는 get_chance_matches,
   적합도는 get_sync_snapshot, 사용자 성향은 get_user_profile. 이 도구들로 답이 안 나오는 개방형 질문만
   search_insights(의미 검색)를 쓴다.
3. 개인화 — 첫 판단 전에 get_user_profile 로 성향·근거를 확인하고, 조언을 그 사람에게 맞춘다.
   성향이 비어 있으면 상담실(/consult)에서 자기이해 대화를 먼저 하도록 권한다.
4. 인용 — 데이터를 근거로 쓸 때 어느 탭·데이터인지 자연스럽게 밝힌다(예: "Pulse 기준 AI 섹터가…").
5. 역할 경계 — 성향을 새로 캐묻는 심층 조사는 상담실 몫이다. 코치는 파악된 성향을 활용해 방향·실행을 다룬다.
6. 대화 태도 — 한 턴에 핵심 하나. 단정 대신 근거와 함께 제안하고, 다음 행동을 구체적으로 제시한다.
"""


def _sse(obj: dict) -> str:
    """SSE 이벤트 1건(JSON data) 직렬화."""
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


class CoachService:
    def __init__(self, session: AsyncSession):
        self.session = session
        settings = get_settings()
        try:
            self._anthropic_key, self._coach_model = resolve_coach_llm(settings)
            self._llm_error = None
        except Exception as e:  # 설정 오류는 stream 에서 노출(비-LLM 엔드포인트는 유지).
            self._anthropic_key = self._coach_model = None
            self._llm_error = str(e)
        try:  # 롤링 요약은 저렴한 기존 사용자 LLM(Gemini) 재사용.
            self._sum_key, self._sum_model, self._sum_base = resolve_user_llm(settings)
        except Exception:
            self._sum_key = self._sum_model = self._sum_base = None
        self._summarizer = self._default_summarizer
        self._graph = None

    # ---- 주입점 (테스트 대체 가능) ----

    def _chat_model(self):
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(model=self._coach_model, api_key=self._anthropic_key, max_tokens=2048)

    def _build_tools(self, user_id: str) -> list:
        return build_internal_tools(user_id)

    async def _default_summarizer(self, prior_summary, older):
        if not self._sum_key:
            return prior_summary
        llm = LlmClient(api_key=self._sum_key, model=self._sum_model, base_url=self._sum_base)
        return await llm.summarize_conversation(prior_summary, older)

    # ---- 세션 수명주기 (consult 와 동일 시맨틱) ----

    async def get_or_create_session(self, user_id: str) -> str:
        repo = CoachSessionRepository(self.session)
        existing = await repo.get_latest_active_session(user_id)
        return existing or await repo.create_session(user_id)

    async def verify_owner(self, user_id: str, session_id: str) -> str:
        sess = await CoachSessionRepository(self.session).get_session(session_id)
        if sess is None:
            raise LookupError("세션을 찾을 수 없습니다.")
        if sess["user_id"] != user_id:
            raise PermissionError("세션 접근 권한이 없습니다.")
        return sess["status"]

    async def get_messages(self, user_id: str, session_id: str) -> list[dict]:
        await self.verify_owner(user_id, session_id)
        return await CoachSessionRepository(self.session).fetch_messages(session_id)

    async def end_session(self, user_id: str, session_id: str) -> None:
        await self.verify_owner(user_id, session_id)
        await CoachSessionRepository(self.session).end_session(session_id)

    # ---- 그래프 노드 지원 ----

    async def _maybe_summarize(self, session_id: str) -> str | None:
        """새로 밀려난(아직 미요약) 오래된 메시지만 증분 롤링 요약. 독립 세션."""
        async with AsyncSessionLocal() as db:
            repo = CoachSessionRepository(db)
            sess = await repo.get_session(session_id)
            if sess is None:
                return None
            prior = sess["context_summary"]
            summarized_until = sess["summarized_until"]
            total = await repo.count_messages(session_id)
            if total <= _THRESHOLD_T:
                return prior
            cutoff = total - _WINDOW_N
            if cutoff <= summarized_until:
                return prior
            msgs = await repo.fetch_messages(session_id)
            new_older = msgs[summarized_until:cutoff]
            if not new_older:
                return prior
            try:
                summary = await self._summarizer(prior, new_older)
            except Exception as e:  # 요약 실패는 치명적이지 않음 — 기존 요약 유지.
                logger.warning(f"코치 롤링 요약 실패(기존 요약 유지): {e}")
                return prior
            if summary:
                await repo.update_summary(session_id, summary, cutoff)
                return summary
            return prior

    async def _load_history(self, session_id: str) -> list[dict]:
        """최근 윈도우 히스토리 — 방금 저장된 현재 user 메시지는 제외(별도 주입)."""
        async with AsyncSessionLocal() as db:
            all_msgs = await CoachSessionRepository(db).fetch_messages(session_id)
        history = all_msgs[:-1] if all_msgs and all_msgs[-1]["role"] == "user" else all_msgs
        _older, recent = consult_context.split_history(history, _WINDOW_N)
        return recent

    async def _load_context_system(self, user_id: str) -> str:
        """코치 시스템 프롬프트 + 플랫폼 컨텍스트. 자기모델은 tool(get_user_profile)로 조회한다."""
        return _COACH_SYSTEM_PROMPT + "\n\n" + _PLATFORM_CONTEXT

    async def _persist_assistant(self, session_id: str, content: str) -> None:
        async with AsyncSessionLocal() as db:
            await CoachSessionRepository(db).add_message(session_id, "assistant", content)

    async def _persist_assistant_if_missing(self, session_id: str, content: str) -> None:
        """강등 경로 저장 — persist 노드가 이미 같은 내용을 저장했으면 건너뛴다(이중 저장 방지)."""
        if not content:
            return
        try:
            async with AsyncSessionLocal() as db:
                msgs = await CoachSessionRepository(db).fetch_messages(session_id)
            if msgs and msgs[-1]["role"] == "assistant" and msgs[-1]["content"] == content:
                return
            await self._persist_assistant(session_id, content)
        except Exception as pe:
            logger.warning(f"코치 강등 경로 부분 응답 저장 실패: {pe}")

    async def _get_graph(self):
        if self._graph is None:
            self._graph = build_coach_graph(self, await get_checkpointer())
        return self._graph

    # ---- SSE ----

    async def stream_sse(self, user_id: str, session_id: str, message: str):
        """사용자 메시지 저장 → 코치 그래프 구동 → custom 이벤트를 SSE 로 중계."""
        async with AsyncSessionLocal() as db:
            await CoachSessionRepository(db).add_message(session_id, "user", message)

        if self._llm_error:
            yield _sse({"type": "error", "message": f"코치 모델 설정 오류 — {self._llm_error}"})
            yield _sse({"type": "done"})
            return

        graph = await self._get_graph()
        config = {"configurable": {"thread_id": session_id}}
        state_in = {"user_id": user_id, "session_id": session_id, "message": message}
        acc = ""
        try:
            async for chunk in graph.astream(state_in, config, stream_mode="custom"):
                if chunk.get("type") == "delta":
                    acc += chunk.get("content") or ""
                yield _sse(chunk)
        except Exception as e:  # 그래프 실행 실패 — 체크포인터 강등하고 부분 응답 보존.
            logger.warning(f"코치 그래프 실행 실패(체크포인터 비활성 강등): {e}")
            disable_checkpointer()
            self._graph = None
            await self._persist_assistant_if_missing(session_id, acc)
            yield _sse({"type": "error", "message": str(e)})
        yield _sse({"type": "done"})
```

주의: coach thread_id 는 코치 session_id(UUID)라 consult thread 와 충돌하지 않는다.

- [ ] **Step 7: 임포트 스모크 + 그래프 테스트 재실행**

Run: `cd backend && python -c "from domain.ai_coach.hub.services.coach_service import CoachService; print('ok')" && python scripts/coach_graph_test.py`
Expected: `ok` + PASS 6 / FAIL 0

- [ ] **Step 8: 기존 consult 테스트 회귀 확인**

Run: `cd backend && python scripts/consult_context_test.py && python scripts/consult_session_models_import_test.py`
Expected: 모두 PASS (coach 도입이 consult 를 건드리지 않았음을 확인)

- [ ] **Step 9: 커밋**

```bash
git add backend/domain/ai_coach/docs/platform_context.md backend/domain/ai_coach/spokes/infra/coach_graph.py backend/domain/ai_coach/hub/services/coach_service.py backend/scripts/coach_graph_test.py
git commit -m "feat(coach): Sonnet tool-calling 코치 그래프·서비스 — prepare→agent→persist, tool 이벤트 SSE"
```

---

### Task 6: 코치 HTTP 라우터 + main.py 등록

**Files:**
- Create: `backend/api/v1/coach/__init__.py` (빈 파일)
- Create: `backend/api/v1/coach/coach_routor.py`
- Modify: `backend/main.py` (import + include_router 2줄)
- Test: `backend/scripts/coach_endpoint_test.py`

**Interfaces:**
- Consumes: `CoachService` (Task 5).
- Produces: `POST /api/coach/sessions`, `POST /api/coach/stream`(SSE), `POST /api/coach/sessions/{id}/end`, `GET /api/coach/sessions/{id}/messages` — consult 라우터와 동일 계약(404/403/409 매핑 포함).

- [ ] **Step 1: 실패하는 테스트 작성**

`backend/scripts/coach_endpoint_test.py`:

```python
# 코치 라우터 등록·경로 계약 단위 테스트(무DB — 앱 라우트 테이블만 검사)

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SCHEDULER_ENABLED", "false")

from main import app

PASS = 0
FAIL = 0


def check(n: str, c: bool, e: str = "") -> None:
    global PASS, FAIL
    if c:
        PASS += 1
        print(f"[PASS] {n}")
    else:
        FAIL += 1
        print(f"[FAIL] {n} {e}")


def run() -> int:
    routes = {(r.path, m) for r in app.routes if hasattr(r, "methods") for m in (r.methods or [])}
    check("세션 생성", ("/api/coach/sessions", "POST") in routes)
    check("스트림", ("/api/coach/stream", "POST") in routes)
    check("세션 종료", ("/api/coach/sessions/{session_id}/end", "POST") in routes)
    check("히스토리", ("/api/coach/sessions/{session_id}/messages", "GET") in routes)

    print(f"\n합계: PASS {PASS} / FAIL {FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(run())
```

- [ ] **Step 2: 실패 확인**

Run: `cd backend && python scripts/coach_endpoint_test.py`
Expected: FAIL 4 (경로 미등록)

- [ ] **Step 3: 라우터 구현**

`backend/api/v1/coach/coach_routor.py`:

```python
# AI 코치 HTTP 라우터 — 세션 생성·tool-calling 스트리밍·종료·히스토리

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from core.api_guards import get_authenticated_user_id
from core.database import get_db
from domain.ai_coach.hub.services.coach_service import CoachService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/coach", tags=["coach"])


class CoachStreamRequest(BaseModel):
    sessionId: uuid.UUID
    message: str


@router.post("/sessions")
async def create_session(
    user_id: str = Depends(get_authenticated_user_id),
    db: AsyncSession = Depends(get_db),
):
    """코치 대화 세션 생성 또는 재개(방문 간 최근 active 세션 이어가기)."""
    session_id = await CoachService(db).get_or_create_session(user_id)
    return {"success": True, "sessionId": session_id}


@router.post("/stream")
async def coach_stream(
    request: CoachStreamRequest,
    user_id: str = Depends(get_authenticated_user_id),
    db: AsyncSession = Depends(get_db),
):
    """세션 소유권 검증 후 데이터 tool 을 쓰는 코치 응답 SSE 스트리밍."""
    svc = CoachService(db)
    try:
        status = await svc.verify_owner(user_id, str(request.sessionId))
    except LookupError:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")
    except PermissionError:
        raise HTTPException(status_code=403, detail="세션 접근 권한이 없습니다.")
    if status == "ended":
        raise HTTPException(status_code=409, detail="종료된 세션입니다.")
    generator = svc.stream_sse(user_id, str(request.sessionId), request.message)
    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/sessions/{session_id}/end")
async def end_session(
    session_id: uuid.UUID,
    user_id: str = Depends(get_authenticated_user_id),
    db: AsyncSession = Depends(get_db),
):
    """세션 종료(소유권 검증). 이미 종료면 멱등."""
    try:
        await CoachService(db).end_session(user_id, str(session_id))
    except LookupError:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")
    except PermissionError:
        raise HTTPException(status_code=403, detail="세션 접근 권한이 없습니다.")
    return {"success": True}


@router.get("/sessions/{session_id}/messages")
async def get_messages(
    session_id: uuid.UUID,
    user_id: str = Depends(get_authenticated_user_id),
    db: AsyncSession = Depends(get_db),
):
    """세션 대화 히스토리(소유권 검증)."""
    try:
        messages = await CoachService(db).get_messages(user_id, str(session_id))
    except LookupError:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")
    except PermissionError:
        raise HTTPException(status_code=403, detail="세션 접근 권한이 없습니다.")
    return {"success": True, "messages": messages}
```

`backend/main.py` — consult 라우터 import 옆에 추가:

```python
from api.v1.coach.coach_routor import router as coach_v1_router
```

등록부(consult 등록 라인 옆):

```python
app.include_router(coach_v1_router, prefix=API_V1_PREFIX)
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd backend && python scripts/coach_endpoint_test.py`
Expected: PASS 4 / FAIL 0

- [ ] **Step 5: 커밋**

```bash
git add backend/api/v1/coach backend/main.py backend/scripts/coach_endpoint_test.py
git commit -m "feat(coach): 코치 SSE 라우터 4종 + 앱 등록 — consult 와 동일 계약"
```

---

### Task 7: 프론트 — coach API 클라이언트 + 최소 CoachView

**Files:**
- Create: `www.yeotaeho.kr/src/lib/api/coach.ts`
- Create: `www.yeotaeho.kr/src/components/features/coach/CoachView.tsx`
- Modify: `www.yeotaeho.kr/src/app/(main)/coach/page.tsx` (준비중 안내 → CoachView 렌더)

**Interfaces:**
- Consumes: 백엔드 `/api/coach/*` (Task 6), 기존 `getStore()`(토큰)·`useStore`(인증 상태).
- Produces: `createCoachSession() -> Promise<string|null>`, `fetchCoachMessages(sessionId) -> Promise<CoachApiMessage[]>`, `streamCoach(sessionId, message, handlers, signal?) -> Promise<void>` — handlers: `{ onDelta, onToolCall?, onToolResult?, onError? }`.

- [ ] **Step 1: API 클라이언트 작성**

`www.yeotaeho.kr/src/lib/api/coach.ts`:

```typescript
// AI 코치 SSE 스트리밍 클라이언트 — delta·tool_call·tool_result 이벤트 수신(fetch ReadableStream)
import { getStore } from '@/store';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export interface CoachApiMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface CoachStreamHandlers {
  onDelta: (text: string) => void;
  onToolCall?: (name: string, label: string) => void;
  onToolResult?: (name: string) => void;
  onError?: (message: string) => void;
}

export async function createCoachSession(): Promise<string | null> {
  const token = getStore().getState().token;
  const res = await fetch(`${API_BASE_URL}/api/coach/sessions`, {
    method: 'POST',
    headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    credentials: 'include',
  });
  if (!res.ok) return null;
  const data = await res.json();
  return data?.sessionId ?? null;
}

export async function fetchCoachMessages(sessionId: string): Promise<CoachApiMessage[]> {
  const token = getStore().getState().token;
  const res = await fetch(`${API_BASE_URL}/api/coach/sessions/${sessionId}/messages`, {
    headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    credentials: 'include',
  });
  if (!res.ok) return [];
  const data = await res.json();
  return data?.messages ?? [];
}

export async function streamCoach(
  sessionId: string,
  message: string,
  handlers: CoachStreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const token = getStore().getState().token;
  const res = await fetch(`${API_BASE_URL}/api/coach/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    credentials: 'include',
    body: JSON.stringify({ sessionId, message }),
    signal,
  });
  if (!res.ok || !res.body) {
    throw new Error(`coach stream failed: ${res.status}`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const events = buffer.split('\n\n');
    buffer = events.pop() ?? ''; // 마지막 미완성 조각 보존
    for (const evt of events) {
      const dataLine = evt.split('\n').find((l) => l.startsWith('data:'));
      if (!dataLine) continue;
      const raw = dataLine.slice(5).trim();
      if (!raw) continue;
      try {
        const obj = JSON.parse(raw) as {
          type?: string;
          content?: string;
          name?: string;
          label?: string;
          message?: string;
        };
        if (obj.type === 'delta' && obj.content) handlers.onDelta(obj.content);
        if (obj.type === 'tool_call' && obj.name) handlers.onToolCall?.(obj.name, obj.label ?? obj.name);
        if (obj.type === 'tool_result' && obj.name) handlers.onToolResult?.(obj.name);
        if (obj.type === 'error') handlers.onError?.(obj.message ?? '코치 응답 중 오류가 발생했어요.');
      } catch {
        /* 파싱 불가 조각 무시 */
      }
    }
  }
}
```

- [ ] **Step 2: CoachView 작성 (최소)**

`www.yeotaeho.kr/src/components/features/coach/CoachView.tsx`:

```tsx
// AI 코치 대화 화면(최소) — SSE 스트리밍 + tool 활동 인디케이터
"use client";

import { SendHorizonal, Sparkles } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { createCoachSession, fetchCoachMessages, streamCoach } from "@/lib/api/coach";
import { useStore } from "@/store";

type CoachMessage = {
  id: string;
  role: "user" | "assistant";
  text: string;
};

function uid() {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

const GREETING: CoachMessage = {
  id: "m0",
  role: "assistant",
  text:
    "안녕하세요, AI 코치입니다. 상담실에서 파악한 성향과 시장 데이터를 근거로 진로 방향과 기회를 함께 판단해 드려요. 어떤 고민부터 볼까요?",
};

export function CoachView() {
  const endRef = useRef<HTMLDivElement>(null);
  const isAuthenticated = useStore((s) => s.isAuthenticated);
  const [messages, setMessages] = useState<CoachMessage[]>([GREETING]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [toolActivity, setToolActivity] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [sessionError, setSessionError] = useState(false);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading, toolActivity]);

  // 로그인 상태에서 세션 재개(get-or-create) + 히스토리 로드
  useEffect(() => {
    if (!isAuthenticated) return;
    (async () => {
      const sid = await createCoachSession();
      if (!sid) {
        setSessionError(true);
        return;
      }
      setSessionId(sid);
      const msgs = await fetchCoachMessages(sid);
      if (msgs.length > 0) {
        setMessages(msgs.map((m) => ({ id: uid(), role: m.role, text: m.content })));
      }
    })();
  }, [isAuthenticated]);

  const send = useCallback(async () => {
    const message = input.trim();
    if (!message || isLoading || !sessionId) return;
    setInput("");
    setIsLoading(true);
    const assistantId = uid();
    setMessages((prev) => [
      ...prev,
      { id: uid(), role: "user", text: message },
      { id: assistantId, role: "assistant", text: "" },
    ]);
    const appendDelta = (text: string) =>
      setMessages((prev) =>
        prev.map((m) => (m.id === assistantId ? { ...m, text: m.text + text } : m)),
      );
    try {
      await streamCoach(sessionId, message, {
        onDelta: (t) => {
          setToolActivity(null);
          appendDelta(t);
        },
        onToolCall: (_name, label) => setToolActivity(label),
        onToolResult: () => setToolActivity(null),
        onError: (msg) => appendDelta(`\n(${msg})`),
      });
    } catch {
      appendDelta("\n(연결에 문제가 생겼어요. 잠시 후 다시 시도해 주세요.)");
    } finally {
      setToolActivity(null);
      setIsLoading(false);
    }
  }, [input, isLoading, sessionId]);

  return (
    <div className="flex h-full flex-col">
      <header className="flex items-center gap-2 border-b border-border px-6 py-4">
        <Sparkles className="h-5 w-5 text-primary" />
        <div>
          <h1 className="text-base font-semibold">AI 코치</h1>
          <p className="text-xs text-muted-foreground">데이터 근거로 진로 방향·기회·실행을 함께 판단해요.</p>
        </div>
      </header>

      <div className="flex-1 space-y-4 overflow-y-auto px-6 py-6">
        {!isAuthenticated && (
          <p className="text-sm text-muted-foreground">로그인하면 코치와 대화를 시작할 수 있어요.</p>
        )}
        {sessionError && (
          <p className="text-sm text-destructive">세션을 열지 못했어요. 새로고침 후 다시 시도해 주세요.</p>
        )}
        {messages.map((m) => (
          <div key={m.id} className={m.role === "user" ? "flex justify-end" : "flex justify-start"}>
            <div
              className={
                m.role === "user"
                  ? "max-w-[80%] rounded-2xl bg-primary px-4 py-2.5 text-sm text-primary-foreground"
                  : "max-w-[80%] whitespace-pre-wrap rounded-2xl bg-muted px-4 py-2.5 text-sm"
              }
            >
              {m.text || (isLoading ? "…" : "")}
            </div>
          </div>
        ))}
        {toolActivity && (
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <span className="h-2 w-2 animate-pulse rounded-full bg-primary" />
            {toolActivity} 중…
          </div>
        )}
        <div ref={endRef} />
      </div>

      <form
        className="flex items-center gap-2 border-t border-border px-6 py-4"
        onSubmit={(e) => {
          e.preventDefault();
          void send();
        }}
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={isAuthenticated ? "코치에게 물어보세요…" : "로그인이 필요해요"}
          disabled={!isAuthenticated || isLoading || !sessionId}
          className="flex-1 rounded-xl border border-border bg-background px-4 py-2.5 text-sm outline-none focus:border-primary"
        />
        <button
          type="submit"
          disabled={!isAuthenticated || isLoading || !input.trim()}
          className="rounded-xl bg-primary p-2.5 text-primary-foreground disabled:opacity-40"
          aria-label="전송"
        >
          <SendHorizonal className="h-4 w-4" />
        </button>
      </form>
    </div>
  );
}
```

스타일 클래스(`border-border`·`bg-muted` 등)는 기존 ConsultView가 쓰는 토큰과 대조해 프로젝트 실제 토큰으로 맞춘다 — 디자인 시스템이 다르면 ConsultView의 말풍선·입력바 클래스를 그대로 복사한다.

- [ ] **Step 3: /coach 페이지 교체**

`www.yeotaeho.kr/src/app/(main)/coach/page.tsx` 전체 교체:

```tsx
// AI 코치 탭 페이지 — CoachView 렌더
import { CoachView } from "@/components/features/coach/CoachView";

export default function CoachPage() {
  return <CoachView />;
}
```

기존 준비중 안내 콘텐츠는 제거. `CoachSidebar`는 레이아웃 소관이므로 건드리지 않는다.

- [ ] **Step 4: 타입 체크·빌드 확인**

Run: `cd www.yeotaeho.kr && pnpm exec tsc --noEmit`
Expected: 에러 0 (기존 에러가 있다면 coach 관련 신규 에러 0 확인)

Run: `cd www.yeotaeho.kr && pnpm run build`
Expected: 빌드 성공, `/coach` 라우트 포함

- [ ] **Step 5: 커밋**

```bash
git add www.yeotaeho.kr/src/lib/api/coach.ts www.yeotaeho.kr/src/components/features/coach/CoachView.tsx "www.yeotaeho.kr/src/app/(main)/coach/page.tsx"
git commit -m "feat(web): /coach 준비중 페이지를 코치 대화 UI 로 전환 — SSE 스트리밍·tool 활동 표시"
```

---

### Task 8: 라이브 verify 스크립트 (실 DB + 실 LLM)

**Files:**
- Create: `backend/scripts/coach_live_verify.py`

**Interfaces:**
- Consumes: 전체 스택. env `DATABASE_URL`·`ANTHROPIC_API_KEY`·`OPENAI_API_KEY` 필요. 실행 인자 `--user-id <uuid>` (실존 사용자).

- [ ] **Step 1: 스크립트 작성**

`backend/scripts/coach_live_verify.py`:

```python
# 코치 라이브 검증 — 실 DB tool 6종 반환 + Sonnet tool-calling 1턴 스트림 실동작 확인

from __future__ import annotations

import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SCHEDULER_ENABLED", "false")

PASS = 0
FAIL = 0


def check(n: str, c: bool, e: str = "") -> None:
    global PASS, FAIL
    if c:
        PASS += 1
        print(f"[PASS] {n}")
    else:
        FAIL += 1
        print(f"[FAIL] {n} {e}")


async def main(user_id: str) -> int:
    from core.database import AsyncSessionLocal
    from domain.ai_coach.hub.services.coach_service import CoachService
    from domain.ai_coach.spokes.agents.tools.internal_tools import build_internal_tools

    # 1) tool 6종 실 DB 반환
    tools = build_internal_tools(user_id)
    for t in tools:
        try:
            args = {"query": "요즘 유망한 분야"} if t.name == "search_insights" else {}
            result = await t.ainvoke(args)
            check(f"tool {t.name} 반환", isinstance(result, dict), str(result)[:120])
            print(f"    → {str(result)[:200]}")
        except Exception as e:
            check(f"tool {t.name} 반환", False, str(e))

    # 2) 코치 1턴 스트림 — tool_call 발생 + 텍스트 응답
    async with AsyncSessionLocal() as db:
        svc = CoachService(db)
        sid = await svc.get_or_create_session(user_id)
    types: list[str] = []
    text = ""
    async with AsyncSessionLocal() as db:
        svc = CoachService(db)
        async for sse in svc.stream_sse(user_id, sid, "요즘 시장에서 나한테 맞는 방향이 뭘까?"):
            import json as _json

            obj = _json.loads(sse.removeprefix("data: ").strip())
            types.append(obj.get("type"))
            if obj.get("type") == "delta":
                text += obj.get("content") or ""
            if obj.get("type") == "tool_call":
                print(f"    [tool_call] {obj.get('name')}")
    check("스트림 done 종료", types[-1] == "done")
    check("tool_call 최소 1회", "tool_call" in types, str(types[:20]))
    check("텍스트 응답 수신", len(text) > 20, text[:120])
    print(f"\n--- 응답 미리보기 ---\n{text[:500]}\n")

    print(f"합계: PASS {PASS} / FAIL {FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--user-id", required=True)
    a = p.parse_args()
    sys.exit(asyncio.run(main(a.user_id)))
```

- [ ] **Step 2: 라이브 실행**

Run: `cd backend && python scripts/coach_live_verify.py --user-id <실존 사용자 UUID>`
Expected: tool 6종 전부 PASS(dict 반환), 스트림에서 `tool_call` ≥ 1회, `done` 종료, 한국어 응답 텍스트. 실패 시 스택트레이스를 읽고 원인 수정 후 재실행 (Windows에서 psycopg 이벤트루프 문제가 나면 Docker 컨테이너에서 실행 — SP-8a에서 확인된 함정).

- [ ] **Step 3: 프론트 연동 확인 (수동)**

Run: 백엔드 `uvicorn` + 프론트 `pnpm run dev` 기동 → `/coach` 접속 → 로그인 → "요즘 뜨는 분야 알려줘" 전송.
Expected: tool 활동 인디케이터("시장 트렌드 조회 중…") 표시 후 스트리밍 응답. 새로고침 시 히스토리 유지.

- [ ] **Step 4: 커밋**

```bash
git add backend/scripts/coach_live_verify.py
git commit -m "test(coach): 라이브 verify — 실 DB tool 6종 + Sonnet tool-calling 스트림 확증"
```

---

## 완료 기준 (스펙 §8 C-1)

1. 코치가 실데이터 근거로 답변 (Task 8 라이브 verify PASS).
2. tool_call 이벤트가 프론트에 표시 (Task 8 Step 3 수동 확인).
3. 단위 테스트 스크립트 5종(coach_llm_resolve · coach_session_models_import · consult_memory_read · coach_tools · coach_graph · coach_endpoint) 전부 PASS + 기존 consult 테스트 회귀 없음.

## 계획에서 의도적으로 뺀 것 (스코프 가드)

- 웹 검색 tool(Tavily/WaterCrawl) → C-2. `launch_roadmap_generation` tool·deepagents → R-1.
- 코치용 자기모델 추출·인사이트 지갑·위젯 렌더 → v2.
- 코치 세션 목록 UI·다중 세션 관리 → 필요해질 때.
