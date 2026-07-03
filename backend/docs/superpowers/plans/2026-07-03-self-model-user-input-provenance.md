# SP-7② 자기모델 사용자 입력 + 축별 provenance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 사용자가 AI의 자기모델 판단을 축당 3단계(낮음·중간·높음)+AI판단으로 교정하고, 출처를 축별(`axis_source`)로 기록해 사용자 확정 축을 코치 추출이 잠식하지 않게 한다(P2 근본 해소).

**Architecture:** 스펙 `backend/docs/superpowers/specs/2026-07-03-self-model-user-input-provenance-design.md` 기준. 2태스크 — (1) 백엔드(`axis_source` 마이그레이션·repo·merge 축별 가드·`apply_user_edits`·`PUT` 엔드포인트·`get_self_model` axisSource), (2) 프론트(편집 모달). provenance는 provenance-unit(riasec/big_five/narrative) 단위 — 축을 편집하면 그 축 전체가 user_form.

**Tech Stack:** FastAPI · SQLAlchemy 2.0 async(text SQL) · Alembic · PostgreSQL(Neon) · Next.js/TS/React 19 · TanStack Query.

## Global Constraints

- 한국어 문장 종결 `.` `?` `!` 만. 새 소스 파일 첫 줄 한 줄 한국어 역할 주석.
- 커밋 논리 단위, `git add .` 금지(파일 명시, `.omc/`·`.superpowers/`·`__pycache__` 제외). 커밋 메시지 끝 `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>` 트레일러.
- Alembic 은 `backend/` 에서 `alembic` CLI 직접. **`alembic upgrade head`(Neon)는 사용자 승인 후에만.** 마이그레이션은 단순 add_column 1개 — 수기 작성(무관 drift 회피).
- 백엔드 테스트 `backend/scripts/*_test.py`(PASS/FAIL check). 통합은 dev Neon — 시드 cleanup(특히 기존 사용자 컬럼 덮어쓸 땐 원값 저장·복원).
- 프론트 `pnpm exec tsc --noEmit` 0 에러.
- **레벨→점수**: `low=25, mid=50, high=75`. **신경성은 정서안정성으로 입력받아 canonical `N=100−안정성점수` 저장**(SP-5 정책). RIASEC 6 `R I A S E C`·Big Five 5 `O C E A N`.
- `axis_source`는 **user_form 축만** 키로 담는다(`{"riasec":"user_form"}`). 없는 축=코치 소유. auto=키 제거.
- `riasec.top_codes` 계약 유지(SP-3 임베딩·설명). 사용자 확정 축도 top_codes 파생.

---

### Task 1: 백엔드 — axis_source provenance + 사용자 편집 쓰기

**Files:**
- Modify: `backend/domain/user_intelligence/models/bases/user_self_model.py` (axis_source 컬럼)
- Create: `backend/alembic/versions/<new>_add_axis_source_to_self_model.py`
- Modify: `backend/domain/user_intelligence/hub/repositories/self_model_repository.py` (fetch/write axis_source)
- Modify: `backend/domain/user_intelligence/hub/services/self_model_service.py` (merge 축별 가드·`apply_user_edits`·`get_self_model` axisSource)
- Modify: `backend/api/v1/user/user_routor.py` (`PUT /self-model`)
- Modify: `backend/alembic/env.py` (모델 이미 등록됐으면 불필요 — 확인만)
- Test(신규): `backend/scripts/self_model_user_edits_test.py` (Neon 통합)
- Modify(테스트): `backend/scripts/self_model_merge_test.py` (축별 가드 회귀)

**Interfaces:**
- Produces:
  - `user_self_model.axis_source JSONB NULL` 컬럼. `fetch_self_model`/`write_self_model` 가 `axis_source` 포함.
  - `merge_structured`: 잠식 가드가 `axis_source.get(axis)=="user_form"` 기준. `result["axis_source"]` = 기존 보존.
  - `SelfModelService.apply_user_edits(user_id, edits: dict) -> dict` — 편집 적용 후 `get_self_model` 반환.
  - `SelfModelService.get_self_model` 반환에 `axisSource`.
  - 상수 `LEVEL_SCORE = {"low":25,"mid":50,"high":75}`. `PUT /api/user/self-model`.

- [ ] **Step 1: ORM 컬럼 추가**

`user_self_model.py` 의 `axis_confidence` 아래에 추가.

```python
    # 축별 출처 — user_form 으로 확정한 축만 기록 {"riasec":"user_form"}. 없으면 코치 소유.
    axis_source: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
```

- [ ] **Step 2: 수기 마이그레이션 작성**

Run: `alembic heads`(cwd `backend/`) 로 현재 head 확인(예 `59a2f51cc892`). 그 뒤 `alembic revision -m "add axis_source to self model"` 로 빈 리비전 생성. `down_revision` 이 현재 head 인지 확인하고 body 작성.

```python
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


def upgrade() -> None:
    op.add_column(
        "user_self_model",
        sa.Column("axis_source", postgresql.JSONB, nullable=True,
                  comment="축별 출처 — user_form 으로 확정한 축만 기록"),
    )


def downgrade() -> None:
    op.drop_column("user_self_model", "axis_source")
```

- [ ] **Step 3: 마이그레이션 적용 (사용자 승인 게이트)**

**사용자 승인 후** 실행. Run: `alembic upgrade head` → 에러 없이 완료. `alembic current` 가 새 revision.

- [ ] **Step 4: repo — axis_source read/write**

`self_model_repository.py`:
- `_FETCH_MODEL` SELECT 에 `axis_source` 추가: `SELECT riasec, big_five, narrative_summary, axis_confidence, source, axis_source ...`.
- `fetch_self_model` 반환 dict 에 `"axis_source": r.axis_source`.
- `_WRITE_MODEL` 컬럼·VALUES·SET 에 axis_source 추가:
```python
_WRITE_MODEL = text(
    """
    INSERT INTO user_self_model
        (user_id, riasec, big_five, narrative_summary, axis_confidence, source, axis_source, updated_at)
    VALUES (CAST(:uid AS UUID), CAST(:riasec AS JSONB), CAST(:big_five AS JSONB),
            :narrative_summary, CAST(:axis_confidence AS JSONB), :source, CAST(:axis_source AS JSONB), now())
    ON CONFLICT (user_id) DO UPDATE SET
        riasec = EXCLUDED.riasec,
        big_five = EXCLUDED.big_five,
        narrative_summary = EXCLUDED.narrative_summary,
        axis_confidence = EXCLUDED.axis_confidence,
        source = EXCLUDED.source,
        axis_source = EXCLUDED.axis_source,
        updated_at = now()
    """
)
```
- `write_self_model` 시그니처에 `axis_source=None` 추가, 파라미터에 `"axis_source": json.dumps(axis_source) if axis_source is not None else None`.

- [ ] **Step 5: merge 축별 가드 실패 테스트**

`self_model_merge_test.py` 에 케이스 추가: existing 이 `axis_source={"riasec":"user_form"}` + riasec 값 보유, big_five 는 코치 소유일 때, incoming 이 riasec·big_five 둘 다 window_scores 로 오면 → **riasec 은 보존(blend 안 됨), big_five 는 blend** 됨을 단정. `merge_structured` 반환 검사.

```python
    # 축별 provenance — riasec 만 user_form 고정, big_five 는 코치 소유
    existing_axis = {
        "riasec": {"scores": {c: 60 for c in "RIASEC"}, "raw": {c: 60 for c in "RIASEC"},
                   "weights": {c: 4 for c in "RIASEC"}, "top_codes": ["R"]},
        "big_five": {"scores": {c: 55 for c in ("O", "C", "E", "A", "N")},
                     "raw": {c: 55 for c in ("O", "C", "E", "A", "N")},
                     "weights": {c: 1 for c in ("O", "C", "E", "A", "N")}},
        "narrative_summary": None,
        "axis_confidence": {"riasec": 1.0, "big_five": 0.2},
        "axis_source": {"riasec": "user_form"},
        "source": "consult_extraction",
    }
    incoming_both = {
        "riasec": {"window_scores": {c: 90 for c in "RIASEC"}, "window_conf": {c: 0.9 for c in "RIASEC"}},
        "big_five": {"window_scores": {c: 90 for c in ("O", "C", "E", "A", "N")}, "window_conf": {c: 0.9 for c in ("O", "C", "E", "A", "N")}},
        "narrative_summary": None,
        "axis_confidence": {"riasec": 0.9, "big_five": 0.9},
    }
    m = merge_structured(existing_axis, incoming_both, "consult_extraction")
    check("user_form riasec 보존", m["riasec"] == existing_axis["riasec"], str(m["riasec"]))
    check("코치 big_five 는 blend(상승)", m["big_five"]["scores"]["O"] > 55, str(m["big_five"]["scores"]))
    check("axis_source 보존", m["axis_source"] == {"riasec": "user_form"}, str(m.get("axis_source")))
```

Run: `python scripts/self_model_merge_test.py`
Expected: 새 단정 FAIL(가드가 아직 행 source 기준).

- [ ] **Step 6: merge 축별 가드 구현**

`self_model_service.py` `merge_structured`:
- 헬퍼 추가(파일 상단, `merge_structured` 위):
```python
def _axis_is_user_form(base: dict, axis: str) -> bool:
    """해당 축이 사용자 확정(user_form)인지 — 축별 provenance."""
    src = base.get("axis_source")
    return isinstance(src, dict) and src.get(axis) == SOURCE_USER_FORM
```
- 두 곳의 `if existing_source == SOURCE_USER_FORM and base.get(axis) is not None:` (blend 분기·일반 분기)를 `if _axis_is_user_form(base, axis):` 로 교체.
- `return` 직전에 `result["axis_source"] = base.get("axis_source")` 추가(추출은 provenance 불변).
- `upsert_structured` 의 `write_self_model(...)` 호출에 `axis_source=merged.get("axis_source")` 추가.

- [ ] **Step 7: 가드 테스트 통과 확인**

Run: `python scripts/self_model_merge_test.py`
Expected: `FAIL=0`.

- [ ] **Step 8: `apply_user_edits` + get_self_model axisSource + 상수**

`self_model_service.py` 상단 임포트에 `from domain.user_intelligence.hub.services.riasec_scoring import BIGFIVE_CODES, BIGFIVE_SHRINK_K, RIASEC_CODES, SHRINK_K, TOP_MIN` 추가. 상수·헬퍼·메서드 추가.

```python
LEVEL_SCORE = {"low": 25, "mid": 50, "high": 75}


def _user_form_riasec(levels: dict) -> dict:
    """레벨(낮음/중간/높음)→점수로 사용자 확정 RIASEC 구성. top_codes 파생·완전표현 가중."""
    scores = {c: LEVEL_SCORE.get(levels.get(c), 50) for c in RIASEC_CODES}
    ranked = sorted(RIASEC_CODES, key=lambda c: scores[c], reverse=True)
    top_codes = [c for c in ranked if scores[c] > TOP_MIN][:2]
    return {"scores": scores, "raw": dict(scores),
            "weights": {c: SHRINK_K for c in RIASEC_CODES}, "top_codes": top_codes}


def _user_form_big_five(levels: dict) -> dict:
    """레벨→점수로 사용자 확정 Big Five 구성. 신경성은 정서안정성 입력→canonical N=100-안정성."""
    scores = {c: LEVEL_SCORE.get(levels.get(c), 50) for c in ("O", "C", "E", "A")}
    scores["N"] = 100 - LEVEL_SCORE.get(levels.get("stability"), 50)
    return {"scores": scores, "raw": dict(scores),
            "weights": {c: BIGFIVE_SHRINK_K for c in BIGFIVE_CODES}}
```

`SelfModelService` 에 메서드 추가.

```python
    async def apply_user_edits(self, user_id: str, edits: dict) -> dict:
        """사용자 편집을 축별로 적용한다. 축 값 설정 시 user_form 고정, 'auto' 는 코치에게 반환."""
        existing = await self.repo.fetch_self_model(user_id) or {}
        riasec = existing.get("riasec")
        big_five = existing.get("big_five")
        narrative = existing.get("narrative_summary")
        axis_source = dict(existing.get("axis_source") or {})

        r = edits.get("riasec")
        if r == "auto":
            axis_source.pop("riasec", None)
        elif isinstance(r, dict) and isinstance(r.get("levels"), dict):
            riasec = _user_form_riasec(r["levels"])
            axis_source["riasec"] = SOURCE_USER_FORM

        b = edits.get("big_five")
        if b == "auto":
            axis_source.pop("big_five", None)
        elif isinstance(b, dict) and isinstance(b.get("levels"), dict):
            big_five = _user_form_big_five(b["levels"])
            axis_source["big_five"] = SOURCE_USER_FORM

        n = edits.get("narrative")
        if n == "auto":
            axis_source.pop("narrative_summary", None)
        elif isinstance(n, str):
            narrative = n.strip()[:500] or None
            if narrative is not None:
                axis_source["narrative_summary"] = SOURCE_USER_FORM
            else:
                axis_source.pop("narrative_summary", None)

        await self.repo.write_self_model(
            user_id, riasec=riasec, big_five=big_five, narrative_summary=narrative,
            axis_confidence=existing.get("axis_confidence"),
            source=existing.get("source") or SOURCE_COACH,
            axis_source=axis_source or None,
        )
        return await self.get_self_model(user_id)
```

`get_self_model` 반환 두 곳(None 분기·정상 분기)에 `"axisSource"` 추가 — None 분기 `"axisSource": None`, 정상 분기 `"axisSource": model.get("axis_source")`.

- [ ] **Step 9: PUT 엔드포인트**

`api/v1/user/user_routor.py` 에 추가(GET /self-model 아래). 상단에 `from pydantic import BaseModel` 가 없으면 확인·추가.

```python
class SelfModelEditRequest(BaseModel):
    riasec: dict | str | None = None
    big_five: dict | str | None = None
    narrative: str | None = None


@router.put("/self-model")
async def update_self_model(
    request: SelfModelEditRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """사용자 자기모델 편집 — 축별 3단계/AI판단. 확정 축은 코치 추출이 잠식하지 않는다."""
    try:
        model = await SelfModelService(db).apply_user_edits(user_id, request.model_dump())
        return {"success": True, "selfModel": model}
    except Exception as e:
        logger.error(f"자기모델 편집 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"자기모델 편집 실패: {str(e)}")
```

- [ ] **Step 10: 통합 테스트 작성 (Neon)**

`backend/scripts/self_model_user_edits_test.py` 생성. 기존 사용자 자기모델을 **원값 저장·복원**하며(데이터 파괴 방지), `apply_user_edits` 를 검증.

```python
# 사용자 자기모델 편집 — 레벨→점수·정서안정성 flip·축별 provenance·auto 해제 (Neon 통합).

from __future__ import annotations

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SCHEDULER_ENABLED", "false")

from sqlalchemy import text

from core.database import AsyncSessionLocal
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


async def run() -> int:
    async with AsyncSessionLocal() as s:
        uid = str((await s.execute(text("SELECT id FROM users ORDER BY created_at LIMIT 1"))).scalar_one())
        prev = (await s.execute(text(
            "SELECT riasec, big_five, narrative_summary, axis_confidence, source, axis_source "
            "FROM user_self_model WHERE user_id = CAST(:u AS UUID)"), {"u": uid})).first()
        row_existed = prev is not None
        snap = dict(prev._mapping) if prev is not None else None

        svc = SelfModelService(s)

        # 편집 — riasec 확정(I 높음), big_five 확정(정서안정성 높음 → N 낮음), 서사
        model = await svc.apply_user_edits(uid, {
            "riasec": {"levels": {"R": "low", "I": "high", "A": "mid", "S": "low", "E": "mid", "C": "low"}},
            "big_five": {"levels": {"O": "high", "C": "high", "E": "mid", "A": "mid", "stability": "high"}},
            "narrative": "탐구를 좋아하는 빌더",
        })
        check("riasec I 점수 75", model["riasec"]["scores"]["I"] == 75, str(model["riasec"]["scores"]))
        check("riasec top_codes I", "I" in (model["riasec"]["top_codes"] or []), str(model["riasec"]["top_codes"]))
        check("정서안정성 flip → N 25", model["bigFive"]["scores"]["N"] == 25, str(model["bigFive"]["scores"]))
        check("big_five O 75", model["bigFive"]["scores"]["O"] == 75)
        check("서사 반영", model["narrativeSummary"] == "탐구를 좋아하는 빌더")
        check("axisSource riasec·big_five·narrative user_form",
              (model["axisSource"] or {}).get("riasec") == "user_form"
              and (model["axisSource"] or {}).get("big_five") == "user_form"
              and (model["axisSource"] or {}).get("narrative_summary") == "user_form", str(model["axisSource"]))

        # user_form 축은 코치 추출이 잠식 안 함
        from domain.user_intelligence.hub.services.self_model_service import merge_structured
        existing = await svc.repo.fetch_self_model(uid)
        merged = merge_structured(existing, {
            "riasec": {"window_scores": {c: 95 for c in "RIASEC"}, "window_conf": {c: 0.9 for c in "RIASEC"}},
            "big_five": None, "narrative_summary": None,
            "axis_confidence": {"riasec": 0.9},
        }, "consult_extraction")
        check("추출이 user_form riasec 보존", merged["riasec"]["scores"]["I"] == 75, str(merged["riasec"]["scores"]))

        # auto — riasec 을 AI 에게 반환
        model2 = await svc.apply_user_edits(uid, {"riasec": "auto"})
        check("auto → axisSource riasec 제거", "riasec" not in (model2["axisSource"] or {}), str(model2["axisSource"]))

        # 원상 복원(데이터 파괴 방지)
        if row_existed:
            await s.execute(text(
                "UPDATE user_self_model SET riasec = CAST(:r AS JSONB), big_five = CAST(:b AS JSONB), "
                "narrative_summary = :n, axis_confidence = CAST(:ac AS JSONB), source = :src, "
                "axis_source = CAST(:asrc AS JSONB), updated_at = now() WHERE user_id = CAST(:u AS UUID)"
            ), {"u": uid,
                "r": json.dumps(snap["riasec"]) if snap["riasec"] is not None else None,
                "b": json.dumps(snap["big_five"]) if snap["big_five"] is not None else None,
                "n": snap["narrative_summary"],
                "ac": json.dumps(snap["axis_confidence"]) if snap["axis_confidence"] is not None else None,
                "src": snap["source"],
                "asrc": json.dumps(snap["axis_source"]) if snap["axis_source"] is not None else None})
        else:
            await s.execute(text("DELETE FROM user_self_model WHERE user_id = CAST(:u AS UUID)"), {"u": uid})
        await s.commit()

    print(f"\n결과: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
```

- [ ] **Step 11: 통합·회귀 실행**

Run: `python scripts/self_model_user_edits_test.py`
Expected: `결과: PASS=8 FAIL=0`.

Run: `python scripts/self_model_merge_test.py; python scripts/self_model_repository_test.py; python scripts/self_model_endpoint_test.py; python scripts/self_model_extraction_test.py; python scripts/big_five_scoring_test.py`
Expected: 각 FAIL=0. (extraction/merge 가 axis_source 를 보존·존중하는지. repository 테스트가 fetch/write 계약 변경을 반영하는지 — 실패 시 axis_source 포함해 갱신.)

- [ ] **Step 12: 커밋**

```bash
git add backend/domain/user_intelligence/models/bases/user_self_model.py backend/alembic/versions/<new>.py backend/domain/user_intelligence/hub/repositories/self_model_repository.py backend/domain/user_intelligence/hub/services/self_model_service.py backend/api/v1/user/user_routor.py backend/scripts/self_model_user_edits_test.py backend/scripts/self_model_merge_test.py
git commit -m "feat(sp7): 자기모델 축별 provenance + 사용자 편집 쓰기(PUT) — user_form 축 코치 잠식 차단"
```

---

### Task 2: 프론트 — 자기모델 편집 모달

**Files:**
- Modify: `www.yeotaeho.kr/src/lib/api/selfModel.ts` (axisSource 타입·`updateSelfModel`)
- Create: `www.yeotaeho.kr/src/components/features/consult/SelfModelEditModal.tsx`
- Modify: `www.yeotaeho.kr/src/components/features/consult/SelfModelPanel.tsx` ("수정" 버튼·모달 연결)

**Interfaces:**
- Consumes: Task 1 `GET /api/user/self-model`(→ `axisSource`) · `PUT /api/user/self-model`(edits).
- Produces: 없음(말단 UI).

- [ ] **Step 1: API 클라이언트 — axisSource 타입 + updateSelfModel**

`selfModel.ts` `SelfModelLive` 에 필드 추가.

```typescript
  axisSource: Record<string, string> | null;
```

`fetchSelfModel` 매핑에 `axisSource: m.axisSource ?? null,` 추가.

편집 페이로드 타입·함수 추가.

```typescript
export type AxisLevel = "low" | "mid" | "high";

export interface SelfModelEdits {
  riasec?: { levels: Record<string, AxisLevel> } | "auto";
  big_five?: { levels: Record<string, AxisLevel> } | "auto";
  narrative?: string | "auto";
}

export async function updateSelfModel(edits: SelfModelEdits): Promise<SelfModelLive> {
  const { data } = await apiClient.put("/api/user/self-model", edits);
  const m = data?.selfModel ?? {};
  return {
    riasec: m.riasec ?? null,
    bigFive: m.bigFive ?? null,
    narrativeSummary: m.narrativeSummary ?? null,
    axisConfidence: m.axisConfidence ?? null,
    axisSource: m.axisSource ?? null,
    evidence: Array.isArray(m.evidence) ? m.evidence : [],
  };
}
```

- [ ] **Step 2: 편집 모달 컴포넌트**

`www.yeotaeho.kr/src/components/features/consult/SelfModelEditModal.tsx` 생성.

```tsx
// 상담실 자기모델 편집 모달 — 축당 낮음·중간·높음·AI판단 세그먼트 + 서사
"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { updateSelfModel, type AxisLevel, type SelfModelEdits, type SelfModelLive } from "@/lib/api/selfModel";
import { useStore } from "@/store";

type Seg = AxisLevel | "auto";
const RIASEC = [
  { key: "R", label: "현실형" }, { key: "I", label: "탐구형" }, { key: "A", label: "예술형" },
  { key: "S", label: "사회형" }, { key: "E", label: "진취형" }, { key: "C", label: "관습형" },
] as const;
const BIG_FIVE = [
  { key: "O", label: "개방성" }, { key: "C", label: "성실성" }, { key: "E", label: "외향성" },
  { key: "A", label: "우호성" }, { key: "stability", label: "정서안정성" },
] as const;
const SEGS: { v: Seg; t: string }[] = [
  { v: "low", t: "낮음" }, { v: "mid", t: "중간" }, { v: "high", t: "높음" }, { v: "auto", t: "AI판단" },
];

function scoreToLevel(v: number | undefined): AxisLevel {
  if (typeof v !== "number") return "mid";
  if (v >= 62) return "high";
  if (v <= 38) return "low";
  return "mid";
}

export function SelfModelEditModal({ data, onClose }: { data: SelfModelLive | null; onClose: () => void }) {
  const profile = useStore((s) => s.profile);
  const qc = useQueryClient();
  const riasecUserForm = (data?.axisSource || {}).riasec === "user_form";
  const bigFiveUserForm = (data?.axisSource || {}).big_five === "user_form";

  // 사용자 확정(user_form) 축만 현재 레벨을 프리필. 코치 소유 축은 "AI판단" 기본 —
  // 손대지 않고 저장하면 코치 소유가 유지되고(footgun 방지), 레벨을 고르면 그때 user_form 이 된다.
  const [riasec, setRiasec] = useState<Record<string, Seg>>(() =>
    Object.fromEntries(RIASEC.map((a) => [a.key,
      riasecUserForm ? scoreToLevel(data?.riasec?.scores?.[a.key as keyof typeof data.riasec.scores]) : "auto"])),
  );
  const [bigFive, setBigFive] = useState<Record<string, Seg>>(() =>
    Object.fromEntries(BIG_FIVE.map((a) => {
      const raw = a.key === "stability"
        ? (typeof data?.bigFive?.scores?.N === "number" ? 100 - data.bigFive.scores.N : undefined)
        : data?.bigFive?.scores?.[a.key as keyof typeof data.bigFive.scores];
      return [a.key, bigFiveUserForm ? scoreToLevel(raw) : "auto"];
    })),
  );
  const narrativeUserForm = (data?.axisSource || {}).narrative_summary === "user_form";
  const [narrative, setNarrative] = useState(narrativeUserForm ? (data?.narrativeSummary ?? "") : "");

  const mutation = useMutation({
    mutationFn: () => {
      const edits: SelfModelEdits = {};
      const rAuto = Object.values(riasec).every((v) => v === "auto");
      edits.riasec = rAuto ? "auto" : { levels: pickLevels(riasec) };
      const bAuto = Object.values(bigFive).every((v) => v === "auto");
      edits.big_five = bAuto ? "auto" : { levels: pickLevels(bigFive) };
      edits.narrative = narrative.trim() ? narrative.trim() : "auto";
      return updateSelfModel(edits);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["self-model", profile?.id] });
      onClose();
    },
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={onClose}>
      <div
        className="max-h-[85vh] w-full max-w-md overflow-y-auto rounded-2xl bg-white p-5 shadow-xl dark:bg-slate-800"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="text-base font-bold text-slate-900 dark:text-slate-100">나의 성향 직접 정하기</h2>
        <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
          내가 정한 항목은 대화로 바뀌지 않아요. AI판단을 고르면 다시 대화로 파악해요.
        </p>

        <Section title="직업 흥미(RIASEC)" axes={RIASEC} state={riasec} setState={setRiasec} />
        <Section title="성격(Big Five)" axes={BIG_FIVE} state={bigFive} setState={setBigFive} />

        <div className="mt-4">
          <p className="mb-1 text-xs font-semibold text-slate-700 dark:text-slate-300">한 줄 자기소개</p>
          <textarea
            value={narrative}
            onChange={(e) => setNarrative(e.target.value)}
            rows={2}
            className="w-full rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-sm dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
            placeholder={data?.narrativeSummary || "예: 문제를 깊이 파고드는 걸 좋아해요."}
          />
        </div>

        <div className="mt-5 flex justify-end gap-2">
          <button type="button" onClick={onClose} className="rounded-lg px-3 py-2 text-sm text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-700">취소</button>
          <button
            type="button"
            onClick={() => mutation.mutate()}
            disabled={mutation.isPending}
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-50"
          >
            {mutation.isPending ? "저장 중…" : "저장"}
          </button>
        </div>
      </div>
    </div>
  );
}

function pickLevels(state: Record<string, Seg>): Record<string, AxisLevel> {
  const out: Record<string, AxisLevel> = {};
  for (const [k, v] of Object.entries(state)) out[k] = v === "auto" ? "mid" : v;
  return out;
}

function Section({
  title, axes, state, setState,
}: {
  title: string;
  axes: readonly { key: string; label: string }[];
  state: Record<string, Seg>;
  setState: (s: Record<string, Seg>) => void;
}) {
  return (
    <div className="mt-4">
      <p className="mb-1.5 text-xs font-semibold text-slate-700 dark:text-slate-300">{title}</p>
      <div className="space-y-1.5">
        {axes.map((a) => (
          <div key={a.key} className="flex items-center gap-2">
            <span className="w-16 shrink-0 text-[11px] text-slate-600 dark:text-slate-300">{a.label}</span>
            <div className="flex flex-1 overflow-hidden rounded-lg border border-slate-200 dark:border-slate-700">
              {SEGS.map((seg) => (
                <button
                  key={seg.v}
                  type="button"
                  onClick={() => setState({ ...state, [a.key]: seg.v })}
                  className={
                    "flex-1 px-1 py-1 text-[11px] transition " +
                    (state[a.key] === seg.v
                      ? "bg-indigo-600 text-white"
                      : "bg-white text-slate-600 hover:bg-slate-50 dark:bg-slate-900 dark:text-slate-300")
                  }
                >
                  {seg.t}
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: SelfModelPanel — "수정" 버튼·모달 연결**

`SelfModelPanel.tsx`:
- import 추가: `import { useState } from "react";`(없으면) · `import { SelfModelEditModal } from "./SelfModelEditModal";` · lucide `Pencil`.
- 컴포넌트에 `const [editing, setEditing] = useState(false);`.
- 패널 헤더("나의 성향 지도") 우측에 수정 버튼 추가(로그인 시에만):
```tsx
        {authed && (
          <button
            type="button"
            onClick={() => setEditing(true)}
            className="ml-auto inline-flex items-center gap-1 rounded-lg px-1.5 py-1 text-[11px] text-slate-500 hover:bg-slate-100 hover:text-indigo-600 dark:text-slate-400 dark:hover:bg-slate-700"
            aria-label="성향 수정"
          >
            <Pencil className="h-3 w-3" /> 수정
          </button>
        )}
```
(헤더 div 를 `flex items-center` 로 만들어 버튼을 오른쪽에 정렬. `authed` 는 기존 게이팅 변수 재사용.)
- 반환 JSX 말미에 모달 렌더:
```tsx
      {editing && <SelfModelEditModal data={data ?? null} onClose={() => setEditing(false)} />}
```

- [ ] **Step 4: 타입 검증**

Run: `cd www.yeotaeho.kr; pnpm exec tsc --noEmit`
Expected: 출력 없음(0 에러).

- [ ] **Step 5: 커밋**

```bash
git add www.yeotaeho.kr/src/lib/api/selfModel.ts www.yeotaeho.kr/src/components/features/consult/SelfModelEditModal.tsx www.yeotaeho.kr/src/components/features/consult/SelfModelPanel.tsx
git commit -m "feat(sp7): 상담실 자기모델 편집 모달 — 축당 3단계·AI판단·서사, PUT 연동"
```

---

## 최종 검증 (whole-branch)

- [ ] 백엔드 회귀 (cwd `backend/`, 각 FAIL=0):
```bash
python scripts/self_model_user_edits_test.py
python scripts/self_model_merge_test.py
python scripts/self_model_repository_test.py
python scripts/self_model_endpoint_test.py
python scripts/self_model_extraction_test.py
python scripts/big_five_scoring_test.py
python scripts/recommend_explain_service_test.py
```
- [ ] 프론트 `cd www.yeotaeho.kr; pnpm exec tsc --noEmit` 0 에러.
- [ ] 리뷰 게이트 — code-reviewer 에이전트 whole-branch → Codex `/codex:review --base <시작 ref> --scope branch`.
