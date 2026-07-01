# 코치 대화 영속화(SP-2a) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 무상태 코치를 명시적 세션 기반 영속 대화(멀티턴 기억 + 롤링 요약)로 전환한다.

**Architecture:** ai_coach 도메인에 `coach_sessions`/`coach_messages` 2테이블. `CoachSessionRepository`(세션·메시지 CRUD), 순수 컨텍스트 조립 헬퍼(`coach_context.py`), `LlmClient.summarize_conversation`, `CoachService` 재작성(스트리밍 중 영속화 + 롤링 요약, 주입 가능한 LLM/summarizer로 테스트), `coach_routor` 4 엔드포인트, 프론트 `CoachView` 세션 라이프사이클.

**Tech Stack:** FastAPI · SQLAlchemy 2.0 async · Alembic · Neon Postgres · SSE(StreamingResponse) · Next.js(프론트). 테스트는 표준 라이브러리 기반 `scripts/*_test.py`.

## Global Constraints

- **테스트 실행** — `cd backend && python scripts/<name>_test.py`. 서버 필요 테스트는 `httpx.ASGITransport`(인프로세스).
- **Alembic** — CLI `alembic`(‘python -m alembic’ 금지). 생성 마이그레이션 검토 후 적용. autogenerate 시 무관 테이블 drift(sectors·sub_sectors·raw_tech_adoption_data·sector_source_map)가 잡히면 **반드시 제거**하고 이 두 테이블만 남긴다.
- **Neon 쓰기 승인** — `alembic upgrade head` 와 Neon insert 테스트는 실행 시 사용자 승인 필요(순수/무DB 테스트는 불필요).
- **스트리밍 DB 세션 함정** — `Depends(get_db)` 세션은 응답 후 닫힘. `StreamingResponse` 제너레이터 내부의 메시지 영속화는 **`AsyncSessionLocal()`로 독립 세션**을 열어 수행한다. 소유권·active 검증은 스트리밍 시작 전 라우트에서 요청 세션으로.
- **파일 헤더** — 새 소스 파일 첫 줄은 한 줄 한국어 주석. 한국어 문장 종결은 `.`/`?`/`!`(‘:’ 금지).
- **UUID** — `coach_sessions.id`는 앱에서 `uuid.uuid4()` 생성(확장 의존 회피).
- **커밋** — 논리 단위마다 semantic commit. `git add .` 금지 — 지정 파일만. 메시지 끝줄 `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
- **테스트 사용자** — Neon 테스트는 `SELECT id FROM users ORDER BY created_at LIMIT 1` 사용자를 재사용, 시작·종료에 그 사용자의 세션/메시지 DELETE로 idempotent.
- **범위** — SP-2a는 영속화·멀티턴·롤링 요약까지. 자기모델 추출(SP-2b)·에이전트화·웹툴은 범위 밖.

---

### Task 1: 코치 세션·메시지 ORM + 마이그레이션

**Files:**
- Create: `backend/domain/ai_coach/models/bases/coach_session.py`
- Create: `backend/domain/ai_coach/models/bases/coach_message.py`
- Modify: `backend/alembic/env.py` (import 2줄, `UserSelfModelEvidence` import 다음)
- Create: `backend/alembic/versions/<autogen>_add_coach_sessions.py`
- Test: `backend/scripts/coach_session_models_import_test.py`

**Interfaces:**
- Produces: ORM `CoachSession`(table `coach_sessions`), `CoachMessage`(table `coach_messages`). 컬럼은 아래 코드 그대로.

- [ ] **Step 1: import 테스트 작성(무DB)**

Create `backend/scripts/coach_session_models_import_test.py`:
```python
# 코치 세션·메시지 ORM import·메타 검증(무DB)

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SCHEDULER_ENABLED", "false")

from domain.ai_coach.models.bases.coach_session import CoachSession
from domain.ai_coach.models.bases.coach_message import CoachMessage

PASS = 0
FAIL = 0


def check(name: str, cond: bool, extra: str = "") -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"[PASS] {name}")
    else:
        FAIL += 1
        print(f"[FAIL] {name} {extra}")


def run() -> int:
    s = CoachSession.__table__
    check("sessions 테이블", s.name == "coach_sessions")
    check("status not null", s.columns["status"].nullable is False)
    check("context_summary nullable", s.columns["context_summary"].nullable is True)
    check("ended_at nullable", s.columns["ended_at"].nullable is True)
    m = CoachMessage.__table__
    check("messages 테이블", m.name == "coach_messages")
    check("role not null", m.columns["role"].nullable is False)
    check("content not null", m.columns["content"].nullable is False)
    check("session 인덱스", any(ix.name == "ix_coach_messages_session" for ix in m.indexes))
    print(f"\n결과: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(run())
```

- [ ] **Step 2: 실패 확인** — Run: `cd backend && python scripts/coach_session_models_import_test.py` → FAIL(ModuleNotFoundError).

- [ ] **Step 3: `coach_session.py` 작성**

Create `backend/domain/ai_coach/models/bases/coach_session.py`:
```python
# 코치 대화 세션 ORM — 명시적 세션(상태·롤링 요약·추출 표시)

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from core.database import Base


class CoachSession(Base):
    __tablename__ = "coach_sessions"
    __table_args__ = (
        Index("ix_coach_sessions_user", "user_id"),
        {"comment": "코치 대화 세션 — 명시적 세션·롤링 요약·추출 표시"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", name="fk_coach_session_user", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(10), nullable=False, server_default="active")
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    title: Mapped[str | None] = mapped_column(String(120), nullable=True)
    context_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    extracted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
```

- [ ] **Step 4: `coach_message.py` 작성**

Create `backend/domain/ai_coach/models/bases/coach_message.py`:
```python
# 코치 대화 메시지 ORM — 세션별 턴(role·content), append-only

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from core.database import Base


class CoachMessage(Base):
    __tablename__ = "coach_messages"
    __table_args__ = (
        Index("ix_coach_messages_session", "session_id", "created_at"),
        {"comment": "코치 대화 메시지 — 세션별 턴(user/assistant)"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("coach_sessions.id", name="fk_coach_message_session", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(10), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
```

- [ ] **Step 5: `alembic/env.py` 모델 등록**

Modify `backend/alembic/env.py` — `UserSelfModelEvidence` import 블록 다음 줄에 추가:
```python
from domain.ai_coach.models.bases.coach_session import CoachSession  # 코치 세션
from domain.ai_coach.models.bases.coach_message import CoachMessage  # 코치 메시지
```

- [ ] **Step 6: import 테스트 통과** — Run: `cd backend && python scripts/coach_session_models_import_test.py` → `PASS=8 FAIL=0`.

- [ ] **Step 7: 마이그레이션 생성** — `cd backend && alembic heads`(단일 head 확인) → `cd backend && alembic revision --autogenerate -m "add coach_sessions and messages"`.

- [ ] **Step 8: 마이그레이션 검토** — `upgrade()`가 `coach_sessions`(id UUID PK, user_id FK CASCADE, status/started_at/created_at, ended_at/title/context_summary/extracted_at nullable, index ix_coach_sessions_user) + `coach_messages`(id BigInteger PK, session_id FK CASCADE, role/content not null, index ix_coach_messages_session) **두 테이블만** 생성하는지 확인. 무관 drift 제거. `downgrade()`는 messages 먼저 drop.

- [ ] **Step 9: Neon 적용(승인 필요)** — `cd backend && alembic upgrade head`. 확인: `to_regclass('public.coach_sessions')`·`coach_messages` non-null.

- [ ] **Step 10: 커밋**
```bash
git add backend/domain/ai_coach/models/bases/coach_session.py backend/domain/ai_coach/models/bases/coach_message.py backend/alembic/env.py backend/alembic/versions/<hash>_add_coach_sessions.py backend/scripts/coach_session_models_import_test.py
git commit -m "feat(coach): 코치 세션·메시지 ORM + 마이그레이션 (SP-2a Task1)"
```

---

### Task 2: CoachSessionRepository

**Files:**
- Create: `backend/domain/ai_coach/hub/repositories/coach_session_repository.py`
- Test: `backend/scripts/coach_session_repository_test.py`

**Interfaces:**
- Consumes: Task 1 테이블.
- Produces: `CoachSessionRepository(session)` with:
  - `async create_session(user_id: str) -> str` (uuid4 생성·insert·반환)
  - `async get_session(session_id: str) -> dict | None` (keys `user_id, status, context_summary`)
  - `async add_message(session_id: str, role: str, content: str) -> None`
  - `async fetch_messages(session_id: str) -> list[dict]` (keys `role, content`, `created_at ASC`)
  - `async count_messages(session_id: str) -> int`
  - `async end_session(session_id: str) -> None`
  - `async update_summary(session_id: str, summary: str) -> None`

- [ ] **Step 1: 리포지토리 Neon 테스트 작성**

Create `backend/scripts/coach_session_repository_test.py`:
```python
# 코치 세션 리포지토리 Neon 라운드트립 — 생성·메시지·히스토리 순서·요약·종료

from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SCHEDULER_ENABLED", "false")

from sqlalchemy import text

from core.database import AsyncSessionLocal
from domain.ai_coach.hub.repositories.coach_session_repository import CoachSessionRepository

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


async def _uid(s) -> str:
    r = (await s.execute(text("SELECT id FROM users ORDER BY created_at LIMIT 1"))).first()
    if r is None:
        raise SystemExit("users 비어있음")
    return str(r.id)


async def _cleanup(s, uid: str) -> None:
    await s.execute(text(
        "DELETE FROM coach_messages WHERE session_id IN "
        "(SELECT id FROM coach_sessions WHERE user_id = CAST(:u AS UUID))"), {"u": uid})
    await s.execute(text("DELETE FROM coach_sessions WHERE user_id = CAST(:u AS UUID)"), {"u": uid})
    await s.commit()


async def run() -> int:
    async with AsyncSessionLocal() as s:
        uid = await _uid(s)
        await _cleanup(s, uid)
        repo = CoachSessionRepository(s)

        sid = await repo.create_session(uid)
        check("세션 생성 uuid", isinstance(sid, str) and len(sid) >= 32, sid)
        sess = await repo.get_session(sid)
        check("소유자 반영", sess and sess["user_id"] == uid, str(sess))
        check("초기 status active", sess and sess["status"] == "active")

        await repo.add_message(sid, "user", "안녕")
        await repo.add_message(sid, "assistant", "반가워요")
        await repo.add_message(sid, "user", "진로 고민이 있어")
        msgs = await repo.fetch_messages(sid)
        check("히스토리 3건 순서", [m["role"] for m in msgs] == ["user", "assistant", "user"], str(msgs))
        check("count 3", await repo.count_messages(sid) == 3)

        await repo.update_summary(sid, "사용자는 진로를 고민 중")
        check("요약 저장", (await repo.get_session(sid))["context_summary"] == "사용자는 진로를 고민 중")

        await repo.end_session(sid)
        check("종료 status ended", (await repo.get_session(sid))["status"] == "ended")

        await _cleanup(s, uid)
    print(f"\n결과: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
```

- [ ] **Step 2: 실패 확인** — Run → FAIL(ModuleNotFoundError).

- [ ] **Step 3: 리포지토리 구현**

Create `backend/domain/ai_coach/hub/repositories/coach_session_repository.py`:
```python
# 코치 세션 리포지토리 — 세션·메시지 CRUD·롤링 요약·종료

from __future__ import annotations

import uuid

from sqlalchemy import text

from domain.auth.hub.repositories.base_repository import BaseRepository

_CREATE = text(
    "INSERT INTO coach_sessions (id, user_id, status, started_at, created_at) "
    "VALUES (CAST(:id AS UUID), CAST(:uid AS UUID), 'active', now(), now())"
)
_GET = text(
    "SELECT user_id, status, context_summary FROM coach_sessions WHERE id = CAST(:id AS UUID)"
)
_ADD_MSG = text(
    "INSERT INTO coach_messages (session_id, role, content, created_at) "
    "VALUES (CAST(:sid AS UUID), :role, :content, now())"
)
_FETCH_MSGS = text(
    "SELECT role, content FROM coach_messages WHERE session_id = CAST(:sid AS UUID) "
    "ORDER BY created_at ASC, id ASC"
)
_COUNT = text("SELECT count(*) AS c FROM coach_messages WHERE session_id = CAST(:sid AS UUID)")
_END = text(
    "UPDATE coach_sessions SET status='ended', ended_at=now() WHERE id = CAST(:id AS UUID)"
)
_UPDATE_SUMMARY = text(
    "UPDATE coach_sessions SET context_summary = :s WHERE id = CAST(:id AS UUID)"
)


class CoachSessionRepository(BaseRepository):
    async def create_session(self, user_id: str) -> str:
        sid = str(uuid.uuid4())
        await self.session.execute(_CREATE, {"id": sid, "uid": user_id})
        await self.session.commit()
        return sid

    async def get_session(self, session_id: str) -> dict | None:
        r = (await self.session.execute(_GET, {"id": session_id})).first()
        if r is None:
            return None
        return {"user_id": str(r.user_id), "status": r.status, "context_summary": r.context_summary}

    async def add_message(self, session_id: str, role: str, content: str) -> None:
        await self.session.execute(_ADD_MSG, {"sid": session_id, "role": role, "content": content})
        await self.session.commit()

    async def fetch_messages(self, session_id: str) -> list[dict]:
        rows = (await self.session.execute(_FETCH_MSGS, {"sid": session_id})).all()
        return [{"role": r.role, "content": r.content} for r in rows]

    async def count_messages(self, session_id: str) -> int:
        return int((await self.session.execute(_COUNT, {"sid": session_id})).first().c)

    async def end_session(self, session_id: str) -> None:
        await self.session.execute(_END, {"id": session_id})
        await self.session.commit()

    async def update_summary(self, session_id: str, summary: str) -> None:
        await self.session.execute(_UPDATE_SUMMARY, {"id": session_id, "s": summary})
        await self.session.commit()
```

- [ ] **Step 4: 테스트 통과(Neon 쓰기 — 승인 필요)** — Run → `PASS=8 FAIL=0`.

- [ ] **Step 5: 커밋**
```bash
git add backend/domain/ai_coach/hub/repositories/coach_session_repository.py backend/scripts/coach_session_repository_test.py
git commit -m "feat(coach): CoachSessionRepository — 세션·메시지·요약·종료 (SP-2a Task2)"
```

---

### Task 3: 순수 컨텍스트 조립 + 롤링 요약 오케스트레이션 + LlmClient.summarize_conversation

**Files:**
- Create: `backend/domain/ai_coach/hub/services/coach_context.py`
- Modify: `backend/core/llm/client.py` (프롬프트 상수 + `summarize_conversation` 메서드)
- Test: `backend/scripts/coach_context_test.py`

**Interfaces:**
- Produces:
  - `select_to_summarize(total: int, window_n: int, threshold_t: int) -> bool` — 요약 트리거 여부(총 메시지 수 > threshold_t).
  - `split_history(messages: list[dict], window_n: int) -> tuple[list[dict], list[dict]]` — `(older, recent)` — 최근 window_n 개를 recent 로.
  - `build_llm_messages(system_content: str, context_summary: str | None, recent: list[dict], user_message: str) -> list[dict]` — LLM messages 배열 조립.
  - `LlmClient.summarize_conversation(prior_summary: str | None, older: list[dict]) -> str`.

- [ ] **Step 1: 순수 헬퍼 테스트 작성(무DB·무LLM)**

Create `backend/scripts/coach_context_test.py`:
```python
# 코치 컨텍스트 조립·롤링 요약 트리거 순수 단위 테스트(무DB·무LLM)

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SCHEDULER_ENABLED", "false")

from domain.ai_coach.hub.services.coach_context import (
    build_llm_messages,
    select_to_summarize,
    split_history,
)

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
    check("임계 이하 미트리거", select_to_summarize(24, 20, 24) is False)
    check("임계 초과 트리거", select_to_summarize(25, 20, 24) is True)

    msgs = [{"role": "user", "content": str(i)} for i in range(25)]
    older, recent = split_history(msgs, 20)
    check("older 5건", len(older) == 5)
    check("recent 20건", len(recent) == 20)
    check("recent 끝 유지", recent[-1]["content"] == "24")

    # 짧은 대화 — 요약 없음, 전체 주입
    out = build_llm_messages("SYS", None, [{"role": "user", "content": "안녕"}], "새 질문")
    check("system 선두", out[0] == {"role": "system", "content": "SYS"})
    check("요약없으면 요약블록 없음", all("[이전 대화 요약]" not in m["content"] for m in out))
    check("마지막 user 메시지", out[-1] == {"role": "user", "content": "새 질문"})

    # 요약 있음 — 요약 블록이 system 다음, recent 앞
    out2 = build_llm_messages("SYS", "사용자는 진로 고민 중", [{"role": "assistant", "content": "직전 답"}], "다음")
    check("요약 블록 포함", any("[이전 대화 요약]" in m["content"] and "진로 고민" in m["content"] for m in out2))
    check("recent 포함", any(m["content"] == "직전 답" for m in out2))

    print(f"\n결과: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(run())
```

- [ ] **Step 2: 실패 확인** — Run → FAIL(ModuleNotFoundError).

- [ ] **Step 3: `coach_context.py` 작성**

Create `backend/domain/ai_coach/hub/services/coach_context.py`:
```python
# 코치 LLM 컨텍스트 조립·롤링 요약 트리거 — 순수 함수(무네트워크)


def select_to_summarize(total: int, window_n: int, threshold_t: int) -> bool:
    """총 메시지 수가 임계 초과면 오래된 메시지를 요약해야 한다."""
    return total > threshold_t


def split_history(messages: list[dict], window_n: int) -> tuple[list[dict], list[dict]]:
    """(older, recent) — 최근 window_n 개를 recent 로, 그 앞을 older 로 분리."""
    if window_n <= 0:
        return messages, []
    return messages[:-window_n], messages[-window_n:]


def build_llm_messages(
    system_content: str,
    context_summary: str | None,
    recent: list[dict],
    user_message: str,
) -> list[dict]:
    """LLM messages 배열 조립 — [system + (요약블록) + recent + 현재 user]."""
    out: list[dict] = [{"role": "system", "content": system_content}]
    if context_summary:
        out.append({"role": "system", "content": f"[이전 대화 요약]\n{context_summary}"})
    for m in recent:
        role = m.get("role")
        content = m.get("content")
        if role in ("user", "assistant") and content:
            out.append({"role": role, "content": content})
    out.append({"role": "user", "content": user_message})
    return out
```

- [ ] **Step 4: 순수 테스트 통과** — Run: `cd backend && python scripts/coach_context_test.py` → `PASS=10 FAIL=0`.

- [ ] **Step 5: `LlmClient.summarize_conversation` 추가**

Modify `backend/core/llm/client.py` — `_COACH_SYSTEM_PROMPT` 정의 다음에 상수 추가:
```python
_COACH_SUMMARY_SYSTEM_PROMPT = (
    "너는 코치와 사용자의 대화를 압축하는 요약기다. 이전 요약과 새 대화를 받아, "
    "사용자에 대한 핵심 사실(관심·성향·상황·목표), 대화의 의도, 합의된 것, 다음 스텝을 "
    "한국어로 간결히 통합 요약하라. 새 정보로 기존 요약을 갱신하되 중요한 과거 맥락은 유지하라. "
    "8문장 이내 평문으로만 출력하라(JSON·머리말 없이)."
)
```
그리고 `stream_chat` 메서드 다음에 메서드 추가:
```python
    async def summarize_conversation(self, prior_summary: str | None, older: list[dict]) -> str:
        """이전 요약 + 오래된 대화를 통합 롤링 요약(평문)으로 압축한다."""
        convo = "\n".join(
            f"{m.get('role')}: {m.get('content')}" for m in older
            if m.get("role") in ("user", "assistant") and m.get("content")
        )
        user = (f"[기존 요약]\n{prior_summary}\n\n" if prior_summary else "") + f"[새 대화]\n{convo}"
        resp = await self._client.chat.completions.create(
            model=self._model,
            temperature=0.2,
            messages=[
                {"role": "system", "content": _COACH_SUMMARY_SYSTEM_PROMPT},
                {"role": "user", "content": user},
            ],
        )
        return (resp.choices[0].message.content or "").strip()
```

- [ ] **Step 6: 회귀 확인(무DB)** — Run: `cd backend && python scripts/coach_context_test.py` → `PASS=10 FAIL=0` (client 변경이 순수 테스트를 깨지 않음). `python -c "import core.llm.client"` 로 import 오류 없음 확인.

- [ ] **Step 7: 커밋**
```bash
git add backend/domain/ai_coach/hub/services/coach_context.py backend/core/llm/client.py backend/scripts/coach_context_test.py
git commit -m "feat(coach): 컨텍스트 조립·롤링 요약 순수 헬퍼 + summarize_conversation (SP-2a Task3)"
```

---

### Task 4: CoachService 재작성 (세션 CRUD + 스트리밍 영속화 + 롤링 요약)

**Files:**
- Modify: `backend/domain/ai_coach/hub/services/coach_service.py`
- Test: `backend/scripts/coach_service_test.py`

**Interfaces:**
- Consumes: Task 2 `CoachSessionRepository`, Task 3 `coach_context`·`LlmClient.summarize_conversation`, 기존 `CoachRepository`(맥락)·`build_coach_context`·`_COACH_SYSTEM_PROMPT`.
- Produces: `CoachService(session)` with:
  - `async create_session(user_id) -> str`
  - `async verify_owner(user_id, session_id) -> str` (소유·존재 검증 — 반환 status; 미존재 `LookupError`, 타인 `PermissionError`)
  - `async get_messages(user_id, session_id) -> list[dict]`
  - `async end_session(user_id, session_id) -> None`
  - `def stream_sse(user_id, session_id, message)` (async generator; 소유권은 라우트에서 검증 후 호출)
- 테스트 주입점: `stream_sse`가 사용할 요약/스트림을 위해 `CoachService`는 `_summarizer`·`_streamer` 를 인스턴스 속성으로 두고 기본은 `LlmClient` 기반. 테스트는 이를 fake 로 대체.

- [ ] **Step 1: 서비스 테스트 작성(Neon + fake LLM)**

Create `backend/scripts/coach_service_test.py`:
```python
# CoachService — 스트리밍 영속화·롤링 요약(fake LLM)·소유권. Neon 라운드트립.

from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SCHEDULER_ENABLED", "false")

from sqlalchemy import text

from core.database import AsyncSessionLocal
from domain.ai_coach.hub.repositories.coach_session_repository import CoachSessionRepository
from domain.ai_coach.hub.services.coach_service import CoachService

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


async def _uid(s) -> str:
    r = (await s.execute(text("SELECT id FROM users ORDER BY created_at LIMIT 1"))).first()
    if r is None:
        raise SystemExit("users 비어있음")
    return str(r.id)


async def _cleanup(s, uid: str) -> None:
    await s.execute(text(
        "DELETE FROM coach_messages WHERE session_id IN "
        "(SELECT id FROM coach_sessions WHERE user_id = CAST(:u AS UUID))"), {"u": uid})
    await s.execute(text("DELETE FROM coach_sessions WHERE user_id = CAST(:u AS UUID)"), {"u": uid})
    await s.commit()


async def _drain(gen) -> str:
    out = ""
    async for evt in gen:
        out += evt
    return out


async def run() -> int:
    async with AsyncSessionLocal() as s:
        uid = await _uid(s)
        await _cleanup(s, uid)
        svc = CoachService(s)

        # fake 주입 — 스트림은 고정 토큰, 요약은 고정 문자열
        async def fake_streamer(messages):
            for tok in ["안", "녕", "하세요"]:
                yield tok

        async def fake_summarizer(prior, older):
            return f"요약({len(older)}건)"

        svc._streamer = fake_streamer
        svc._summarizer = fake_summarizer

        sid = await svc.create_session(uid)
        # 스트림 1회 — 사용자+어시스턴트 저장
        await _drain(svc.stream_sse(uid, sid, "안녕"))
        async with AsyncSessionLocal() as s2:
            msgs = await CoachSessionRepository(s2).fetch_messages(sid)
        check("user+assistant 저장", [m["role"] for m in msgs] == ["user", "assistant"], str(msgs))
        check("assistant 누적 저장", msgs[1]["content"] == "안녕하세요", msgs[1]["content"])

        # 소유권 — 타인 uuid
        import uuid as _u
        try:
            await svc.verify_owner(str(_u.uuid4()), sid)
            check("타인 접근 거부", False, "no raise")
        except PermissionError:
            check("타인 접근 PermissionError", True)

        # 롤링 요약 — 임계(24)까지 채운 뒤 스트림 → 요약 생성
        async with AsyncSessionLocal() as s3:
            repo = CoachSessionRepository(s3)
            for i in range(24):
                await repo.add_message(sid, "user" if i % 2 == 0 else "assistant", f"m{i}")
        await _drain(svc.stream_sse(uid, sid, "요약 트리거"))
        async with AsyncSessionLocal() as s4:
            sess = await CoachSessionRepository(s4).get_session(sid)
        check("롤링 요약 생성", bool(sess["context_summary"]) and sess["context_summary"].startswith("요약("), str(sess["context_summary"]))

        await svc.end_session(uid, sid)
        async with AsyncSessionLocal() as s5:
            check("종료 반영", (await CoachSessionRepository(s5).get_session(sid))["status"] == "ended")

        await _cleanup(s, uid)
    print(f"\n결과: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
```

- [ ] **Step 2: 실패 확인** — Run → FAIL(AttributeError/시그니처 불일치).

- [ ] **Step 3: `coach_service.py` 재작성**

Replace `backend/domain/ai_coach/hub/services/coach_service.py` 전체:
```python
# AI 코치 서비스 — 세션 영속·멀티턴·롤링 요약 + 맥락 주입 LLM SSE 스트리밍

from __future__ import annotations

import json

from sqlalchemy.ext.asyncio import AsyncSession

from core.config.settings import get_settings
from core.database import AsyncSessionLocal
from core.llm.client import _COACH_SYSTEM_PROMPT, LlmClient
from domain.ai_coach.hub.repositories.coach_repository import CoachRepository
from domain.ai_coach.hub.repositories.coach_session_repository import CoachSessionRepository
from domain.ai_coach.hub.services import coach_context

_WINDOW_N = 20
_THRESHOLD_T = 24


def build_coach_context(ctx: dict) -> str:
    """맥락 dict → 시스템 프롬프트에 붙일 맥락 문자열. 무네트워크 순수 함수."""
    persona = ctx.get("persona") or {}
    roadmap = ctx.get("roadmap")
    quests = ctx.get("quests") or []
    movers = ctx.get("movers") or []
    parts = ["[사용자 맥락]"]
    skills = [s.get("name") for s in (persona.get("skills") or []) if s.get("name")]
    parts.append(f"- 보유 스킬: {', '.join(skills) if skills else '미입력'}")
    if persona.get("summary"):
        parts.append(f"- 요약: {persona['summary']}")
    if roadmap:
        parts.append(f"- 로드맵: {roadmap.get('title')}")
    if quests:
        parts.append("- 진행 중/예정 퀘스트: " + ", ".join(q.get("title") for q in quests))
    if movers:
        parts.append("- 시장 상위 섹터: " + ", ".join(m.get("sector_slug") for m in movers))
    return "\n".join(parts)


def _sse(obj: dict) -> str:
    """SSE 이벤트 1건(JSON data) 직렬화."""
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


class CoachService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = CoachRepository(session)
        settings = get_settings()
        self._model = settings.llm_classify_model
        self._api_key = settings.openai_api_key
        # 주입점(테스트 대체 가능). 기본은 실제 LLM.
        self._streamer = self._default_streamer
        self._summarizer = self._default_summarizer

    async def _default_streamer(self, messages: list[dict]):
        llm = LlmClient(api_key=self._api_key, model=self._model)
        async for delta in llm.stream_chat(messages):
            yield delta

    async def _default_summarizer(self, prior_summary, older):
        llm = LlmClient(api_key=self._api_key, model=self._model)
        return await llm.summarize_conversation(prior_summary, older)

    async def create_session(self, user_id: str) -> str:
        return await CoachSessionRepository(self.session).create_session(user_id)

    async def verify_owner(self, user_id: str, session_id: str) -> str:
        """세션 소유·존재 검증. 반환 status. 미존재 LookupError, 타인 PermissionError."""
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

    async def _maybe_summarize(self, session_id: str) -> str | None:
        """임계 초과면 오래된 메시지를 롤링 요약해 저장하고, 현재 요약을 반환한다. 독립 세션 사용."""
        async with AsyncSessionLocal() as db:
            repo = CoachSessionRepository(db)
            sess = await repo.get_session(session_id)
            prior = sess["context_summary"] if sess else None
            total = await repo.count_messages(session_id)
            if not coach_context.select_to_summarize(total, _WINDOW_N, _THRESHOLD_T):
                return prior
            msgs = await repo.fetch_messages(session_id)
            older, _recent = coach_context.split_history(msgs, _WINDOW_N)
            if not older:
                return prior
            summary = await self._summarizer(prior, older)
            if summary:
                await repo.update_summary(session_id, summary)
            return summary or prior

    async def stream_sse(self, user_id: str, session_id: str, message: str):
        """사용자 메시지 저장 → 히스토리+요약+맥락 주입 스트리밍 → 어시스턴트 응답 저장(독립 세션)."""
        # 1) 사용자 메시지 저장(독립 세션 — 스트리밍 중 요청 세션 수명 회피).
        async with AsyncSessionLocal() as db:
            await CoachSessionRepository(db).add_message(session_id, "user", message)

        # 2) 롤링 요약(임계 초과 시) + 최근 윈도우 로드.
        summary = await self._maybe_summarize(session_id)
        async with AsyncSessionLocal() as db:
            all_msgs = await CoachSessionRepository(db).fetch_messages(session_id)
        # 방금 저장한 현재 user 메시지는 message 로 별도 주입하므로 히스토리에서 제외.
        history = all_msgs[:-1] if all_msgs and all_msgs[-1]["role"] == "user" else all_msgs
        _older, recent = coach_context.split_history(history, _WINDOW_N)

        # 3) 맥락.
        try:
            ctx = await self.repo.fetch_context(user_id)
            context_str = build_coach_context(ctx)
        except Exception:
            context_str = ""
        system_content = _COACH_SYSTEM_PROMPT + ("\n\n" + context_str if context_str else "")

        if not self._api_key:
            yield _sse({"type": "delta", "content": "현재 AI 코치가 비활성화되어 있습니다(API 키 미설정)."})
            yield _sse({"type": "done"})
            return

        messages = coach_context.build_llm_messages(system_content, summary, recent, message)

        # 4) 스트리밍 + 누적.
        acc = ""
        try:
            async for delta in self._streamer(messages):
                acc += delta
                yield _sse({"type": "delta", "content": delta})
        except Exception as e:  # 스트림 도중 실패 — 에러 이벤트로 알린다.
            yield _sse({"type": "error", "message": str(e)})

        # 5) 어시스턴트 응답 저장(내용 있으면).
        if acc:
            async with AsyncSessionLocal() as db:
                await CoachSessionRepository(db).add_message(session_id, "assistant", acc)
        yield _sse({"type": "done"})
```

- [ ] **Step 4: 서비스 테스트 통과(Neon — 승인 필요)** — Run: `cd backend && python scripts/coach_service_test.py` → `PASS=8 FAIL=0`.

- [ ] **Step 5: 커밋**
```bash
git add backend/domain/ai_coach/hub/services/coach_service.py backend/scripts/coach_service_test.py
git commit -m "feat(coach): CoachService 세션 영속·스트리밍 저장·롤링 요약 (SP-2a Task4)"
```

---

### Task 5: 코치 세션 API (coach_routor 4 엔드포인트)

**Files:**
- Modify: `backend/api/v1/coach/coach_routor.py`
- Test: `backend/scripts/coach_endpoint_test.py`

**Interfaces:**
- Consumes: Task 4 `CoachService`.
- Produces: `POST /api/coach/sessions`, `POST /api/coach/stream`(sessionId+message), `POST /api/coach/sessions/{id}/end`, `GET /api/coach/sessions/{id}/messages`. 소유권 403·미존재 404·무토큰 401.

- [ ] **Step 1: 엔드포인트 테스트 작성**

Create `backend/scripts/coach_endpoint_test.py`:
```python
# 코치 세션 엔드포인트 — 생성·스트림(무키 경로)·messages·end·소유권 403/404·무토큰 401

from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SCHEDULER_ENABLED", "false")

import httpx
from sqlalchemy import text

from core.database import AsyncSessionLocal
from domain.auth.hub.security.services.jwt import JWTService

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


async def _uid(s) -> str:
    r = (await s.execute(text("SELECT id FROM users ORDER BY created_at LIMIT 1"))).first()
    if r is None:
        raise SystemExit("users 비어있음")
    return str(r.id)


async def _cleanup(s, uid: str) -> None:
    await s.execute(text(
        "DELETE FROM coach_messages WHERE session_id IN "
        "(SELECT id FROM coach_sessions WHERE user_id = CAST(:u AS UUID))"), {"u": uid})
    await s.execute(text("DELETE FROM coach_sessions WHERE user_id = CAST(:u AS UUID)"), {"u": uid})
    await s.commit()


async def run() -> int:
    from main import app

    async with AsyncSessionLocal() as s:
        uid = await _uid(s)
        await _cleanup(s, uid)

    token = JWTService().generate_token(uid, provider="test", email="coach@test.local")
    h = {"Authorization": f"Bearer {token}"}
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post("/api/coach/sessions", headers=h)
        check("세션 생성 200", r.status_code == 200, str(r.status_code))
        sid = r.json().get("sessionId")
        check("sessionId 반환", bool(sid))

        # 스트림(무키 경로면 비활성 메시지 — 사용자 메시지는 저장됨)
        r = await c.post("/api/coach/stream", headers=h, json={"sessionId": sid, "message": "안녕"})
        check("스트림 200", r.status_code == 200, str(r.status_code))

        r = await c.get(f"/api/coach/sessions/{sid}/messages", headers=h)
        check("messages 200", r.status_code == 200)
        roles = [m["role"] for m in r.json().get("messages", [])]
        check("user 메시지 저장", "user" in roles, str(roles))

        # 소유권 — 타인 토큰
        other = JWTService().generate_token("00000000-0000-0000-0000-000000000000", provider="test", email="x@test.local")
        r = await c.get(f"/api/coach/sessions/{sid}/messages", headers={"Authorization": f"Bearer {other}"})
        check("타인 403", r.status_code == 403, str(r.status_code))

        # 미존재 404
        r = await c.get("/api/coach/sessions/11111111-1111-1111-1111-111111111111/messages", headers=h)
        check("미존재 404", r.status_code == 404, str(r.status_code))

        # 종료
        r = await c.post(f"/api/coach/sessions/{sid}/end", headers=h)
        check("end 200", r.status_code == 200)

        # 무토큰 401
        r = await c.post("/api/coach/sessions")
        check("무토큰 401", r.status_code == 401, str(r.status_code))

    async with AsyncSessionLocal() as s:
        await _cleanup(s, uid)
    print(f"\n결과: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
```

- [ ] **Step 2: 실패 확인** — Run → FAIL(404 on /sessions).

- [ ] **Step 3: `coach_routor.py` 재작성**

Replace `backend/api/v1/coach/coach_routor.py` 전체:
```python
# AI 코치 HTTP 라우터 — 세션 생성·영속 스트리밍·종료·히스토리

import logging

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
    sessionId: str
    message: str


@router.post("/sessions")
async def create_session(
    user_id: str = Depends(get_authenticated_user_id),
    db: AsyncSession = Depends(get_db),
):
    """새 코치 대화 세션 생성."""
    session_id = await CoachService(db).create_session(user_id)
    return {"success": True, "sessionId": session_id}


@router.post("/stream")
async def coach_stream(
    request: CoachStreamRequest,
    user_id: str = Depends(get_authenticated_user_id),
    db: AsyncSession = Depends(get_db),
):
    """세션 소유권 검증 후 사용자 메시지+맥락 주입 LLM 응답 SSE 스트리밍."""
    svc = CoachService(db)
    try:
        status = await svc.verify_owner(user_id, request.sessionId)
    except LookupError:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")
    except PermissionError:
        raise HTTPException(status_code=403, detail="세션 접근 권한이 없습니다.")
    if status == "ended":
        raise HTTPException(status_code=409, detail="종료된 세션입니다.")
    generator = svc.stream_sse(user_id, request.sessionId, request.message)
    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/sessions/{session_id}/end")
async def end_session(
    session_id: str,
    user_id: str = Depends(get_authenticated_user_id),
    db: AsyncSession = Depends(get_db),
):
    """세션 종료(소유권 검증). 이미 종료면 멱등."""
    try:
        await CoachService(db).end_session(user_id, session_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")
    except PermissionError:
        raise HTTPException(status_code=403, detail="세션 접근 권한이 없습니다.")
    return {"success": True}


@router.get("/sessions/{session_id}/messages")
async def get_messages(
    session_id: str,
    user_id: str = Depends(get_authenticated_user_id),
    db: AsyncSession = Depends(get_db),
):
    """세션 대화 히스토리(소유권 검증)."""
    try:
        messages = await CoachService(db).get_messages(user_id, session_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")
    except PermissionError:
        raise HTTPException(status_code=403, detail="세션 접근 권한이 없습니다.")
    return {"success": True, "messages": messages}
```

- [ ] **Step 4: 테스트 통과(Neon — 승인 필요)** — Run: `cd backend && python scripts/coach_endpoint_test.py` → `PASS=9 FAIL=0`.

- [ ] **Step 5: 커밋**
```bash
git add backend/api/v1/coach/coach_routor.py backend/scripts/coach_endpoint_test.py
git commit -m "feat(coach): 세션 생성·영속 스트림·종료·히스토리 API (SP-2a Task5)"
```

---

### Task 6: 프론트 — CoachView 세션 라이프사이클

**Files:**
- Modify: `www.yeotaeho.kr/src/lib/api/coach.ts`
- Modify: `www.yeotaeho.kr/src/components/features/coach/CoachView.tsx`

**Interfaces:**
- Consumes: Task 5 API.
- Produces: `createCoachSession()`·`endCoachSession(id)`·`fetchCoachMessages(id)`·`streamCoach(sessionId, message, onDelta, signal)`.

- [ ] **Step 1: `coach.ts` 확장**

Modify `www.yeotaeho.kr/src/lib/api/coach.ts` — 파일 상단 import 아래에 API 함수 추가하고 `streamCoach` 시그니처에 `sessionId` 추가:
```typescript
export interface CoachMessage {
  role: 'user' | 'assistant';
  content: string;
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

export async function fetchCoachMessages(sessionId: string): Promise<CoachMessage[]> {
  const token = getStore().getState().token;
  const res = await fetch(`${API_BASE_URL}/api/coach/sessions/${sessionId}/messages`, {
    headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    credentials: 'include',
  });
  if (!res.ok) return [];
  const data = await res.json();
  return data?.messages ?? [];
}

export async function endCoachSession(sessionId: string): Promise<void> {
  const token = getStore().getState().token;
  await fetch(`${API_BASE_URL}/api/coach/sessions/${sessionId}/end`, {
    method: 'POST',
    headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    credentials: 'include',
  }).catch(() => {});
}
```
그리고 `streamCoach` 의 시그니처와 body 를 수정:
```typescript
export async function streamCoach(
  sessionId: string,
  message: string,
  onDelta: (text: string) => void,
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
  // 이하 기존 ReadableStream 파싱 로직 동일.
```
(파싱 루프 본문은 기존 그대로 유지 — `sessionId` 인자와 body 만 추가.)

- [ ] **Step 2: `CoachView.tsx` 세션 배선**

`CoachView`에서: (1) 컴포넌트 마운트 시(로그인 상태) `createCoachSession()` 호출해 `sessionId` state 보관, `fetchCoachMessages`로 기존 히스토리 로드. (2) 전송 핸들러가 `streamCoach(sessionId, message, onDelta, signal)` 호출. (3) 언마운트 `useEffect` cleanup에서 `endCoachSession(sessionId)` 호출. 기존 로컬 mock 대화 상태를 서버 히스토리로 대체. 비로그인 시 세션 생성 스킵(기존 안내 유지).
정확한 편집은 `CoachView.tsx` 현재 구조를 읽고 mock 대화 배열을 `messages` state(초기 = 히스토리)로, 전송을 `streamCoach(sessionId, ...)`로 교체. `sessionId`가 없으면(비로그인/생성 실패) 전송 비활성.

- [ ] **Step 3: 타입 체크** — Run: `cd www.yeotaeho.kr && npx tsc --noEmit` → EXIT 0.

- [ ] **Step 4: 커밋**
```bash
git add www.yeotaeho.kr/src/lib/api/coach.ts www.yeotaeho.kr/src/components/features/coach/CoachView.tsx
git commit -m "feat(coach): CoachView 세션 라이프사이클·히스토리 로드 (SP-2a Task6)"
```

---

## 마무리(전 태스크 완료 후)

- [ ] **전체 회귀** — `cd backend && python scripts/coach_session_models_import_test.py && python scripts/coach_context_test.py && python scripts/coach_session_repository_test.py && python scripts/coach_service_test.py && python scripts/coach_endpoint_test.py` 전부 PASS. 프론트 `tsc` 0.
- [ ] **감사 기록** — `backend/domain/ai_coach/docs/audit_trail.md` 최상단에 SP-2a 항목(경로 승인 후).
- [ ] **Codex 리뷰** — 브랜치 범위. Critical/Important 조치 후 재리뷰.
- [ ] **다음 SP** — SP-2b(세션 종료 후 자기모델 추출): `ended` + `extracted_at IS NULL` 세션 스캔 → 대화 전문 LLM 추출 → `SelfModelService.upsert_structured`/`append_evidence(source='coach_extraction')` → `extracted_at` 기록. 별도 spec/plan.

## Self-Review (플랜 작성자 체크)

- **스펙 커버리지** — spec §3(2테이블)=T1, §4(4 API)=T5, §5(멀티턴+롤링요약)=T3(순수)+T4(오케스트레이션), §6(스트리밍 DB 세션 함정)=T4(모든 쓰기 `AsyncSessionLocal`), §7(프론트)=T6, §8 성공기준 1=T1·2/3/4=T4·T5·T2·5(롤링요약)=T3/T4·6(tsc)=T6, §9 테스트=각 태스크. 커버 갭 없음.
- **플레이스홀더** — T6 Step 2는 기존 파일 구조 의존이라 서술형(현재 `CoachView.tsx`를 읽고 교체) — 코드 전량 대신 정확한 교체 지침. 그 외 전부 실제 코드·명령·기대값.
- **타입 일관성** — 리포지토리 반환 키(`user_id, status, context_summary` / `role, content`)가 T2 정의·T4 서비스 소비에서 일치. `coach_context` 3함수 시그니처가 T3 정의·테스트·T4 호출에서 일치. `verify_owner`의 `LookupError`/`PermissionError`가 T4 정의·T5 라우트 처리에서 일치. `streamCoach(sessionId, message, onDelta, signal)`가 T6 정의·CoachView 호출에서 일치.
