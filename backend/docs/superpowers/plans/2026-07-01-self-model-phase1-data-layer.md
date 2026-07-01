# 자기모델 데이터층(SP-1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** AI 상담실이 파악할 사용자 자기모델(구조 척추 + 서사 근거)을 저장·병합·조회하는 데이터층을 만든다.

**Architecture:** 두 테이블 — `user_self_model`(1행/사용자·RIASEC·Big Five·자기서사) + `user_self_model_evidence`(N행·호불호·제약·민감정보, append-only+dedup). 리포지토리는 dumb SQL(upsert·append·fetch), 서비스는 순수 병합 규칙(`user_form` 우위·confidence 게이팅)과 조회 셰이핑. 읽기 API `GET /api/user/self-model`(비민감 기본). 추출(SP-2)·추천 반영(SP-3)은 이 위에 얹힌다.

**Tech Stack:** FastAPI · SQLAlchemy 2.0 async · Alembic · PostgreSQL(Neon) · Pydantic. 테스트는 표준 라이브러리 기반 `scripts/*_test.py`(pytest 아님).

## Global Constraints

- **테스트 실행** — `cd backend && python scripts/<name>_test.py` (프로젝트는 pytest 아닌 독립 스크립트 사용). 서버 필요 테스트는 `httpx.ASGITransport`(인프로세스).
- **Alembic** — CLI `alembic` 사용(`python -m alembic` 금지). 생성 마이그레이션은 검토 후 적용, 수동 DDL 금지.
- **Neon 쓰기 승인** — 마이그레이션 `alembic upgrade head` 와 Neon 에 insert 하는 통합 테스트는 **실행 시 사용자 승인 필요**. 순수 테스트(모델 import·병합 규칙)는 승인 불필요.
- **파일 헤더** — 새 소스 파일 첫 줄은 한 줄 한국어 주석으로 역할 명시(CLAUDE.md 규칙 6).
- **한국어 문장** — 종결은 `.` `?` `!` 만(`:` 로 끝내지 않기).
- **커밋** — 논리 단위마다 semantic commit. `git add .` 금지 — 지정 파일만 스테이징(`.omc/`·`__pycache__` 제외). 커밋 메시지 끝에 `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
- **테스트 사용자** — Neon 테스트는 `SELECT id FROM users ORDER BY created_at LIMIT 1` 사용자를 재사용하고, 시작·종료에 해당 user_id 의 자기모델 행을 DELETE 하여 idempotent 유지(다른 사용자 데이터 불변).
- **범위** — SP-1은 저장·병합·읽기까지. 임베딩 직렬화·Sync/Chance 설명(SP-3)·대화 추출(SP-2)·폼 입력 UI 는 범위 밖.

---

### Task 1: 자기모델 ORM 2종 + 마이그레이션

**Files:**
- Create: `backend/domain/user_intelligence/models/bases/user_self_model.py`
- Create: `backend/domain/user_intelligence/models/bases/user_self_model_evidence.py`
- Modify: `backend/alembic/env.py` (모델 import 2줄 추가 — line 75 `UserPreference` import 다음)
- Create: `backend/alembic/versions/<autogen>_add_user_self_model.py` (autogenerate)
- Test: `backend/scripts/self_model_models_import_test.py`

**Interfaces:**
- Produces: ORM `UserSelfModel`(table `user_self_model`) · `UserSelfModelEvidence`(table `user_self_model_evidence`). 컬럼은 아래 코드 그대로. 후속 태스크가 이 테이블·컬럼명을 사용.

- [ ] **Step 1: import 검증 테스트 작성(DB 불필요)**

Create `backend/scripts/self_model_models_import_test.py`:
```python
# 자기모델 ORM import·테이블 메타 검증(무DB)

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SCHEDULER_ENABLED", "false")

from domain.user_intelligence.models.bases.user_self_model import UserSelfModel
from domain.user_intelligence.models.bases.user_self_model_evidence import UserSelfModelEvidence

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
    check("self_model 테이블명", UserSelfModel.__tablename__ == "user_self_model")
    cols = UserSelfModel.__table__.columns
    check("riasec nullable", cols["riasec"].nullable is True)
    check("source not null", cols["source"].nullable is False)
    ev = UserSelfModelEvidence.__table__
    check("evidence 테이블명", ev.name == "user_self_model_evidence")
    check("content not null", ev.columns["content"].nullable is False)
    check("is_sensitive not null", ev.columns["is_sensitive"].nullable is False)
    check("content_hash not null", ev.columns["content_hash"].nullable is False)
    check("dedup 유니크", any(c.name == "uq_self_model_evidence_dedup" for c in ev.constraints))
    print(f"\n결과: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(run())
```

- [ ] **Step 2: 실패 확인**

Run: `cd backend && python scripts/self_model_models_import_test.py`
Expected: FAIL — `ModuleNotFoundError: ... user_self_model`.

- [ ] **Step 3: `user_self_model.py` 작성**

Create `backend/domain/user_intelligence/models/bases/user_self_model.py`:
```python
# 사용자 자기모델(구조 척추) ORM — RIASEC·Big Five·자기서사(코치 추출/폼, 전부 nullable)

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from core.database import Base


class UserSelfModel(Base):
    __tablename__ = "user_self_model"
    __table_args__ = {
        "comment": "자기모델 구조 척추 — RIASEC·Big Five·자기서사(coach 추출/폼)"
    }

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", name="fk_user_self_model_user", ondelete="CASCADE"),
        primary_key=True,
    )
    # {"scores": {"R":0-100,"I":..,...}, "top_codes": ["I","A","S"]}
    riasec: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # {"openness":0-100,"conscientiousness":..,"extraversion":..,"agreeableness":..,"neuroticism":..}
    big_five: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    narrative_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 축별 신뢰도 {"riasec":0.0-1.0, "big_five":..}
    axis_confidence: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    source: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default="coach_extraction"
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
```

- [ ] **Step 4: `user_self_model_evidence.py` 작성**

Create `backend/domain/user_intelligence/models/bases/user_self_model_evidence.py`:
```python
# 자기모델 근거(호불호·제약·민감정보) ORM — append-only, content_hash dedup, 민감 격리 플래그

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from core.database import Base


class UserSelfModelEvidence(Base):
    __tablename__ = "user_self_model_evidence"
    __table_args__ = (
        UniqueConstraint("user_id", "content_hash", name="uq_self_model_evidence_dedup"),
        Index("ix_self_model_evidence_user", "user_id"),
        {"comment": "자기모델 근거 — 대화 추출 호불호·제약·민감정보(append-only, dedup)"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", name="fk_self_model_evidence_user", ondelete="CASCADE"),
        nullable=False,
    )
    dimension: Mapped[str] = mapped_column(String(30), nullable=False)
    polarity: Mapped[str | None] = mapped_column(String(10), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float | None] = mapped_column(Numeric(3, 2), nullable=True)
    is_sensitive: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    coach_session_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default="coach_extraction"
    )
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
```

- [ ] **Step 5: `alembic/env.py` 에 모델 등록**

Modify `backend/alembic/env.py` — line 75 `from domain.user_intelligence.models.bases.user_preference import UserPreference  # 성향·선호` 다음 줄에 추가:
```python
from domain.user_intelligence.models.bases.user_self_model import UserSelfModel  # 자기모델
from domain.user_intelligence.models.bases.user_self_model_evidence import (  # 자기모델 근거
    UserSelfModelEvidence,
)
```

- [ ] **Step 6: import 테스트 통과 확인(무DB)**

Run: `cd backend && python scripts/self_model_models_import_test.py`
Expected: PASS — 모든 항목, `PASS=8 FAIL=0`.

- [ ] **Step 7: 마이그레이션 자동생성**

Run: `cd backend && alembic heads`
Expected: 단일 head 확인(복수면 먼저 병합).

Run: `cd backend && alembic revision --autogenerate -m "add user_self_model and evidence"`
Expected: `backend/alembic/versions/<hash>_add_user_self_model_and_evidence.py` 생성.

- [ ] **Step 8: 생성 마이그레이션 검토**

생성 파일 `upgrade()` 에 다음이 있는지 확인(없으면 수기 보정):
- `op.create_table("user_self_model", ...)` — user_id PK+FK(ondelete CASCADE), riasec/big_five/axis_confidence JSONB nullable, narrative_summary Text nullable, source not null server_default, updated_at.
- `op.create_table("user_self_model_evidence", ...)` — id BigInteger PK autoincrement, user_id FK CASCADE not null, dimension/content not null, is_sensitive/content_hash not null, unique `uq_self_model_evidence_dedup(user_id, content_hash)`, index `ix_self_model_evidence_user`.
- `downgrade()` 는 두 테이블 drop(evidence 먼저).
무관한 테이블 변경(다른 모델 drift)이 섞였으면 제거.

- [ ] **Step 9: Neon 적용 (사용자 승인 필요)**

사용자 승인 후 Run: `cd backend && alembic upgrade head`
Expected: `Running upgrade ... -> <hash>`. 확인: `cd backend && python -c "import asyncio;from sqlalchemy import text;from core.database import AsyncSessionLocal;\nasync def m():\n async with AsyncSessionLocal() as s:\n  print((await s.execute(text(\"SELECT to_regclass('public.user_self_model'), to_regclass('public.user_self_model_evidence')\"))).first())\nasyncio.run(m())"`
Expected: `('user_self_model', 'user_self_model_evidence')`.

- [ ] **Step 10: 커밋**

```bash
git add backend/domain/user_intelligence/models/bases/user_self_model.py backend/domain/user_intelligence/models/bases/user_self_model_evidence.py backend/alembic/env.py backend/alembic/versions/<hash>_add_user_self_model_and_evidence.py backend/scripts/self_model_models_import_test.py
git commit -m "feat(self-model): 자기모델 2테이블 ORM + 마이그레이션 (SP-1 Task1)"
```

---

### Task 2: SelfModelRepository (upsert·append dedup·fetch)

**Files:**
- Create: `backend/domain/user_intelligence/hub/repositories/self_model_repository.py`
- Test: `backend/scripts/self_model_repository_test.py`

**Interfaces:**
- Consumes: Task 1 테이블 `user_self_model`·`user_self_model_evidence`.
- Produces:
  - `normalize_content(content: str) -> str`
  - `content_hash(dimension: str, polarity: str | None, content: str) -> str`
  - `SelfModelRepository(session)` with:
    - `async fetch_self_model(user_id: str) -> dict | None` (keys `riasec, big_five, narrative_summary, axis_confidence, source`)
    - `async write_self_model(user_id, riasec, big_five, narrative_summary, axis_confidence, source) -> None` (dumb overwrite upsert)
    - `async fetch_evidence(user_id: str, include_sensitive: bool = False) -> list[dict]` (keys `dimension, polarity, content, confidence, is_sensitive, source`)
    - `async append_evidence(user_id: str, items: list[dict], source: str) -> int` (dedup, 삽입 수 반환)

- [ ] **Step 1: 리포지토리 Neon 라운드트립 테스트 작성**

Create `backend/scripts/self_model_repository_test.py`:
```python
# 자기모델 리포지토리 Neon 라운드트립 — write/fetch·append dedup·민감 격리

from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SCHEDULER_ENABLED", "false")

from sqlalchemy import text

from core.database import AsyncSessionLocal
from domain.user_intelligence.hub.repositories.self_model_repository import (
    SelfModelRepository,
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


async def _uid(s) -> str:
    r = (await s.execute(text("SELECT id FROM users ORDER BY created_at LIMIT 1"))).first()
    if r is None:
        raise SystemExit("users 테이블이 비어 있습니다.")
    return str(r.id)


async def _cleanup(s, uid: str) -> None:
    await s.execute(text("DELETE FROM user_self_model_evidence WHERE user_id = CAST(:u AS UUID)"), {"u": uid})
    await s.execute(text("DELETE FROM user_self_model WHERE user_id = CAST(:u AS UUID)"), {"u": uid})
    await s.commit()


async def run() -> int:
    async with AsyncSessionLocal() as s:
        uid = await _uid(s)
        await _cleanup(s, uid)
        repo = SelfModelRepository(s)

        await repo.write_self_model(
            uid, {"scores": {"I": 80}, "top_codes": ["I"]}, None, "탐구형", {"riasec": 0.7}, "coach_extraction"
        )
        m = await repo.fetch_self_model(uid)
        check("write/fetch riasec", bool(m) and m["riasec"]["top_codes"] == ["I"], str(m))
        check("source 반영", bool(m) and m["source"] == "coach_extraction")

        items = [
            {"dimension": "like", "polarity": "like", "content": "발표에서 에너지를 얻는다", "confidence": 0.8},
            {"dimension": "like", "polarity": "like", "content": "발표에서  에너지를 얻는다"},  # 정규화 시 동일 → dedup
            {"dimension": "constraint", "content": "장거리 통근 불가", "is_sensitive": True},
        ]
        n = await repo.append_evidence(uid, items, "coach_extraction")
        check("dedup 삽입 2건", n == 2, str(n))
        n2 = await repo.append_evidence(uid, items, "coach_extraction")
        check("재삽입 dedup 0건", n2 == 0, str(n2))

        non_sensitive = await repo.fetch_evidence(uid, include_sensitive=False)
        check("비민감 fetch 는 constraint 제외", all(e["dimension"] != "constraint" for e in non_sensitive), str(non_sensitive))
        allev = await repo.fetch_evidence(uid, include_sensitive=True)
        check("include_sensitive 는 constraint 포함", any(e["dimension"] == "constraint" for e in allev))

        await _cleanup(s, uid)
    print(f"\n결과: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
```

- [ ] **Step 2: 실패 확인**

Run: `cd backend && python scripts/self_model_repository_test.py`
Expected: FAIL — `ModuleNotFoundError: ... self_model_repository`.

- [ ] **Step 3: 리포지토리 구현**

Create `backend/domain/user_intelligence/hub/repositories/self_model_repository.py`:
```python
# 자기모델 리포지토리 — 구조 척추 upsert·근거 append(dedup)·조회(민감 격리)

from __future__ import annotations

import hashlib
import json
import re

from sqlalchemy import text

from domain.auth.hub.repositories.base_repository import BaseRepository


def normalize_content(content: str) -> str:
    """근거 dedup 용 정규화 — 앞뒤 공백 제거·연속 공백 압축·소문자."""
    return re.sub(r"\s+", " ", (content or "").strip().lower())


def content_hash(dimension: str, polarity: str | None, content: str) -> str:
    """(dimension|polarity|정규화content) SHA-256 — 세션 간 중복 근거 방지 키."""
    basis = f"{dimension}|{polarity or ''}|{normalize_content(content)}"
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()


_FETCH_MODEL = text(
    """
    SELECT riasec, big_five, narrative_summary, axis_confidence, source
    FROM user_self_model WHERE user_id = CAST(:uid AS UUID)
    """
)

_WRITE_MODEL = text(
    """
    INSERT INTO user_self_model
        (user_id, riasec, big_five, narrative_summary, axis_confidence, source, updated_at)
    VALUES (CAST(:uid AS UUID), CAST(:riasec AS JSONB), CAST(:big_five AS JSONB),
            :narrative_summary, CAST(:axis_confidence AS JSONB), :source, now())
    ON CONFLICT (user_id) DO UPDATE SET
        riasec = EXCLUDED.riasec,
        big_five = EXCLUDED.big_five,
        narrative_summary = EXCLUDED.narrative_summary,
        axis_confidence = EXCLUDED.axis_confidence,
        source = EXCLUDED.source,
        updated_at = now()
    """
)

_FETCH_EVIDENCE = text(
    """
    SELECT dimension, polarity, content, confidence, is_sensitive, source
    FROM user_self_model_evidence
    WHERE user_id = CAST(:uid AS UUID)
      AND (:include_sensitive OR is_sensitive = false)
    ORDER BY created_at DESC, id DESC
    """
)

_INSERT_EVIDENCE = text(
    """
    INSERT INTO user_self_model_evidence
        (user_id, dimension, polarity, content, confidence, is_sensitive,
         content_hash, coach_session_ref, source, created_at)
    VALUES (CAST(:uid AS UUID), :dimension, :polarity, :content, :confidence, :is_sensitive,
            :content_hash, :coach_session_ref, :source, now())
    ON CONFLICT (user_id, content_hash) DO NOTHING
    """
)


class SelfModelRepository(BaseRepository):
    async def fetch_self_model(self, user_id: str) -> dict | None:
        r = (await self.session.execute(_FETCH_MODEL, {"uid": user_id})).first()
        if r is None:
            return None
        return {
            "riasec": r.riasec,
            "big_five": r.big_five,
            "narrative_summary": r.narrative_summary,
            "axis_confidence": r.axis_confidence,
            "source": r.source,
        }

    async def write_self_model(
        self, user_id, riasec, big_five, narrative_summary, axis_confidence, source
    ) -> None:
        await self.session.execute(
            _WRITE_MODEL,
            {
                "uid": user_id,
                "riasec": json.dumps(riasec) if riasec is not None else None,
                "big_five": json.dumps(big_five) if big_five is not None else None,
                "narrative_summary": narrative_summary,
                "axis_confidence": json.dumps(axis_confidence) if axis_confidence is not None else None,
                "source": source,
            },
        )
        await self.session.commit()

    async def fetch_evidence(self, user_id: str, include_sensitive: bool = False) -> list[dict]:
        rows = (
            await self.session.execute(
                _FETCH_EVIDENCE, {"uid": user_id, "include_sensitive": include_sensitive}
            )
        ).all()
        return [
            {
                "dimension": r.dimension,
                "polarity": r.polarity,
                "content": r.content,
                "confidence": float(r.confidence) if r.confidence is not None else None,
                "is_sensitive": r.is_sensitive,
                "source": r.source,
            }
            for r in rows
        ]

    async def append_evidence(self, user_id: str, items: list[dict], source: str) -> int:
        inserted = 0
        for it in items:
            dim = it["dimension"]
            pol = it.get("polarity")
            content = it["content"]
            res = await self.session.execute(
                _INSERT_EVIDENCE,
                {
                    "uid": user_id,
                    "dimension": dim,
                    "polarity": pol,
                    "content": content,
                    "confidence": it.get("confidence"),
                    "is_sensitive": bool(it.get("is_sensitive", False)),
                    "content_hash": content_hash(dim, pol, content),
                    "coach_session_ref": it.get("coach_session_ref"),
                    "source": source,
                },
            )
            inserted += 1 if (res.rowcount or 0) > 0 else 0
        await self.session.commit()
        return inserted
```

- [ ] **Step 4: 테스트 통과 확인 (Neon 쓰기 — 사용자 승인 필요)**

Run: `cd backend && python scripts/self_model_repository_test.py`
Expected: PASS — `PASS=6 FAIL=0`.

- [ ] **Step 5: 커밋**

```bash
git add backend/domain/user_intelligence/hub/repositories/self_model_repository.py backend/scripts/self_model_repository_test.py
git commit -m "feat(self-model): SelfModelRepository — upsert·append dedup·민감 격리 조회 (SP-1 Task2)"
```

---

### Task 3: SelfModelService (순수 병합 규칙 + 조회 셰이핑)

**Files:**
- Create: `backend/domain/user_intelligence/hub/services/self_model_service.py`
- Test: `backend/scripts/self_model_merge_test.py`

**Interfaces:**
- Consumes: `SelfModelRepository`(Task 2).
- Produces:
  - `merge_structured(existing: dict | None, incoming: dict, source: str) -> dict` (순수 — 반환 keys `riasec, big_five, narrative_summary, axis_confidence, source`)
  - `SelfModelService(db)` with:
    - `async get_self_model(user_id: str, include_sensitive: bool = False) -> dict` (camelCase: `riasec, bigFive, narrativeSummary, axisConfidence, source, evidence`)
    - `async upsert_structured(user_id: str, incoming: dict, source: str) -> dict`
    - `async append_evidence(user_id: str, items: list[dict], source: str) -> int`

- [ ] **Step 1: 병합 규칙 순수 단위 테스트 작성(무DB)**

Create `backend/scripts/self_model_merge_test.py`:
```python
# 자기모델 병합 규칙 순수 단위 테스트 — user_form 우위·confidence 게이팅·빈 축 채움

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SCHEDULER_ENABLED", "false")

from domain.user_intelligence.hub.services.self_model_service import merge_structured

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
    # 1. 빈 상태 + coach 고신뢰 → 기록
    r = merge_structured(None, {"riasec": {"top_codes": ["I"]}, "axis_confidence": {"riasec": 0.7}}, "coach_extraction")
    check("coach 고신뢰 기록", r["riasec"] == {"top_codes": ["I"]})
    check("source coach", r["source"] == "coach_extraction")

    # 2. coach 저신뢰 → 보류(값 미기록, 신뢰도만 반영)
    r = merge_structured(None, {"riasec": {"top_codes": ["I"]}, "axis_confidence": {"riasec": 0.2}}, "coach_extraction")
    check("저신뢰 값 보류", r["riasec"] is None)
    check("저신뢰 신뢰도 반영", (r["axis_confidence"] or {}).get("riasec") == 0.2)

    # 3. user_form 우위 — 기존 user_form 을 coach 가 못 덮음
    existing = {"riasec": {"top_codes": ["A"]}, "source": "user_form", "axis_confidence": {"riasec": 1.0}}
    r = merge_structured(existing, {"riasec": {"top_codes": ["I"]}, "axis_confidence": {"riasec": 0.9}}, "coach_extraction")
    check("user_form 우위 유지", r["riasec"] == {"top_codes": ["A"]})
    check("source user_form 유지", r["source"] == "user_form")

    # 4. user_form 은 기존 coach 를 덮음
    existing = {"riasec": {"top_codes": ["A"]}, "source": "coach_extraction"}
    r = merge_structured(existing, {"riasec": {"top_codes": ["I"]}}, "user_form")
    check("user_form 덮어쓰기", r["riasec"] == {"top_codes": ["I"]})
    check("source→user_form", r["source"] == "user_form")

    # 5. 빈 축만 coach 채움 (기존 user_form 은 riasec 만, big_five 없음)
    existing = {"riasec": {"top_codes": ["A"]}, "source": "user_form"}
    r = merge_structured(existing, {"big_five": {"openness": 70}, "axis_confidence": {"big_five": 0.8}}, "coach_extraction")
    check("빈 축 coach 채움", r["big_five"] == {"openness": 70})
    check("기존 riasec 보존", r["riasec"] == {"top_codes": ["A"]})

    print(f"\n결과: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(run())
```

- [ ] **Step 2: 실패 확인**

Run: `cd backend && python scripts/self_model_merge_test.py`
Expected: FAIL — `ModuleNotFoundError: ... self_model_service`.

- [ ] **Step 3: 서비스 구현**

Create `backend/domain/user_intelligence/hub/services/self_model_service.py`:
```python
# 자기모델 서비스 — 병합 규칙(user_form 우위·confidence 게이팅) + 조회 셰이핑

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from domain.user_intelligence.hub.repositories.self_model_repository import SelfModelRepository

CONFIDENCE_THRESHOLD = 0.40
SOURCE_USER_FORM = "user_form"
SOURCE_COACH = "coach_extraction"
_AXES = ("riasec", "big_five", "narrative_summary")


def _incoming_conf(incoming: dict, axis: str, source: str) -> float:
    conf = (incoming.get("axis_confidence") or {}).get(axis)
    if conf is not None:
        return float(conf)
    return 1.0 if source == SOURCE_USER_FORM else 0.0


def merge_structured(existing: dict | None, incoming: dict, source: str) -> dict:
    """구조 축 병합(순수). user_form 우위·빈 축만 coach 채움·저confidence 보류.

    existing: 기존 행 dict|None. incoming: {riasec, big_five, narrative_summary, axis_confidence}.
    반환: 저장할 최종 행 dict(riasec, big_five, narrative_summary, axis_confidence, source).
    """
    base = dict(existing or {})
    existing_source = base.get("source")
    result = {axis: base.get(axis) for axis in _AXES}
    merged_conf = dict(base.get("axis_confidence") or {})

    for axis in _AXES:
        inc = incoming.get(axis)
        if inc is None:
            continue
        if source == SOURCE_USER_FORM:
            result[axis] = inc  # 사용자 명시 입력 최우선
            merged_conf[axis] = 1.0
            continue
        # coach_extraction
        if existing_source == SOURCE_USER_FORM and base.get(axis) is not None:
            continue  # user_form 우위 — 덮어쓰지 않음
        conf = _incoming_conf(incoming, axis, source)
        merged_conf[axis] = conf
        if conf < CONFIDENCE_THRESHOLD:
            continue  # 저신뢰 보류 — 값 미기록, 신뢰도만 반영
        result[axis] = inc

    result["source"] = (
        SOURCE_USER_FORM
        if source == SOURCE_USER_FORM or existing_source == SOURCE_USER_FORM
        else SOURCE_COACH
    )
    result["axis_confidence"] = merged_conf or None
    return result


class SelfModelService:
    def __init__(self, db: AsyncSession):
        self.repo = SelfModelRepository(db)

    async def get_self_model(self, user_id: str, include_sensitive: bool = False) -> dict:
        """구조 축 + 근거(기본 비민감). 없으면 null 기본값."""
        model = await self.repo.fetch_self_model(user_id)
        evidence = await self.repo.fetch_evidence(user_id, include_sensitive=include_sensitive)
        if model is None:
            return {
                "riasec": None,
                "bigFive": None,
                "narrativeSummary": None,
                "axisConfidence": None,
                "source": None,
                "evidence": evidence,
            }
        return {
            "riasec": model["riasec"],
            "bigFive": model["big_five"],
            "narrativeSummary": model["narrative_summary"],
            "axisConfidence": model["axis_confidence"],
            "source": model["source"],
            "evidence": evidence,
        }

    async def upsert_structured(self, user_id: str, incoming: dict, source: str) -> dict:
        existing = await self.repo.fetch_self_model(user_id)
        merged = merge_structured(existing, incoming, source)
        await self.repo.write_self_model(
            user_id,
            riasec=merged["riasec"],
            big_five=merged["big_five"],
            narrative_summary=merged["narrative_summary"],
            axis_confidence=merged["axis_confidence"],
            source=merged["source"],
        )
        return merged

    async def append_evidence(self, user_id: str, items: list[dict], source: str) -> int:
        return await self.repo.append_evidence(user_id, items, source)
```

- [ ] **Step 4: 병합 테스트 통과 확인(무DB)**

Run: `cd backend && python scripts/self_model_merge_test.py`
Expected: PASS — `PASS=10 FAIL=0`.

- [ ] **Step 5: 커밋**

```bash
git add backend/domain/user_intelligence/hub/services/self_model_service.py backend/scripts/self_model_merge_test.py
git commit -m "feat(self-model): SelfModelService — 병합 규칙(user_form 우위·게이팅)·조회 셰이핑 (SP-1 Task3)"
```

---

### Task 4: 읽기 API `GET /api/user/self-model`

**Files:**
- Modify: `backend/api/v1/user/user_routor.py` (import + 라우트 추가)
- Test: `backend/scripts/self_model_endpoint_test.py`

**Interfaces:**
- Consumes: `SelfModelService`(Task 3). user_routor 기존 의존성 `get_current_user_id`·`get_db`.
- Produces: `GET /api/user/self-model` → `{"success": True, "selfModel": {...}}`(camelCase, 비민감 근거). 무토큰 401.

- [ ] **Step 1: 엔드포인트 테스트 작성**

Create `backend/scripts/self_model_endpoint_test.py`:
```python
# 자기모델 엔드포인트 — GET 라운드트립·camelCase·민감 제외·무토큰 401

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
from domain.user_intelligence.hub.repositories.self_model_repository import SelfModelRepository

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
        raise SystemExit("users 테이블이 비어 있습니다.")
    return str(r.id)


async def _cleanup(s, uid: str) -> None:
    await s.execute(text("DELETE FROM user_self_model_evidence WHERE user_id = CAST(:u AS UUID)"), {"u": uid})
    await s.execute(text("DELETE FROM user_self_model WHERE user_id = CAST(:u AS UUID)"), {"u": uid})
    await s.commit()


async def run() -> int:
    from main import app

    async with AsyncSessionLocal() as s:
        uid = await _uid(s)
        await _cleanup(s, uid)
        repo = SelfModelRepository(s)
        await repo.write_self_model(uid, {"top_codes": ["I"]}, None, "탐구형", {"riasec": 0.7}, "coach_extraction")
        await repo.append_evidence(
            uid,
            [
                {"dimension": "like", "content": "발표를 좋아함"},
                {"dimension": "constraint", "content": "통근 제약", "is_sensitive": True},
            ],
            "coach_extraction",
        )

    token = JWTService().generate_token(uid, provider="test", email="sm@test.local")
    headers = {"Authorization": f"Bearer {token}"}
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/api/user/self-model", headers=headers)
        check("GET 200", r.status_code == 200, str(r.status_code))
        sm = r.json().get("selfModel", {})
        check("riasec 반영", sm.get("riasec") == {"top_codes": ["I"]}, str(sm.get("riasec")))
        check("narrativeSummary camelCase", sm.get("narrativeSummary") == "탐구형")
        ev = sm.get("evidence", [])
        check("비민감 근거 포함", any(e["dimension"] == "like" for e in ev))
        check("민감 근거 제외", all(e["dimension"] != "constraint" for e in ev), str(ev))
        r2 = await c.get("/api/user/self-model")
        check("무토큰 401", r2.status_code == 401, str(r2.status_code))

    async with AsyncSessionLocal() as s:
        await _cleanup(s, uid)
    print(f"\n결과: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
```

- [ ] **Step 2: 실패 확인**

Run: `cd backend && python scripts/self_model_endpoint_test.py`
Expected: FAIL — `GET 200` 항목이 404(라우트 없음).

- [ ] **Step 3: user_routor 에 라우트 추가**

Modify `backend/api/v1/user/user_routor.py` — import 블록(line 13 `from domain.auth.hub.services.user_service import UserService` 다음)에 추가:
```python
from domain.user_intelligence.hub.services.self_model_service import SelfModelService
```
그리고 파일 끝(`upsert_basic_profile` 라우트 다음)에 라우트 추가:
```python
@router.get("/self-model")
async def get_self_model(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """현재 사용자 자기모델(구조 척추 + 비민감 근거) — 없으면 null 기본값."""
    try:
        model = await SelfModelService(db).get_self_model(user_id, include_sensitive=False)
        return {"success": True, "selfModel": model}
    except Exception as e:
        logger.error(f"자기모델 조회 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"자기모델 조회 실패: {str(e)}")
```

- [ ] **Step 4: 테스트 통과 확인 (Neon 쓰기 — 사용자 승인 필요)**

Run: `cd backend && python scripts/self_model_endpoint_test.py`
Expected: PASS — `PASS=6 FAIL=0`.

- [ ] **Step 5: 커밋**

```bash
git add backend/api/v1/user/user_routor.py backend/scripts/self_model_endpoint_test.py
git commit -m "feat(self-model): GET /api/user/self-model 읽기 API (SP-1 Task4)"
```

---

## 마무리(전 태스크 완료 후)

- [ ] **전체 회귀** — `cd backend && python scripts/self_model_models_import_test.py && python scripts/self_model_merge_test.py && python scripts/self_model_repository_test.py && python scripts/self_model_endpoint_test.py` 전부 PASS.
- [ ] **감사 기록** — `backend/domain/user_intelligence/docs/audit_trail.md` 최상단에 SP-1 항목 추가(CLAUDE.md 형식). **경로 승인 후 작성.**
- [ ] **Codex 리뷰** — 커밋 범위(`--base <SP-1 직전 ref> --scope branch`) Codex 리뷰. Critical/Important 조치 후 재리뷰.
- [ ] **다음 SP** — SP-2(대화 추출 엔진)는 `SelfModelService.upsert_structured`·`append_evidence`(`source='coach_extraction'`)를 재사용. 별도 spec/plan.

## Self-Review (플랜 작성자 체크)

- **스펙 커버리지** — spec §4(2테이블)=Task1, §5(병합 규칙)=Task3 `merge_structured`+Task2 dedup/격리, §7 읽기 API=Task4, §8 성공기준 1(테이블)=Task1 Step9·2(병합)=Task3·3(GET 401/민감)=Task4·4(테스트)=전 태스크. §6(임베딩)은 SP-3 범위로 명시 제외 — 커버 갭 없음.
- **플레이스홀더** — 없음(전 스텝 실제 코드·명령·기대값 포함).
- **타입 일관성** — `write_self_model`/`fetch_self_model` 키(`riasec, big_five, narrative_summary, axis_confidence, source`)가 Task2 정의와 Task3 `merge_structured` 반환·`get_self_model` 셰이핑에서 일치. `content_hash(dimension, polarity, content)` 시그니처가 Task2 정의·repo 내부 호출·테스트에서 일치. 서비스 camelCase(`bigFive, narrativeSummary, axisConfidence`)는 Task4 테스트 기대와 일치.
