# 대화→자기모델 증분 추출(SP-2b) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 코치 대화에서 사용자의 성향·호불호·가치관·제약을 비동기 증분 추출해 SP-1 자기모델에 축적한다.

**Architecture:** `coach_sessions.extracted_until`(이미 추출한 메시지 수)로 증분 지점 추적. `LlmClient.extract_self_model`이 최근 미추출 대화를 구조축(RIASEC top_codes·서사) + 근거(evidence)로 추출 → `SelfModelExtractionService`가 `SelfModelService.upsert_structured`/`append_evidence(source='coach_extraction')`로 반영 → 일일 스케줄러 잡이 신규 메시지 충분한 세션을 스캔. 전부 멱등.

**Tech Stack:** FastAPI · SQLAlchemy 2.0 async · Alembic · Neon · OpenAI(JSON mode) · APScheduler. 테스트는 표준 라이브러리 `scripts/*_test.py`.

## Global Constraints

- **테스트 실행** — `cd backend && python scripts/<name>_test.py`.
- **Alembic** — CLI `alembic`. autogenerate 시 무관 테이블 drift(sectors·sub_sectors·raw_tech_adoption_data·sector_source_map)가 잡히면 제거하고 대상 변경만 남긴다.
- **Neon 쓰기 승인** — 마이그레이션 upgrade·Neon insert 테스트는 실행 시 사용자 승인. 순수 파서 테스트는 불필요.
- **파일 헤더** — 새 소스 첫 줄 한 줄 한국어 주석. 한국어 종결 `.`/`?`/`!`(‘:’ 금지).
- **재사용 계약(변경 금지)** — `SelfModelService(db).upsert_structured(user_id, incoming: dict, source: str)`(incoming keys `riasec, big_five, narrative_summary, axis_confidence`), `.append_evidence(user_id, items: list[dict], source: str) -> int`(item keys `dimension, polarity, content, confidence, is_sensitive`). `CoachSessionRepository(db)`의 `get_session`·`fetch_messages`·`count_messages`.
- **source 고정** — 추출 기록은 항상 `source="coach_extraction"`.
- **커밋** — 논리 단위 semantic commit. `git add .` 금지(지정 파일만, `.omc/`·`.superpowers/`·`__pycache__` 제외). 끝줄 `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
- **테스트 사용자·정리** — Neon 테스트는 `SELECT id FROM users ORDER BY created_at LIMIT 1` 사용자 재사용, 시작·종료에 그 사용자의 coach 세션/메시지 + `user_self_model`/`user_self_model_evidence` 행 DELETE(idempotent).
- **상수** — `MIN_NEW = 6`(추출 트리거 최소 신규 메시지 수).
- **범위** — SP-2b는 추출·저장까지. 임베딩 반영(SP-3)·능동 탐침·numeric big_five/6점수·UI 는 범위 밖.

---

### Task 1: `extracted_until` 컬럼 + 리포지토리 확장

**Files:**
- Modify: `backend/domain/ai_coach/models/bases/coach_session.py` (컬럼 추가)
- Create: `backend/alembic/versions/<autogen>_add_extracted_until.py`
- Modify: `backend/domain/ai_coach/hub/repositories/coach_session_repository.py`
- Test: `backend/scripts/coach_extract_repo_test.py`

**Interfaces:**
- Consumes: SP-2a `coach_sessions`·`coach_messages`, `CoachSessionRepository`.
- Produces: `get_session` 반환에 `extracted_until` 추가 · `update_extracted(session_id, extracted_until) -> None` · `fetch_extractable_sessions(min_new, limit) -> list[dict]`(keys `id`, `user_id`).

- [ ] **Step 1: 리포지토리 Neon 테스트 작성**

Create `backend/scripts/coach_extract_repo_test.py`:
```python
# 코치 세션 추출 지점 리포지토리 확장 Neon 테스트 — extracted_until·update·추출대상 조회

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
        for i in range(8):
            await repo.add_message(sid, "user" if i % 2 == 0 else "assistant", f"m{i}")

        sess = await repo.get_session(sid)
        check("초기 extracted_until 0", sess["extracted_until"] == 0, str(sess))

        await repo.update_extracted(sid, 4)
        sess = await repo.get_session(sid)
        check("update_extracted 반영", sess["extracted_until"] == 4)

        # 8 메시지, extracted_until 4 → 신규 4. min_new=2 면 4>2 선택, min_new=5 면 미선택.
        sel2 = await repo.fetch_extractable_sessions(2, 10)
        check("추출대상 선택(min_new=2)", any(r["id"] == sid for r in sel2), str(sel2))
        sel5 = await repo.fetch_extractable_sessions(5, 10)
        check("미달 미선택(min_new=5)", all(r["id"] != sid for r in sel5), str(sel5))
        check("추출대상 user_id 동반", all("user_id" in r for r in sel2))

        await _cleanup(s, uid)
    print(f"\n결과: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
```

- [ ] **Step 2: 실패 확인** — `cd backend && python scripts/coach_extract_repo_test.py` → FAIL(`extracted_until` KeyError 또는 메서드 없음).

- [ ] **Step 3: ORM 컬럼 추가**

Modify `backend/domain/ai_coach/models/bases/coach_session.py` — `summarized_until` 컬럼 정의 다음에 추가(`Integer` import 되어 있음):
```python
    extracted_until: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
```

- [ ] **Step 4: 마이그레이션**

Run: `cd backend && alembic heads`(단일 head) → `alembic revision --autogenerate -m "add extracted_until to coach_sessions"`. 검토: `upgrade()`가 `op.add_column('coach_sessions', sa.Column('extracted_until', sa.Integer(), nullable=False, server_default='0'))` 만(무관 drift 제거), `downgrade()`는 `drop_column`. 승인 후 `alembic upgrade head`.

- [ ] **Step 5: 리포지토리 확장**

Modify `backend/domain/ai_coach/hub/repositories/coach_session_repository.py`:
1. `_GET` 쿼리에 `extracted_until` 추가 — 예: `SELECT user_id, status, context_summary, summarized_until, extracted_until FROM coach_sessions WHERE id = CAST(:id AS UUID)`.
2. `get_session` 반환 dict 에 `"extracted_until": r.extracted_until` 추가.
3. 모듈 끝에 쿼리·메서드 추가:
```python
_UPDATE_EXTRACTED = text(
    "UPDATE coach_sessions SET extracted_until = :eu, extracted_at = now() WHERE id = CAST(:id AS UUID)"
)
_FETCH_EXTRACTABLE = text(
    """
    SELECT s.id, s.user_id
    FROM coach_sessions s
    WHERE (SELECT count(*) FROM coach_messages m WHERE m.session_id = s.id)
          > s.extracted_until + :min_new
    ORDER BY s.started_at ASC
    LIMIT :limit
    """
)
```
```python
    async def update_extracted(self, session_id: str, extracted_until: int) -> None:
        await self.session.execute(
            _UPDATE_EXTRACTED, {"id": session_id, "eu": extracted_until}
        )
        await self.session.commit()

    async def fetch_extractable_sessions(self, min_new: int, limit: int) -> list[dict]:
        rows = (
            await self.session.execute(
                _FETCH_EXTRACTABLE, {"min_new": min_new, "limit": limit}
            )
        ).all()
        return [{"id": str(r.id), "user_id": str(r.user_id)} for r in rows]
```

- [ ] **Step 6: 테스트 통과(Neon 승인)** — `cd backend && python scripts/coach_extract_repo_test.py` → `PASS=5 FAIL=0`.

- [ ] **Step 7: 커밋**
```bash
git add backend/domain/ai_coach/models/bases/coach_session.py backend/alembic/versions/<hash>_add_extracted_until.py backend/domain/ai_coach/hub/repositories/coach_session_repository.py backend/scripts/coach_extract_repo_test.py
git commit -m "feat(self-model): coach_sessions.extracted_until + 추출대상 조회 (SP-2b Task1)"
```

---

### Task 2: 추출 LLM (`extract_self_model` + 순수 파서)

**Files:**
- Modify: `backend/core/llm/client.py`
- Test: `backend/scripts/self_model_extract_parse_test.py`

**Interfaces:**
- Produces: `_parse_self_model_extract(raw: str | None) -> dict`(keys `riasec_top_codes: list[str]`, `riasec_confidence: float`, `narrative: str | None`, `evidence: list[dict]`) · `LlmClient.extract_self_model(messages: list[dict]) -> dict`.

- [ ] **Step 1: 순수 파서 테스트 작성(무DB·무LLM)**

Create `backend/scripts/self_model_extract_parse_test.py`:
```python
# 자기모델 추출 응답 순수 파서 테스트 — RIASEC 필터·confidence 클램프·dimension 닫힌집합

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SCHEDULER_ENABLED", "false")

from core.llm.client import _parse_self_model_extract

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
    ok = _parse_self_model_extract(json.dumps({
        "riasec_top_codes": ["I", "A", "Z"], "riasec_confidence": 1.5,
        "narrative": "탐구·표현 지향",
        "evidence": [
            {"dimension": "like", "polarity": "like", "content": "발표를 좋아함", "confidence": 0.8},
            {"dimension": "weird", "content": "장거리 통근 싫음", "is_sensitive": True},
            {"dimension": "value", "content": "  ", "confidence": 0.5},
        ],
    }))
    check("RIASEC 유효코드만", ok["riasec_top_codes"] == ["I", "A"], str(ok["riasec_top_codes"]))
    check("confidence 클램프", ok["riasec_confidence"] == 1.0)
    check("narrative", ok["narrative"] == "탐구·표현 지향")
    check("dimension 닫힌집합 보정", ok["evidence"][1]["dimension"] == "other")
    check("is_sensitive 유지", ok["evidence"][1]["is_sensitive"] is True)
    check("빈 content 드롭", len(ok["evidence"]) == 2, str(ok["evidence"]))

    empty = _parse_self_model_extract("not json")
    check("파싱불가 빈결과", empty == {"riasec_top_codes": [], "riasec_confidence": 0.0, "narrative": None, "evidence": []})

    nocode = _parse_self_model_extract(json.dumps({"riasec_top_codes": [], "riasec_confidence": 0.9}))
    check("코드 없으면 confidence 0", nocode["riasec_confidence"] == 0.0)

    print(f"\n결과: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(run())
```

- [ ] **Step 2: 실패 확인** — `cd backend && python scripts/self_model_extract_parse_test.py` → FAIL(ImportError).

- [ ] **Step 3: 프롬프트 상수 + 파서 추가**

Modify `backend/core/llm/client.py` — `_COACH_SUMMARY_SYSTEM_PROMPT` 정의 다음에 추가:
```python
_SELF_MODEL_EXTRACT_SYSTEM_PROMPT = (
    "너는 청년 진로 코치와 사용자의 대화에서 사용자의 '자기모델' 신호를 추출하는 분석기다. "
    "대화에서 드러난 (1) 직업 흥미(RIASEC: R현실·I탐구·A예술·S사회·E기업·C관습 중 두드러진 1~3개), "
    "(2) 한 줄 자기서사, (3) 근거(호불호·가치관·제약·포부·스킬 신호)를 뽑아라. "
    "확실하지 않으면 riasec_top_codes 를 빈 배열로, narrative 를 null 로 두라(억지 추정 금지). "
    "각 신호에 confidence(0~1)를 정직하게 매겨라. "
    "민감정보(트라우마·개인적 아픔·건강·가정사 등)는 사용자가 스스로 드러낸 것만 is_sensitive=true 로 표시하고, "
    "능동적으로 캐묻거나 추론하지 마라. "
    'JSON 객체만 출력하라. 형식: {"riasec_top_codes": [<"R"|"I"|"A"|"S"|"E"|"C">...], '
    '"riasec_confidence": <0~1>, "narrative": <문자열 또는 null>, '
    '"evidence": [{"dimension": <"like"|"dislike"|"value"|"constraint"|"sensitive"|"aspiration"|"skill_signal"|"other">, '
    '"polarity": <"like"|"dislike"|"neutral"|null>, "content": <근거 문장>, '
    '"confidence": <0~1>, "is_sensitive": <bool>}...]}.'
)

_RIASEC_CODES = ("R", "I", "A", "S", "E", "C")
_EVIDENCE_DIMS = ("like", "dislike", "value", "constraint", "sensitive", "aspiration", "skill_signal", "other")
_EVIDENCE_POLARITIES = ("like", "dislike", "neutral")


def _parse_self_model_extract(raw: str | None) -> dict:
    """자기모델 추출 응답을 검증된 결과로 파싱한다. 무네트워크 순수 함수.

    riasec_top_codes 는 유효 코드만·최대 6개(없으면 confidence 0). evidence 는 content 있는 항목만·최대 20개,
    dimension 닫힌집합 외는 'other', polarity 닫힌집합 외는 None, confidence 0~1 클램프.
    """
    empty = {"riasec_top_codes": [], "riasec_confidence": 0.0, "narrative": None, "evidence": []}
    try:
        obj = json.loads(raw) if raw else {}
    except (json.JSONDecodeError, TypeError):
        return dict(empty)
    if not isinstance(obj, dict):
        return dict(empty)

    codes_raw = obj.get("riasec_top_codes")
    codes = [c for c in codes_raw if c in _RIASEC_CODES][:6] if isinstance(codes_raw, list) else []
    try:
        rconf = float(obj.get("riasec_confidence"))
    except (TypeError, ValueError):
        rconf = 0.0
    rconf = max(0.0, min(1.0, rconf))
    if not codes:
        rconf = 0.0

    narrative = obj.get("narrative")
    narrative = narrative.strip()[:500] if isinstance(narrative, str) and narrative.strip() else None

    evidence: list[dict] = []
    ev_raw = obj.get("evidence")
    if isinstance(ev_raw, list):
        for it in ev_raw:
            if not isinstance(it, dict):
                continue
            content = it.get("content")
            if not isinstance(content, str) or not content.strip():
                continue
            dim = it.get("dimension")
            dim = dim if dim in _EVIDENCE_DIMS else "other"
            pol = it.get("polarity")
            pol = pol if pol in _EVIDENCE_POLARITIES else None
            try:
                conf = float(it.get("confidence"))
            except (TypeError, ValueError):
                conf = 0.0
            conf = max(0.0, min(1.0, conf))
            evidence.append({
                "dimension": dim,
                "polarity": pol,
                "content": content.strip()[:500],
                "confidence": conf,
                "is_sensitive": bool(it.get("is_sensitive", False)),
            })
            if len(evidence) >= 20:
                break

    return {
        "riasec_top_codes": codes,
        "riasec_confidence": rconf,
        "narrative": narrative,
        "evidence": evidence,
    }
```

- [ ] **Step 4: 파서 테스트 통과** — `cd backend && python scripts/self_model_extract_parse_test.py` → `PASS=9 FAIL=0`.

- [ ] **Step 5: `extract_self_model` 메서드 추가**

Modify `backend/core/llm/client.py` — `summarize_conversation` 메서드 다음에 추가:
```python
    async def extract_self_model(self, messages: list[dict]) -> dict:
        """코치 대화(최근 미추출분)에서 자기모델 신호(RIASEC·서사·근거)를 추출한다."""
        convo = "\n".join(
            f"{m.get('role')}: {m.get('content')}" for m in messages
            if m.get("role") in ("user", "assistant") and m.get("content")
        )
        resp = await self._client.chat.completions.create(
            model=self._model,
            temperature=0.2,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": _SELF_MODEL_EXTRACT_SYSTEM_PROMPT},
                {"role": "user", "content": convo},
            ],
        )
        return _parse_self_model_extract(resp.choices[0].message.content)
```

- [ ] **Step 6: import 확인** — `cd backend && python -c "import core.llm.client"` → 오류 없음. 파서 테스트 재실행 green.

- [ ] **Step 7: 커밋**
```bash
git add backend/core/llm/client.py backend/scripts/self_model_extract_parse_test.py
git commit -m "feat(self-model): extract_self_model LLM + 순수 파서 (SP-2b Task2)"
```

---

### Task 3: SelfModelExtractionService

**Files:**
- Create: `backend/domain/ai_coach/hub/services/self_model_extraction_service.py`
- Test: `backend/scripts/self_model_extraction_test.py`

**Interfaces:**
- Consumes: Task 1 리포지토리(`get_session`·`fetch_messages`·`update_extracted`·`fetch_extractable_sessions`), Task 2 `LlmClient.extract_self_model`, SP-1 `SelfModelService`.
- Produces: `SelfModelExtractionService(db)` with `async extract_session(user_id, session_id) -> dict`, `async extract_pending(limit=20) -> dict`. 테스트 주입점 `self._extractor`.

- [ ] **Step 1: 서비스 Neon 테스트 작성(fake extractor)**

Create `backend/scripts/self_model_extraction_test.py`:
```python
# SelfModelExtractionService — 세션→자기모델 추출·멱등·MIN_NEW 스킵(fake extractor, Neon)

from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SCHEDULER_ENABLED", "false")

from sqlalchemy import text

from core.database import AsyncSessionLocal
from domain.ai_coach.hub.repositories.coach_session_repository import CoachSessionRepository
from domain.ai_coach.hub.services.self_model_extraction_service import SelfModelExtractionService
from domain.user_intelligence.hub.services.self_model_service import SelfModelService

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
    await s.execute(text("DELETE FROM user_self_model_evidence WHERE user_id = CAST(:u AS UUID)"), {"u": uid})
    await s.execute(text("DELETE FROM user_self_model WHERE user_id = CAST(:u AS UUID)"), {"u": uid})
    await s.commit()


async def run() -> int:
    async with AsyncSessionLocal() as s:
        uid = await _uid(s)
        await _cleanup(s, uid)
        repo = CoachSessionRepository(s)
        sid = await repo.create_session(uid)
        for i in range(8):
            await repo.add_message(sid, "user" if i % 2 == 0 else "assistant", f"발표와 데이터 분석 이야기 {i}")

        svc = SelfModelExtractionService(s)
        fake_calls = {"n": 0}

        async def fake_extractor(messages):
            fake_calls["n"] += 1
            return {
                "riasec_top_codes": ["I", "A"],
                "riasec_confidence": 0.8,
                "narrative": "탐구·표현 지향",
                "evidence": [
                    {"dimension": "like", "polarity": "like", "content": "발표를 좋아함", "confidence": 0.9, "is_sensitive": False},
                    {"dimension": "constraint", "polarity": None, "content": "장거리 통근 어려움", "confidence": 0.7, "is_sensitive": True},
                ],
            }

        svc._extractor = fake_extractor

        res = await svc.extract_session(uid, sid)
        check("추출 8건", res.get("extracted") == 8, str(res))
        check("근거 2건", res.get("evidence") == 2, str(res))

        model = await SelfModelService(s).get_self_model(uid, include_sensitive=True)
        check("riasec 반영", model["riasec"] == {"top_codes": ["I", "A"]}, str(model["riasec"]))
        check("narrative 반영", model["narrativeSummary"] == "탐구·표현 지향")
        contents = [e["content"] for e in model["evidence"]]
        check("비민감 근거 저장", "발표를 좋아함" in contents)
        check("민감 근거 격리 저장", "장거리 통근 어려움" in contents)  # include_sensitive=True 이므로 보임

        # extracted_until 전진
        check("extracted_until=8", (await repo.get_session(sid))["extracted_until"] == 8)

        # 멱등 — 새 메시지 없으면 스킵, 추출기 재호출 안 됨
        res2 = await svc.extract_session(uid, sid)
        check("재추출 스킵", res2.get("skipped") is True, str(res2))
        check("추출기 1회만 호출", fake_calls["n"] == 1, str(fake_calls))

        # MIN_NEW 미만 — 3개만 더 추가(신규 3 < 6) → 스킵
        for i in range(3):
            await repo.add_message(sid, "user", f"추가 {i}")
        res3 = await svc.extract_session(uid, sid)
        check("MIN_NEW 미만 스킵", res3.get("skipped") is True, str(res3))

        # extract_pending — 6개 더 추가하면 신규 9 → 선택·처리
        for i in range(6):
            await repo.add_message(sid, "user", f"더 {i}")
        pend = await svc.extract_pending(limit=10)
        check("extract_pending 처리", pend.get("processed") >= 1, str(pend))

        await _cleanup(s, uid)
    print(f"\n결과: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
```

- [ ] **Step 2: 실패 확인** — `cd backend && python scripts/self_model_extraction_test.py` → FAIL(ModuleNotFoundError).

- [ ] **Step 3: 서비스 구현**

Create `backend/domain/ai_coach/hub/services/self_model_extraction_service.py`:
```python
# 자기모델 추출 서비스 — 코치 대화(최근 미추출분)에서 자기모델 신호를 증분 추출·반영

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from core.config.settings import get_settings
from core.llm.client import LlmClient
from domain.ai_coach.hub.repositories.coach_session_repository import CoachSessionRepository
from domain.user_intelligence.hub.services.self_model_service import SelfModelService

logger = logging.getLogger(__name__)

MIN_NEW = 6
SOURCE = "coach_extraction"


class SelfModelExtractionService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.coach_repo = CoachSessionRepository(db)
        settings = get_settings()
        self._api_key = settings.openai_api_key
        self._model = settings.llm_classify_model
        self._extractor = self._default_extractor

    async def _default_extractor(self, messages: list[dict]) -> dict:
        llm = LlmClient(api_key=self._api_key, model=self._model)
        return await llm.extract_self_model(messages)

    async def extract_session(self, user_id: str, session_id: str) -> dict:
        """세션의 미추출 대화에서 자기모델을 갱신한다. 신규 메시지 부족 시 스킵."""
        sess = await self.coach_repo.get_session(session_id)
        if sess is None:
            return {"skipped": True, "reason": "no_session"}
        extracted_until = sess["extracted_until"]
        msgs = await self.coach_repo.fetch_messages(session_id)
        cutoff = len(msgs)
        new_msgs = msgs[extracted_until:cutoff]
        if len(new_msgs) < MIN_NEW:
            return {"skipped": True, "reason": "insufficient"}

        result = await self._extractor(new_msgs)
        svc = SelfModelService(self.db)
        incoming = {
            "riasec": {"top_codes": result["riasec_top_codes"]} if result["riasec_top_codes"] else None,
            "big_five": None,
            "narrative_summary": result["narrative"],
            "axis_confidence": {"riasec": result["riasec_confidence"]},
        }
        await svc.upsert_structured(user_id, incoming, SOURCE)
        n_ev = await svc.append_evidence(user_id, result["evidence"], SOURCE)
        await self.coach_repo.update_extracted(session_id, cutoff)
        return {"extracted": len(new_msgs), "evidence": n_ev, "riasec": bool(result["riasec_top_codes"])}

    async def extract_pending(self, limit: int = 20) -> dict:
        """신규 메시지 충분한 세션을 스캔해 각각 추출한다. 건별 실패 격리."""
        rows = await self.coach_repo.fetch_extractable_sessions(MIN_NEW, limit)
        processed = 0
        for r in rows:
            try:
                res = await self.extract_session(r["user_id"], r["id"])
                if not res.get("skipped"):
                    processed += 1
            except Exception as e:
                logger.warning(f"자기모델 추출 실패(session {r['id']}): {e}")
        return {"sessions": len(rows), "processed": processed}
```

- [ ] **Step 4: 테스트 통과(Neon 승인)** — `cd backend && python scripts/self_model_extraction_test.py` → `PASS=11 FAIL=0`.

- [ ] **Step 5: 커밋**
```bash
git add backend/domain/ai_coach/hub/services/self_model_extraction_service.py backend/scripts/self_model_extraction_test.py
git commit -m "feat(self-model): SelfModelExtractionService — 대화 증분 추출·멱등 (SP-2b Task3)"
```

---

### Task 4: 스케줄러 일일 추출 잡

**Files:**
- Modify: `backend/core/scheduler.py`
- Test: `backend/scripts/self_model_extract_job_test.py`

**Interfaces:**
- Consumes: Task 3 `SelfModelExtractionService`.
- Produces: `_job_self_model_extract() -> dict` 등록(일일).

- [ ] **Step 1: 잡 스모크 테스트 작성**

Create `backend/scripts/self_model_extract_job_test.py`:
```python
# 자기모델 추출 잡 스모크 — _job_self_model_extract 가 dict 반환(에러 없이 실행)

from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SCHEDULER_ENABLED", "false")

from core.scheduler import _job_self_model_extract

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


async def run() -> int:
    res = await _job_self_model_extract()
    check("dict 반환", isinstance(res, dict), str(type(res)))
    check("sessions 키", "sessions" in res and "processed" in res, str(res))
    print(f"\n결과: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
```

- [ ] **Step 2: 실패 확인** — `cd backend && python scripts/self_model_extract_job_test.py` → FAIL(ImportError: `_job_self_model_extract`).

- [ ] **Step 3: 잡 함수 + 등록**

Modify `backend/core/scheduler.py`:
1. 기존 `_job_*` 함수들(예: `_job_user_embed`) 근처에 추가:
```python
async def _job_self_model_extract() -> dict[str, Any]:
    """코치 대화에서 자기모델 증분 추출(멱등, 일일)."""
    async with AsyncSessionLocal() as session:
        return await SelfModelExtractionService(session).extract_pending(limit=50)
```
2. 파일 상단 import 에 추가: `from domain.ai_coach.hub.services.self_model_extraction_service import SelfModelExtractionService`.
3. 스케줄러 잡 등록부(다른 `scheduler.add_job(... CronTrigger ...)` 호출들 옆)에 일일 잡 추가 — 기존 일일 잡의 `add_job` 형식을 그대로 따라 `CronTrigger(hour=10, minute=0)` 로 등록(09:00 정제 파이프라인 이후):
```python
    scheduler.add_job(
        _job_self_model_extract,
        CronTrigger(hour=10, minute=0),
        id="self_model_extract",
        replace_existing=True,
    )
```
(파일의 실제 `add_job` 시그니처·타임존 인자를 먼저 확인해 동일하게 맞춘다.)

- [ ] **Step 4: 스모크 통과(Neon 승인)** — `cd backend && python scripts/self_model_extract_job_test.py` → `PASS=2 FAIL=0`.

- [ ] **Step 5: 커밋**
```bash
git add backend/core/scheduler.py backend/scripts/self_model_extract_job_test.py
git commit -m "feat(self-model): 일일 자기모델 추출 스케줄러 잡 (SP-2b Task4)"
```

---

## 마무리(전 태스크 완료 후)

- [ ] **전체 회귀** — `cd backend && python scripts/coach_extract_repo_test.py && python scripts/self_model_extract_parse_test.py && python scripts/self_model_extraction_test.py && python scripts/self_model_extract_job_test.py` 전부 PASS. 기존 coach·self_model 테스트 회귀 확인.
- [ ] **감사 기록** — `backend/domain/ai_coach/docs/audit_trail.md`(추출은 coach 주도) 최상단에 SP-2b 항목(경로 승인 후).
- [ ] **ERD** — `erd.md` §6.6 `coach_sessions` 에 `extracted_until` 반영.
- [ ] **Codex 리뷰** — 브랜치 범위. Critical/Important 조치 후 재리뷰.
- [ ] **다음** — SP-3: 자기모델(구조축·비민감 근거)을 `build_user_embed_text` 직렬화 + Sync/Chance 설명 레이어.

## Self-Review (플랜 작성자 체크)

- **스펙 커버리지** — spec §3(extracted_until)=T1, §4(추출 LLM)=T2, §5(추출 서비스)=T3, §6(리포지토리)=T1, §7(스케줄러)=T4, §8 성공기준 1=T1·2/3/4=T3·5(민감격리)=T3(SP-1 위임)·6(게이팅)=T3(SP-1 위임), §9 테스트=각 태스크. 커버 갭 없음.
- **플레이스홀더** — T4 Step3은 기존 scheduler `add_job` 시그니처 확인 지시(파일 구조 의존) — 그 외 전부 실제 코드·명령·기대값.
- **타입 일관성** — `_parse_self_model_extract` 반환 키(`riasec_top_codes, riasec_confidence, narrative, evidence`)가 T2 정의·T3 `extract_session` 소비에서 일치. `incoming` 키(`riasec, big_five, narrative_summary, axis_confidence`)가 SP-1 `upsert_structured` 계약과 일치. evidence item 키(`dimension, polarity, content, confidence, is_sensitive`)가 SP-1 `append_evidence` 계약과 일치. `get_session["extracted_until"]`·`update_extracted`·`fetch_extractable_sessions` 가 T1 정의·T3 소비에서 일치.
