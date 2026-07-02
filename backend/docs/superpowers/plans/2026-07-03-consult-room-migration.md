# 상담실 이전 (coach → consult / user_intelligence) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 코치 대화·세션·자기모델 추출 엔진을 `ai_coach` → `user_intelligence` 도메인으로 이전·전수 개명(coach→consult, 테이블 포함)하고, `/consult`(AI 상담실)를 실엔진으로 교체하며, 상담 맥락에서 로드맵 로직을 제거한다.

**Architecture:** 스펙 `backend/docs/superpowers/specs/2026-07-03-consult-room-migration-design.md` 기준. 3태스크 — (1) 백엔드 원자적 이동·개명(모델·리포·서비스·라우터·스케줄러·마이그레이션·테스트, 동작 불변), (2) 로드맵 제거 + 상담사 프롬프트(동작 변경), (3) 프론트(consult 실엔진·coach 플레이스홀더). 이동은 임포트 그래프가 결합돼 있어 백엔드 이동을 한 원자 태스크로 묶는다.

**Tech Stack:** FastAPI · SQLAlchemy 2.0 async(text SQL) · Alembic(수기 rename 마이그레이션) · PostgreSQL(Neon) · OpenAI SSE · Next.js/TS.

## Global Constraints

- 한국어 문장 종결은 `.` `?` `!` 만 — `:` 로 끝내지 않는다.
- 새 소스 파일 첫 줄은 한 줄 한국어 역할 주석.
- 커밋은 논리 단위별. `git add .` 금지 — 파일 명시, `.omc/`·`.superpowers/`·`__pycache__` 제외.
- 커밋 메시지 끝에 `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>` 트레일러.
- Alembic 은 `backend/` 에서 `alembic` CLI 직접 실행(`python -m alembic` 아님). **`alembic upgrade head`(Neon 반영)는 사용자 승인 후에만 실행.** 현재 head 는 `a6af4387ed37`.
- 마이그레이션은 **수기 작성**(autogenerate 는 rename 을 drop+add 로 오탐). rename 은 데이터 보존.
- 백엔드 테스트는 `backend/scripts/*_test.py` 관행(PASS/FAIL check 함수, `python scripts/<name>_test.py`, exit code). 통합 테스트는 dev Neon 을 쓰므로 시드는 반드시 cleanup.
- 프론트 검증은 `www.yeotaeho.kr` 에서 `pnpm exec tsc --noEmit` 0 에러.
- `ai_coach` 도메인 폴더는 삭제하지 않고 빈 스캐폴딩(`__init__.py`·빈 hub/models/spokes)으로 보존 — 향후 로드맵 코치용.
- 상담 맥락(`build_consult_context` 출력)에 "로드맵"·"퀘스트" 문자열이 남지 않아야 한다.

---

### Task 1: 백엔드 원자적 이동·개명 (동작 불변)

**목표**: coach→consult 전수 개명 + ai_coach→user_intelligence 이동. **동작은 완전 동일**(로드맵 맥락 이 태스크에서는 그대로 유지 — 제거는 Task 2). 이동은 임포트 그래프가 결합돼 한 커밋으로 원자 처리한다.

**Files (이동·개명):**
- Move: `domain/ai_coach/models/bases/coach_session.py` → `domain/user_intelligence/models/bases/consult_session.py`
- Move: `domain/ai_coach/models/bases/coach_message.py` → `domain/user_intelligence/models/bases/consult_message.py`
- Move: `domain/ai_coach/hub/repositories/coach_session_repository.py` → `domain/user_intelligence/hub/repositories/consult_session_repository.py`
- Move: `domain/ai_coach/hub/repositories/coach_repository.py` → `domain/user_intelligence/hub/repositories/consult_context_repository.py`
- Move: `domain/ai_coach/hub/services/coach_context.py` → `domain/user_intelligence/hub/services/consult_context.py`
- Move: `domain/ai_coach/hub/services/coach_service.py` → `domain/user_intelligence/hub/services/consult_service.py`
- Move: `domain/ai_coach/hub/services/self_model_extraction_service.py` → `domain/user_intelligence/hub/services/self_model_extraction_service.py`
- Move: `api/v1/coach/coach_routor.py` → `api/v1/consult/consult_routor.py` (+ `api/v1/consult/__init__.py` 생성)
- Modify: `main.py`, `core/scheduler.py`, `alembic/env.py`
- Create: `alembic/versions/<autogen-id>_rename_coach_to_consult.py`
- Move(테스트): `scripts/coach_context_test.py`→`consult_context_test.py`, `coach_service_test.py`→`consult_service_test.py`, `coach_session_repository_test.py`→`consult_session_repository_test.py`, `coach_session_models_import_test.py`→`consult_session_models_import_test.py`, `coach_stream_test.py`→`consult_stream_test.py`, `coach_extract_repo_test.py`→`consult_extract_repo_test.py`
- Modify(테스트): `scripts/self_model_extraction_test.py`, `scripts/self_model_extract_job_test.py` (임포트 경로만)
- Modify: `domain/user_intelligence/models/bases/user_self_model_evidence.py` (`coach_session_ref`→`consult_session_ref`)
- Modify: `domain/user_intelligence/hub/services/self_model_service.py` (`SOURCE_COACH="consult_extraction"`)
- Modify: `backend/docs/erd.md` §6.6

**Interfaces (개명 후 — Task 2·3 이 참조):**
- `ConsultSession`(테이블 `consult_sessions`) · `ConsultMessage`(테이블 `consult_messages`) — 컬럼 불변.
- `ConsultSessionRepository` — 메서드 시그니처 불변: `create_session(user_id)→str`, `get_session(session_id)→dict|None`, `add_message(session_id, role, content)`, `fetch_messages(session_id)→list[dict]`, `count_messages(session_id)→int`, `end_session(session_id)`, `update_summary(session_id, summary, until)`, `get_latest_active_session(user_id)→str|None`, `update_extracted(session_id, until)`, `fetch_extractable_sessions(min_new, limit)→list[dict]`.
- `ConsultContextRepository.fetch_context(user_id)→dict` — Task 1 에서는 반환 `{persona, roadmap, quests, movers}` 유지(불변).
- `ConsultService` — `CoachService` 와 동일 메서드. 순수 함수 `build_consult_context(ctx)→str`(현 `build_coach_context` 개명, Task 1 에서는 로드맵 주입 유지).
- `consult_context` 모듈 — `select_to_summarize`·`split_history`·`build_llm_messages` 불변.
- API — `/api/consult/sessions`·`/api/consult/stream`·`/api/consult/sessions/{id}/end`·`/api/consult/sessions/{id}/messages`.

- [ ] **Step 1: 모델 2개 이동·개명**

`domain/user_intelligence/models/bases/consult_session.py` 생성(첫 줄 주석 `# 상담 대화 세션 ORM — 명시적 세션·롤링 요약·추출 표시`). 기존 `coach_session.py` 내용에서 클래스 `CoachSession`→`ConsultSession`, `__tablename__="consult_sessions"`, `Index("ix_consult_sessions_user", "user_id")`, FK `name="fk_consult_session_user"`, comment `"상담 대화 세션 — 명시적 세션·롤링 요약·추출 표시"`. 나머지 컬럼 동일.

`domain/user_intelligence/models/bases/consult_message.py` 생성(첫 줄 `# 상담 대화 메시지 ORM — role·content append-only`). `CoachMessage`→`ConsultMessage`, `__tablename__="consult_messages"`, `Index("ix_consult_messages_session", "session_id", "created_at")`, FK `ForeignKey("consult_sessions.id", name="fk_consult_message_session", ondelete="CASCADE")`.

기존 `domain/ai_coach/models/bases/coach_session.py`·`coach_message.py` 삭제.

- [ ] **Step 2: 세션 리포 이동·개명**

`domain/user_intelligence/hub/repositories/consult_session_repository.py` 생성. 기존 `coach_session_repository.py` 내용을 옮기되: 첫 줄 주석 `# 상담 세션 리포지토리 — CRUD·재개·요약 갱신·추출 대상 조회`, 클래스 `CoachSessionRepository`→`ConsultSessionRepository`, 모델 임포트 `from domain.user_intelligence.models.bases.consult_session import ConsultSession`·`consult_message import ConsultMessage`, SQL 문자열의 `coach_sessions`→`consult_sessions`·`coach_messages`→`consult_messages`. 메서드 시그니처·로직 불변. 기존 파일 삭제.

- [ ] **Step 3: 맥락 리포 이동·개명 (로직 불변)**

`domain/user_intelligence/hub/repositories/consult_context_repository.py` 생성. 기존 `coach_repository.py` 내용 그대로, 첫 줄 `# 상담 맥락 리포지토리 — 페르소나·활성 로드맵·상위 Pulse 섹터 읽기(공유 DB read)`, 클래스 `CoachRepository`→`ConsultContextRepository`. **로드맵 쿼리·반환 이 태스크에서는 유지**(Task 2 에서 제거). 기존 파일 삭제.

- [ ] **Step 4: 서비스·순수헬퍼 이동·개명**

`domain/user_intelligence/hub/services/consult_context.py` 생성 — 기존 `coach_context.py` 내용 그대로(순수 헬퍼), 첫 줄 `# 상담 대화 컨텍스트 순수 헬퍼 — 윈도우 분할·주입 메시지 조립`. 기존 삭제.

`domain/user_intelligence/hub/services/consult_service.py` 생성 — 기존 `coach_service.py` 내용에서: 첫 줄 `# AI 상담 서비스 — 세션 영속·멀티턴·롤링 요약 + 맥락 주입 LLM SSE 스트리밍`, 임포트 `from core.llm.client import _COACH_SYSTEM_PROMPT, LlmClient`(Task 2 에서 `_CONSULT_SYSTEM_PROMPT`로 교체 예정, Task 1 은 그대로), `from domain.user_intelligence.hub.repositories.consult_context_repository import ConsultContextRepository`·`consult_session_repository import ConsultSessionRepository`·`from domain.user_intelligence.hub.services import consult_context`, 클래스 `CoachService`→`ConsultService`, 함수 `build_coach_context`→`build_consult_context`, `CoachRepository`→`ConsultContextRepository`, `CoachSessionRepository`→`ConsultSessionRepository`. 로직·로드맵 주입 불변. 기존 삭제.

- [ ] **Step 5: 자기모델 추출 서비스 이동**

`domain/user_intelligence/hub/services/self_model_extraction_service.py` 생성 — 기존 `ai_coach` 버전 내용에서 임포트 `from domain.user_intelligence.hub.repositories.consult_session_repository import ConsultSessionRepository`(기존 `CoachSessionRepository`), 코드 내 `CoachSessionRepository`→`ConsultSessionRepository`, 상수 `SOURCE="consult_extraction"`(기존 `"coach_extraction"`). 나머지 로직 불변. 기존 `ai_coach/.../self_model_extraction_service.py` 삭제.

- [ ] **Step 6: evidence 컬럼·source 상수 개명**

`domain/user_intelligence/models/bases/user_self_model_evidence.py` 46행 `coach_session_ref`→`consult_session_ref`(속성명·컬럼명). `self_model_service.py` 11행 `SOURCE_COACH = "consult_extraction"`.

- [ ] **Step 7: 라우터 이동·개명 + main.py**

`api/v1/consult/__init__.py` 생성(빈 파일). `api/v1/consult/consult_routor.py` 생성 — 기존 `coach_routor.py` 내용에서 첫 줄 `# AI 상담 HTTP 라우터 — 세션 생성·영속 스트리밍·종료·히스토리`, `from domain.user_intelligence.hub.services.consult_service import ConsultService`, `router = APIRouter(prefix="/consult", tags=["consult"])`, `CoachService`→`ConsultService`, docstring 의 "코치"→"상담". 라우트 경로는 prefix 로 자동 `/consult/*`. 기존 `api/v1/coach/coach_routor.py`·`api/v1/coach/__init__.py` 삭제(폴더 비우기).

`main.py` — `from api.v1.coach.coach_routor import router as coach_v1_router`→`from api.v1.consult.consult_routor import router as consult_v1_router`, `app.include_router(coach_v1_router, ...)`→`app.include_router(consult_v1_router, prefix=API_V1_PREFIX)`.

- [ ] **Step 8: 스케줄러·alembic env 임포트 갱신**

`core/scheduler.py` 90행 `from domain.ai_coach.hub.services.self_model_extraction_service import (...)`→`from domain.user_intelligence.hub.services.self_model_extraction_service import (...)`.

`alembic/env.py` 80·81행 `from domain.ai_coach.models.bases.coach_session import CoachSession`·`coach_message import CoachMessage`→`from domain.user_intelligence.models.bases.consult_session import ConsultSession`·`consult_message import ConsultMessage`(주석도 상담으로).

- [ ] **Step 9: 수기 rename 마이그레이션 작성**

Run: `alembic revision -m "rename coach to consult"` (cwd `backend/`) — 빈 리비전 생성. 생성 파일에 첫 줄 docstring 유지, `down_revision` 이 `a6af4387ed37` 인지 확인. body 를 다음으로 작성.

```python
def upgrade() -> None:
    op.rename_table("coach_sessions", "consult_sessions")
    op.rename_table("coach_messages", "consult_messages")
    op.execute("ALTER INDEX ix_coach_sessions_user RENAME TO ix_consult_sessions_user")
    op.execute("ALTER INDEX ix_coach_messages_session RENAME TO ix_consult_messages_session")
    op.execute("ALTER TABLE consult_sessions RENAME CONSTRAINT fk_coach_session_user TO fk_consult_session_user")
    op.execute("ALTER TABLE consult_messages RENAME CONSTRAINT fk_coach_message_session TO fk_consult_message_session")
    op.alter_column("user_self_model_evidence", "coach_session_ref", new_column_name="consult_session_ref")
    op.execute("UPDATE user_self_model SET source = 'consult_extraction' WHERE source = 'coach_extraction'")
    op.execute("UPDATE user_self_model_evidence SET source = 'consult_extraction' WHERE source = 'coach_extraction'")


def downgrade() -> None:
    op.execute("UPDATE user_self_model_evidence SET source = 'coach_extraction' WHERE source = 'consult_extraction'")
    op.execute("UPDATE user_self_model SET source = 'coach_extraction' WHERE source = 'consult_extraction'")
    op.alter_column("user_self_model_evidence", "consult_session_ref", new_column_name="coach_session_ref")
    op.execute("ALTER TABLE consult_messages RENAME CONSTRAINT fk_consult_message_session TO fk_coach_message_session")
    op.execute("ALTER TABLE consult_sessions RENAME CONSTRAINT fk_consult_session_user TO fk_coach_session_user")
    op.execute("ALTER INDEX ix_consult_messages_session RENAME TO ix_coach_messages_session")
    op.execute("ALTER INDEX ix_consult_sessions_user RENAME TO ix_coach_sessions_user")
    op.rename_table("consult_messages", "coach_messages")
    op.rename_table("consult_sessions", "coach_sessions")
```

`op` import 가 없으면 상단에 `from alembic import op` 확인. `sa` 미사용이면 그대로 둔다.

- [ ] **Step 10: 마이그레이션 적용 (사용자 승인 게이트)**

**사용자에게 Neon 반영 승인을 받은 뒤** 실행.

Run: `alembic upgrade head`
Expected: 에러 없이 완료. `alembic current` 가 새 revision. 확인 쿼리(선택): `psql`/스크립트로 `SELECT to_regclass('consult_sessions')` 가 non-null.

- [ ] **Step 11: 테스트 6개 이동·개명 + 임포트 2개 갱신**

각 이동 테스트: 파일명 변경 + 내부 임포트(`domain.ai_coach.*`→`domain.user_intelligence.*`, 클래스 `Coach*`→`Consult*`) + 시드 SQL 의 `coach_sessions`/`coach_messages`→`consult_sessions`/`consult_messages` + 헤더 주석의 "코치"→"상담". assertion 로직은 불변.
- `consult_context_test.py`(구 coach_context_test) — 순수 헬퍼 테스트, 임포트만.
- `consult_service_test.py`(구 coach_service_test) — `ConsultService`·`ConsultSessionRepository`.
- `consult_session_repository_test.py`(구 coach_session_repository_test) — 시드 테이블명 갱신.
- `consult_session_models_import_test.py`(구 coach_session_models_import_test) — `ConsultSession`·`ConsultMessage` 임포트.
- `consult_stream_test.py`(구 coach_stream_test) — HTTP 경로 `/api/coach/*`→`/api/consult/*` 있으면 갱신.
- `consult_extract_repo_test.py`(구 coach_extract_repo_test) — `ConsultSessionRepository`·시드 테이블명.
- `self_model_extraction_test.py` — `from domain.user_intelligence.hub.services.self_model_extraction_service import SelfModelExtractionService`·`from domain.user_intelligence.hub.repositories.consult_session_repository import ConsultSessionRepository`, 시드 테이블명 `coach_*`→`consult_*`.
- `self_model_extract_job_test.py` — `_job_self_model_extract` 는 스케줄러 경유라 임포트 불변 가능, 시드 있으면 테이블명 갱신.

- [ ] **Step 12: ai_coach 스캐폴딩 보존 확인**

`domain/ai_coach/` 의 `hub/services`·`hub/repositories`·`models/bases` 에서 이동한 `.py` 만 제거되고 `__init__.py`·빈 폴더는 남았는지 확인(빈 스캐폴딩 보존). `api/v1/coach/` 폴더는 완전 삭제(라우터 이동).

- [ ] **Step 13: 전체 관련 회귀 실행**

Run (cwd `backend/`, 각 FAIL=0):
```bash
python scripts/consult_context_test.py
python scripts/consult_service_test.py
python scripts/consult_session_repository_test.py
python scripts/consult_session_models_import_test.py
python scripts/consult_stream_test.py
python scripts/consult_extract_repo_test.py
python scripts/self_model_extraction_test.py
python scripts/self_model_extract_job_test.py
python scripts/scheduler_refine_pipeline_test.py
```
잔여 참조 검사: `grep -rn "domain.ai_coach\|CoachService\|CoachSessionRepository\|coach_sessions\|coach_messages\|from api.v1.coach" backend --include=*.py | grep -v __pycache__` 결과가 비어야 한다(마이그레이션 파일의 `coach_sessions` rename 인자·downgrade 는 예외).

- [ ] **Step 14: ERD 갱신 + 커밋**

`backend/docs/erd.md` §6.6 의 `coach_sessions`·`coach_messages` 표기를 `consult_sessions`·`consult_messages` 로, `coach_session_ref`→`consult_session_ref`, provenance `coach_extraction`→`consult_extraction` 로 갱신.

```bash
git add backend/domain/user_intelligence backend/api/v1/consult backend/main.py backend/core/scheduler.py backend/alembic/env.py backend/alembic/versions/<new>.py backend/scripts/consult_*.py backend/scripts/self_model_extraction_test.py backend/scripts/self_model_extract_job_test.py backend/docs/erd.md
git add -A backend/domain/ai_coach backend/api/v1/coach
git commit -m "refactor(consult): 코치 대화 엔진을 user_intelligence 로 이전·전수 개명 (동작 불변)"
```

---

### Task 2: 로드맵 제거 + 상담사 시스템 프롬프트 (동작 변경)

**목표**: 이동된 상담 맥락에서 로드맵/퀘스트 주입을 제거하고, 코치 멘토 프롬프트를 상담사 프롬프트로 교체.

**Files:**
- Modify: `domain/user_intelligence/hub/repositories/consult_context_repository.py`
- Modify: `domain/user_intelligence/hub/services/consult_service.py` (`build_consult_context`, 프롬프트 임포트)
- Modify: `core/llm/client.py` (`_CONSULT_SYSTEM_PROMPT` 신설)
- Modify: `scripts/consult_context_test.py`, `scripts/consult_service_test.py` (로드맵 부재 단정)

**Interfaces:**
- Consumes: Task 1 의 `ConsultContextRepository`·`ConsultService`·`build_consult_context`·`consult_service` 모듈.
- Produces: `ConsultContextRepository.fetch_context(user_id)→{"persona":..., "movers":...}`(roadmap·quests 키 제거). `build_consult_context(ctx)→str`(로드맵·퀘스트 라인 없음). `core/llm/client._CONSULT_SYSTEM_PROMPT`.

- [ ] **Step 1: 로드맵 부재 실패 테스트 작성**

`scripts/consult_context_test.py` 에 순수 단정 추가(맨 아래 run 내, 기존 assertion 뒤).

```python
    # 로드맵 제거 회귀 가드 — 로드맵/퀘스트가 있어도 맥락 문자열에 새지 않는다.
    ctx_with_roadmap = {
        "persona": {"skills": [{"name": "Python"}], "summary": "데이터 지향"},
        "roadmap": {"title": "백엔드 로드맵"},
        "quests": [{"title": "FastAPI 퀘스트"}],
        "movers": [{"sector_slug": "ai-software"}],
    }
    s = build_consult_context(ctx_with_roadmap)
    check("맥락에 로드맵 없음", "로드맵" not in s and "백엔드 로드맵" not in s, s)
    check("맥락에 퀘스트 없음", "퀘스트" not in s and "FastAPI 퀘스트" not in s, s)
    check("맥락에 페르소나 유지", "Python" in s, s)
```

`consult_context_test.py` 상단 임포트에 `from domain.user_intelligence.hub.services.consult_service import build_consult_context` 추가(없으면).

- [ ] **Step 2: 실패 확인**

Run: `python scripts/consult_context_test.py`
Expected: `[FAIL] 맥락에 로드맵 없음` (현재 build_consult_context 가 로드맵 주입).

- [ ] **Step 3: `build_consult_context` 로드맵 라인 제거**

`consult_service.py` 의 `build_consult_context` 를 다음으로 교체.

```python
def build_consult_context(ctx: dict) -> str:
    """맥락 dict → 시스템 프롬프트에 붙일 맥락 문자열. 무네트워크 순수 함수.

    상담사 맥락은 페르소나·시장 상위 섹터만 — 로드맵·퀘스트는 코치 위임이라 주입하지 않는다.
    """
    persona = ctx.get("persona") or {}
    movers = ctx.get("movers") or []
    parts = ["[사용자 맥락]"]
    skills = [s.get("name") for s in (persona.get("skills") or []) if s.get("name")]
    parts.append(f"- 보유 스킬: {', '.join(skills) if skills else '미입력'}")
    if persona.get("summary"):
        parts.append(f"- 요약: {persona['summary']}")
    if movers:
        parts.append("- 시장 상위 섹터: " + ", ".join(m.get("sector_slug") for m in movers))
    return "\n".join(parts)
```

- [ ] **Step 4: 맥락 리포에서 로드맵 쿼리 제거**

`consult_context_repository.py` 를 다음으로 교체(로드맵·퀘스트 SQL·조회 삭제).

```python
# 상담 맥락 리포지토리 — 페르소나·상위 Pulse 섹터 읽기(로드맵은 코치 위임이라 제외)

from __future__ import annotations

from sqlalchemy import text

from domain.auth.hub.repositories.base_repository import BaseRepository

_FETCH_PERSONA = text(
    "SELECT skills, summary FROM user_personas WHERE user_id = CAST(:uid AS UUID)"
)

_FETCH_MOVERS = text(
    """
    SELECT sector_slug, score
    FROM pulse_metrics_log
    WHERE recorded_date = (SELECT MAX(recorded_date) FROM pulse_metrics_log)
    ORDER BY momentum_pct DESC NULLS LAST, score DESC
    LIMIT 3
    """
)


class ConsultContextRepository(BaseRepository):
    async def fetch_context(self, user_id: str) -> dict:
        """상담 맥락 묶음 — 페르소나·상위 섹터(로드맵·퀘스트 제외)."""
        pr = (await self.session.execute(_FETCH_PERSONA, {"uid": user_id})).first()
        persona = {
            "skills": (pr.skills or []) if pr else [],
            "summary": (pr.summary or "") if pr else "",
        }
        mrows = (await self.session.execute(_FETCH_MOVERS)).all()
        movers = [{"sector_slug": m.sector_slug, "score": m.score} for m in mrows]
        return {"persona": persona, "movers": movers}
```

- [ ] **Step 5: 상담사 시스템 프롬프트 신설·연결**

`core/llm/client.py` 의 `_COACH_SYSTEM_PROMPT` 정의 아래에 추가.

```python
_CONSULT_SYSTEM_PROMPT = (
    "너는 청년 진로 내비게이터의 'AI 상담사'다. 대화를 통해 사용자의 성격·성향·가치관·호불호를 파악하고, "
    "사용자가 미처 몰랐던 강점·관심 패턴을 짚어 준다. 진로의 방향을 함께 발견하는 것이 목표다. "
    "구체적 로드맵·퀘스트 설계는 다루지 않는다(그건 코치의 몫). 막연한 응원 대신 통찰을 주는 질문을 던지고, "
    "근거 없는 단정·과장은 피하며, 사용자의 말에서 관찰된 것만 언급한다. 답변은 따뜻하고 간결하게(보통 3~6문장)."
)
```

`consult_service.py` 임포트를 `from core.llm.client import _CONSULT_SYSTEM_PROMPT, LlmClient` 로 바꾸고, `stream_sse` 내 `system_content = _COACH_SYSTEM_PROMPT + ...` 를 `system_content = _CONSULT_SYSTEM_PROMPT + ...` 로 교체.

- [ ] **Step 6: 테스트 통과 확인 + 서비스 회귀**

Run: `python scripts/consult_context_test.py`
Expected: `FAIL=0` (로드맵 부재 3단정 포함 통과).

Run: `python scripts/consult_service_test.py`
Expected: `FAIL=0`. (맥락 주입이 로드맵 없이도 동작하는지 — 실패 시 테스트의 로드맵 관련 기대를 상담 맥락에 맞춰 갱신.)

- [ ] **Step 7: 커밋**

```bash
git add backend/domain/user_intelligence/hub/repositories/consult_context_repository.py backend/domain/user_intelligence/hub/services/consult_service.py backend/core/llm/client.py backend/scripts/consult_context_test.py backend/scripts/consult_service_test.py
git commit -m "refactor(consult): 상담 맥락에서 로드맵 제거 + 상담사 시스템 프롬프트"
```

---

### Task 3: 프론트 — consult 실엔진 + coach 플레이스홀더

**목표**: `/consult` 목업을 실엔진으로 교체, `/coach` 를 로드맵 코치 플레이스홀더로, 컴포넌트·API 클라이언트 개명.

**Files:**
- Move: `www.yeotaeho.kr/src/components/features/coach/CoachView.tsx` → `.../consult/ConsultView.tsx`
- Move: `www.yeotaeho.kr/src/components/features/coach/InsightWalletPanel.tsx` → `.../consult/InsightWalletPanel.tsx`
- Move: `www.yeotaeho.kr/src/lib/api/coach.ts` → `.../lib/api/consult.ts`
- Modify: `www.yeotaeho.kr/src/app/(main)/consult/page.tsx` (목업 → `<ConsultView />`)
- Modify: `www.yeotaeho.kr/src/app/(main)/coach/page.tsx` (플레이스홀더)

**Interfaces:**
- Consumes: Task 1 의 API `/api/consult/sessions`·`/stream`·`/sessions/{id}/end`·`/sessions/{id}/messages`.
- Produces: 없음(말단 UI).

- [ ] **Step 1: API 클라이언트 개명**

`www.yeotaeho.kr/src/lib/api/consult.ts` 생성 — 기존 `coach.ts` 내용에서 첫 줄 주석을 상담으로, 모든 엔드포인트 문자열 `/api/coach/`→`/api/consult/`, export 함수·타입명 중 `coach`/`Coach` 접두를 `consult`/`Consult` 로(예: `createCoachSession`→`createConsultSession`, `streamCoach`→`streamConsult`, `CoachMessage`→`ConsultMessage`, `fetchCoachMessages`→`fetchConsultMessages`, `endCoachSession`→`endConsultSession`). 기존 `coach.ts` 삭제. (정확한 export 목록은 파일을 열어 1:1 개명.)

- [ ] **Step 2: 컴포넌트 개명·이동**

`www.yeotaeho.kr/src/components/features/consult/ConsultView.tsx` 생성 — 기존 `CoachView.tsx` 내용에서 컴포넌트 `CoachView`→`ConsultView`, `import { ... } from "@/lib/api/coach"`→`"@/lib/api/consult"` 및 개명된 함수·타입 사용, `./InsightWalletPanel` 임포트 경로 유지, 사용자 노출 문구의 "코치"→"상담사/상담"(있으면). `InsightWalletPanel.tsx` 를 `consult/` 로 이동(내용 불변). 기존 `components/features/coach/` 폴더 삭제.

- [ ] **Step 3: `/consult` 페이지 실엔진 교체**

`www.yeotaeho.kr/src/app/(main)/consult/page.tsx` 전체를 다음으로 교체.

```tsx
"use client";

import { ConsultView } from "@/components/features/consult/ConsultView";

export default function ConsultPage() {
  return <ConsultView />;
}
```

- [ ] **Step 4: `/coach` 플레이스홀더**

`www.yeotaeho.kr/src/app/(main)/coach/page.tsx` 전체를 다음으로 교체.

```tsx
"use client";

import Link from "next/link";
import { ChevronRight, Map } from "lucide-react";

export default function CoachPage() {
  return (
    <div className="mx-auto max-w-xl px-4 py-16 text-center">
      <div className="mx-auto mb-5 inline-flex rounded-2xl bg-indigo-100 p-4 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-300">
        <Map className="h-8 w-8" />
      </div>
      <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100">로드맵 코치 준비 중</h1>
      <p className="mt-3 text-sm leading-relaxed text-slate-600 dark:text-slate-400">
        AI 코치는 상담실에서 발견한 방향을 바탕으로 성장 로드맵을 함께 설계합니다. 곧 찾아옵니다.
      </p>
      <Link
        href="/roadmap"
        className="mt-6 inline-flex items-center gap-1 rounded-xl bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-indigo-700"
      >
        지금은 로드맵 보기 <ChevronRight className="h-4 w-4" />
      </Link>
    </div>
  );
}
```

- [ ] **Step 5: 잔여 참조 확인 + 타입 검증**

Run(잔여 coach 참조): `grep -rn "features/coach\|lib/api/coach\|CoachView\|from \"@/lib/api/coach\"" www.yeotaeho.kr/src` — 비어야 한다.

Run: `cd www.yeotaeho.kr; pnpm exec tsc --noEmit`
Expected: 출력 없음(0 에러).

- [ ] **Step 6: 커밋**

```bash
git add www.yeotaeho.kr/src/components/features/consult www.yeotaeho.kr/src/lib/api/consult.ts "www.yeotaeho.kr/src/app/(main)/consult/page.tsx" "www.yeotaeho.kr/src/app/(main)/coach/page.tsx"
git add -A www.yeotaeho.kr/src/components/features/coach www.yeotaeho.kr/src/lib/api/coach.ts
git commit -m "refactor(consult): /consult 실엔진 연결 + /coach 로드맵 코치 플레이스홀더"
```

---

## 최종 검증 (whole-branch)

- [ ] 백엔드 관련 회귀 (cwd `backend/`, 각 FAIL=0):
```bash
python scripts/consult_context_test.py
python scripts/consult_service_test.py
python scripts/consult_session_repository_test.py
python scripts/consult_session_models_import_test.py
python scripts/consult_stream_test.py
python scripts/consult_extract_repo_test.py
python scripts/self_model_extraction_test.py
python scripts/self_model_extract_job_test.py
python scripts/self_model_merge_test.py
python scripts/scheduler_refine_pipeline_test.py
python scripts/recommend_explain_service_test.py
```
- [ ] 잔여 참조 0: `grep -rn "domain.ai_coach\|CoachService\|coach_sessions\|coach_messages\|api.v1.coach\|coach_extraction" backend --include=*.py | grep -v __pycache__ | grep -v "alembic/versions"` 가 비어야 한다.
- [ ] 프론트 `cd www.yeotaeho.kr; pnpm exec tsc --noEmit` 0 에러 + `grep -rn "features/coach\|lib/api/coach" www.yeotaeho.kr/src` 비어야 함.
- [ ] 리뷰 게이트 — code-reviewer 에이전트 whole-branch → Codex `/codex:review --base <시작 ref> --scope branch`.
