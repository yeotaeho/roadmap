# KIAT Gap youth_fit 변별 개선 + Gold 사영 단일화 (Phase 2 Refinement) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** youth_fit 점수가 0.6~0.7 에 뭉치는 문제를 앵커 루브릭 프롬프트로 고치고, 이를 위한 PROMPT_VERSION v2 bump 가 공유 Gold 사영을 깨뜨리지 않도록 사영을 단일 잡으로 분리한다.

**Architecture:** 두 refine 서비스(`GapRefineService`·`TechDemandGapService`)는 Silver 적재만 하고, 신규 `GapProjectionService` 가 소스별 pv(discourse=v1, innovation=v2)를 단일 소유해 Gold 를 한 번에 재조립한다. `project_to_gold` 는 명시적 2-소스 SQL 로 일반화한다.

**Tech Stack:** FastAPI · SQLAlchemy 2.0(async) · PostgreSQL(Neon) · OpenAI `gpt-4o-mini` · 커스텀 `check()` 무네트워크 테스트 스크립트.

## Global Constraints

- 설계 SSOT: `backend/docs/specs/2026-06-27-kiat-gap-tech-demand-phase2-refine-design.md`.
- 새 소스 파일 첫 줄: 한 줄 한국어 역할 주석(CLAUDE.md #6).
- 한국어 문장 종결은 `.` `?` `!` 만(CLAUDE.md #5) — 프롬프트 내 `:` 는 라벨용이며 문장은 `.` 로 끝낸다.
- 멱등 자연키: `refined_gap_insights (raw_table_ref, raw_id, prompt_version)`.
- 소스별 현재 pv: discourse=`"v1"`(불변), innovation(tech_demand)=`"v2"`(Task 3 에서 bump).
- youth_fit 임계 기본값 0.5(`settings.tech_demand_youth_fit_min`).
- DB 스키마 변경 없음 — `youth_fit_score` 컬럼은 Phase 2 에서 이미 존재.
- 작업 단위 커밋 직후 audit_trail 기록(CLAUDE.md #9) — 단, md 작성 전 사용자 경로 승인 필요.
- 브랜치: `feat/kiat-gap-youth-fit-refine`(이미 생성, spec 커밋 `af9845b` 포함).

## File Structure

| 파일 | 책임 |
|---|---|
| `backend/domain/market_insight/hub/repositories/gap_repository.py` | `project_to_gold` 소스별 pv 일반화 + 게이트 SQL |
| `backend/domain/market_insight/hub/services/gap_refine_service.py` | discourse Silver 적재만(사영 제거) |
| `backend/domain/market_insight/hub/services/tech_demand_gap_service.py` | KIAT Silver 적재만(사영 제거) + pv v2 |
| `backend/domain/market_insight/hub/services/gap_projection_service.py` | **신규** — 소스별 pv 단일 소유, 단일 Gold 재조립 |
| `backend/core/llm/client.py` | `_TECH_DEMAND_GAP_SYSTEM_PROMPT` 앵커 루브릭 + few-shot |
| `backend/core/scheduler.py` | `_job_gap_project` + 파이프라인 등록 |
| `backend/api/v1/insight/insight_routor.py` | `/gap/refine` 에 사영 이어 호출 + `POST /gap/project` |
| `backend/scripts/tech_demand_gap_backfill.py` | refine 후 사영 호출 |
| `backend/scripts/gap_chunk_test.py` | refine 사영 미호출 단언 |
| `backend/scripts/gap_projection_test.py` | **신규** — 사영 서비스 단위 테스트 |

---

### Task 1: 사영 단일화 (behavior-preserving refactor)

discourse·tech_demand 모두 아직 `"v1"` 인 상태에서 사영을 분리한다. 이 시점엔 동작 변화가 없어야 한다(Gold 출력 동일). pv 분기·프롬프트는 후속 태스크.

**Files:**
- Modify: `backend/domain/market_insight/hub/repositories/gap_repository.py`
- Modify: `backend/domain/market_insight/hub/services/gap_refine_service.py`
- Modify: `backend/domain/market_insight/hub/services/tech_demand_gap_service.py`
- Create: `backend/domain/market_insight/hub/services/gap_projection_service.py`
- Modify: `backend/scripts/gap_chunk_test.py`
- Create: `backend/scripts/gap_projection_test.py`

**Interfaces:**
- Produces:
  - `GapRepository.project_to_gold(disc_pv: str, td_pv: str, fit_min: float = 0.0) -> int` — discourse@disc_pv + innovation@td_pv(youth_fit ≥ fit_min) 재조립, 적재 이슈 수 반환.
  - `GapProjectionService(session).project_and_serve() -> dict` 반환 `{"issues": int}`. 모듈 상수 `DISCOURSE_PV`·`TECH_DEMAND_PV` 노출.
  - `GapRefineService.refine_and_serve(...)` 반환 `{"scanned", "gaps", "skipped"}` (`issues` 키 제거).
  - `TechDemandGapService.refine_and_serve(...)` 반환 `{"scanned", "gaps", "skipped"}` (`issues` 키 제거).

- [ ] **Step 1: `gap_chunk_test.py` 단언을 사영 미호출로 변경 (실패)**

`backend/scripts/gap_chunk_test.py:105-107` 의 두 줄을 교체:

```python
    check("project_to_gold 0회(refine 는 사영 안 함)", svc.repo.gold_calls == 0)
    # 60건 / 25 = 2청크 중간 + 1회(잔여 flush) = 3회
    check(f"commit >= 3(청크 {REFINE_CHUNK}×2 + 잔여 flush)", svc.session.commits >= 3)
```

- [ ] **Step 2: 변경 테스트 실패 확인**

Run: `cd backend && python scripts/gap_chunk_test.py`
Expected: FAIL — 현재 `GapRefineService` 가 `project_to_gold` 를 1회 호출하므로 `gold_calls == 0` 가 거짓.

- [ ] **Step 3: 사영 서비스 단위 테스트 작성 (실패)**

`backend/scripts/gap_projection_test.py`:

```python
# GapProjectionService 단일 사영 무네트워크 테스트

from __future__ import annotations

import asyncio
import os
import sys

for _k, _v in dict(
    NEON_DATABASE_URL="postgresql+asyncpg://u:p@localhost/db",
    JWT_SECRET="x",
    NAVER_CLIENT_ID="x",
    NAVER_CLIENT_SECRET="x",
    NAVER_REDIRECT_URI="x",
).items():
    os.environ.setdefault(_k, _v)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from domain.market_insight.hub.services.gap_projection_service import (  # noqa: E402
    DISCOURSE_PV,
    TECH_DEMAND_PV,
    GapProjectionService,
)

PASS = 0
FAIL = 0


def check(name: str, cond: bool) -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"[PASS] {name}")
    else:
        FAIL += 1
        print(f"[FAIL] {name}")


class _FakeRepo:
    def __init__(self) -> None:
        self.calls: list = []

    async def project_to_gold(self, disc_pv, td_pv, fit_min) -> int:
        self.calls.append((disc_pv, td_pv, fit_min))
        return 7


class _FakeSession:
    def __init__(self) -> None:
        self.commits = 0

    async def commit(self) -> None:
        self.commits += 1


def test_single_projection() -> None:
    svc = GapProjectionService.__new__(GapProjectionService)
    svc.session = _FakeSession()
    svc.repo = _FakeRepo()
    svc._fit_min = 0.5

    res = asyncio.run(svc.project_and_serve())

    check("project_to_gold 정확히 1회", len(svc.repo.calls) == 1)
    check("두 소스 pv 전달", svc.repo.calls[0][:2] == (DISCOURSE_PV, TECH_DEMAND_PV))
    check("fit_min 전달", svc.repo.calls[0][2] == 0.5)
    check("issues 반환", res["issues"] == 7)
    check("commit >= 1", svc.session.commits >= 1)


def main() -> int:
    test_single_projection()
    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: 사영 테스트 실패 확인**

Run: `cd backend && python scripts/gap_projection_test.py`
Expected: FAIL — `ImportError: cannot import name 'GapProjectionService'`.

- [ ] **Step 5: `gap_repository.py` — `project_to_gold` 시그니처·SQL 일반화**

`_FETCH_SILVER_FOR_GOLD`(`gap_repository.py:75-91`)의 `WHERE` 절을 소스별 pv 매칭으로 교체. 전체 상수를 다음으로 교체:

```python
# 유효 gap(문제 있음) Silver + 원천 메타(근거용). 소스(discourse/innovation)별 evidence COALESCE.
# discourse 는 disc_pv, innovation(tech_demand)은 td_pv 로 현재 세대만 선택.
# innovation 행은 youth_fit_score >= :fit_min 만 통과(discourse 는 NULL 이라 무조건 통과).
_FETCH_SILVER_FOR_GOLD = text(
    """
    SELECT g.sector_slug, g.extracted_problem, g.extracted_opportunity, g.detail_summary,
           g.stakeholders, g.next_actions, g.reference_date, g.raw_table_ref, g.raw_id,
           COALESCE(d.headline, i.title) AS ev_title,
           COALESCE(d.source_url, i.source_url) AS ev_url
    FROM refined_gap_insights g
    LEFT JOIN raw_discourse_data d
           ON d.id = g.raw_id AND g.raw_table_ref = 'raw_discourse_data'
    LEFT JOIN raw_innovation_data i
           ON i.id = g.raw_id AND g.raw_table_ref = 'raw_innovation_data'
    WHERE g.extracted_problem IS NOT NULL
      AND ( (g.raw_table_ref = 'raw_discourse_data'  AND g.prompt_version = :disc_pv)
         OR (g.raw_table_ref = 'raw_innovation_data' AND g.prompt_version = :td_pv) )
      AND (g.raw_table_ref <> 'raw_innovation_data' OR g.youth_fit_score >= :fit_min)
    ORDER BY g.reference_date DESC NULLS LAST, g.id DESC
    """
)
```

`project_to_gold` 메서드(`gap_repository.py:169-210`)의 시그니처와 fetch 바인드만 교체 — 본문 루프는 불변:

```python
    async def project_to_gold(
        self, disc_pv: str, td_pv: str, fit_min: float = 0.0
    ) -> int:
        """유효 gap Silver → gap_issues + issue_evidences 멱등 재생성. 적재 이슈 수 반환.

        discourse(disc_pv)·innovation tech_demand(td_pv) 두 소스를 함께 재조립한다.
        innovation 행은 youth_fit_score >= fit_min 만 Gold 통과.
        """
        await self.session.execute(_CLEAR_GOLD)
        rows = (
            await self.session.execute(
                _FETCH_SILVER_FOR_GOLD,
                {"disc_pv": disc_pv, "td_pv": td_pv, "fit_min": fit_min},
            )
        ).all()
        n = 0
        for r in rows:
            issue_id = (
                await self.session.execute(
                    _INSERT_ISSUE,
                    {
                        "sector_slug": r.sector_slug,
                        "problem_summary": (r.extracted_problem or "")[:255],
                        "chance_summary": (r.extracted_opportunity or "")[:255],
                        "detail_summary": r.detail_summary,
                        "stakeholders": json.dumps(r.stakeholders or []),
                        "next_actions": json.dumps(r.next_actions or []),
                        "published_date": r.reference_date,
                    },
                )
            ).scalar_one()
            ev_type = "TECH_DEMAND" if r.raw_table_ref == "raw_innovation_data" else "NEWS"
            await self.session.execute(
                _INSERT_EVIDENCE,
                {
                    "issue_id": issue_id,
                    "evidence_type": ev_type,
                    "title": (r.ev_title or "근거 자료")[:255],
                    "url": r.ev_url,
                    "raw_table_ref": r.raw_table_ref,
                    "raw_id": r.raw_id,
                },
            )
            n += 1
        return n
```

- [ ] **Step 6: `gap_refine_service.py` — 사영 호출 제거**

`gap_refine_service.py:68-70` 의 세 줄을 교체:

```python
        await self.session.commit()
        return {"scanned": len(rows), "gaps": gaps, "skipped": skipped}
```

(즉 `issues = await self.repo.project_to_gold(PROMPT_VERSION)` 줄을 삭제하고, trailing `await self.session.commit()` 로 잔여 청크를 flush, 반환 dict 에서 `issues` 키 제거.)

- [ ] **Step 7: `tech_demand_gap_service.py` — 사영 호출 제거**

`tech_demand_gap_service.py:73-75` 의 세 줄을 교체:

```python
        await self.session.commit()
        return {"scanned": len(rows), "gaps": gaps, "skipped": skipped}
```

`self._fit_min` 은 이 서비스에서 더는 안 쓰이지만 `__init__` 의 `self._fit_min = settings.tech_demand_youth_fit_min` 줄은 그대로 두지 말고 제거(orphan). `__init__` 에서 해당 한 줄 삭제.

- [ ] **Step 8: `gap_projection_service.py` 작성**

`backend/domain/market_insight/hub/services/gap_projection_service.py`:

```python
# Gold 사영 — discourse·tech_demand Silver 를 소스별 pv 로 단일 재조립하는 서비스

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from core.config.settings import get_settings
from domain.market_insight.hub.repositories.gap_repository import GapRepository
from domain.market_insight.hub.services.gap_refine_service import (
    PROMPT_VERSION as DISCOURSE_PV,
)
from domain.market_insight.hub.services.tech_demand_gap_service import (
    PROMPT_VERSION as TECH_DEMAND_PV,
)


class GapProjectionService:
    """discourse(disc_pv)+tech_demand(td_pv) Silver → gap_issues 단일 재조립(youth_fit 게이트)."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = GapRepository(session)
        self._fit_min = get_settings().tech_demand_youth_fit_min

    async def project_and_serve(self) -> dict:
        """전소스 Gold 재생성 후 commit. 멱등. 반환: {"issues"}."""
        issues = await self.repo.project_to_gold(
            DISCOURSE_PV, TECH_DEMAND_PV, self._fit_min
        )
        await self.session.commit()
        return {"issues": issues}
```

- [ ] **Step 9: 두 테스트 통과 확인**

Run: `cd backend && python scripts/gap_chunk_test.py && python scripts/gap_projection_test.py`
Expected: `gap_chunk_test` 모든 PASS(`gold_calls == 0` 포함), `gap_projection_test` `5 passed, 0 failed`.

- [ ] **Step 10: 임포트 스모크 + 회귀 파서 테스트**

Run: `cd backend && python -c "from domain.market_insight.hub.services.gap_projection_service import GapProjectionService, DISCOURSE_PV, TECH_DEMAND_PV; print(DISCOURSE_PV, TECH_DEMAND_PV)" && python scripts/tech_demand_gap_parse_test.py`
Expected: `v1 v1`(아직 bump 전) · 파서 테스트 전 PASS.

- [ ] **Step 11: 커밋**

```bash
git add backend/domain/market_insight/hub/repositories/gap_repository.py backend/domain/market_insight/hub/services/gap_refine_service.py backend/domain/market_insight/hub/services/tech_demand_gap_service.py backend/domain/market_insight/hub/services/gap_projection_service.py backend/scripts/gap_chunk_test.py backend/scripts/gap_projection_test.py
git commit -m "refactor(insight): Gap Gold 사영을 GapProjectionService 단일 잡으로 분리 (Phase 2 refine)"
```

---

### Task 2: 호출부 이관 (스케줄러·HTTP·백필)

refine 서비스가 더는 사영하지 않으므로 모든 호출부가 사영을 명시 호출하도록 이관한다.

**Files:**
- Modify: `backend/core/scheduler.py` (임포트 `51` 아래, `_job_tech_demand_gap` `555` 아래, `_REFINE_PIPELINE` `640` 아래)
- Modify: `backend/api/v1/insight/insight_routor.py` (임포트 `17` 부근, `/gap/refine` `205-213`)
- Modify: `backend/scripts/tech_demand_gap_backfill.py`

**Interfaces:**
- Consumes: `GapProjectionService.project_and_serve`(Task 1).
- Produces: `_job_gap_project()` 잡 · `_REFINE_PIPELINE` 의 `gap_project` 스텝 · `POST /api/insight/gap/project` 엔드포인트.

- [ ] **Step 1: 스케줄러 임포트 추가**

`scheduler.py:51`(`TechDemandGapService` 임포트) 바로 아래에 추가:

```python
from domain.market_insight.hub.services.gap_projection_service import GapProjectionService
```

- [ ] **Step 2: `_job_gap_project` 잡 함수 추가**

`scheduler.py:555`(`_job_tech_demand_gap` 의 `return ...` 줄) 다음, `_job_causal_refine` 정의 위에 추가:

```python
async def _job_gap_project() -> dict[str, Any] | None:
    """discourse+tech_demand Silver → Gap 카드 단일 재조립(youth_fit 게이트, 멱등). LLM 무관이라 키 가드 불필요."""
    async with AsyncSessionLocal() as session:
        return await GapProjectionService(session).project_and_serve()
```

- [ ] **Step 3: 파이프라인 등록**

`scheduler.py:640` 의 `("tech_demand_gap",   _job_tech_demand_gap),` 바로 아래에 추가:

```python
    ("gap_project",       _job_gap_project),
```

- [ ] **Step 4: 스케줄러 등록 스모크**

Run: `cd backend && python -c "from core.scheduler import _REFINE_PIPELINE; names=[n for n,_ in _REFINE_PIPELINE]; print('gap_project' in names, names.index('gap_project') == names.index('tech_demand_gap')+1)"`
Expected: `True True`

- [ ] **Step 5: `insight_routor.py` 임포트 추가**

`insight_routor.py:17`(`GapRefineService` 임포트) 바로 아래에 추가:

```python
from domain.market_insight.hub.services.gap_projection_service import GapProjectionService
```

- [ ] **Step 6: `/gap/refine` 에 사영 이어 호출 + `/gap/project` 추가**

`insight_routor.py:205-213` 의 `refine_gap` 엔드포인트를 다음으로 교체:

```python
@router.post("/gap/refine", dependencies=[Depends(require_internal_token)])
async def refine_gap(db: AsyncSession = Depends(get_db)):
    """Gap 정제·서빙 수동 트리거 — discourse → Silver → Gold 재생성."""
    try:
        result = await GapRefineService(db).refine_and_serve()
        projected = await GapProjectionService(db).project_and_serve()
        return {"success": True, **result, **projected}
    except Exception as e:
        logger.error(f"Gap 정제 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Gap 정제 실패: {str(e)}")


@router.post("/gap/project", dependencies=[Depends(require_internal_token)])
async def project_gap(db: AsyncSession = Depends(get_db)):
    """Gap Gold 재사영만 — youth_fit 임계 재튜닝 후 LLM 재실행 없이 Gold 재생성."""
    try:
        result = await GapProjectionService(db).project_and_serve()
        return {"success": True, **result}
    except Exception as e:
        logger.error(f"Gap 사영 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Gap 사영 실패: {str(e)}")
```

- [ ] **Step 7: 라우터 임포트 스모크**

Run: `cd backend && python -c "from api.v1.insight.insight_routor import router; paths=[r.path for r in router.routes]; print('/gap/project' in paths, '/gap/refine' in paths)"`
Expected: `True True`

- [ ] **Step 8: 백필 스크립트에 사영 호출 추가**

`tech_demand_gap_backfill.py` 임포트 블록에 추가(`TechDemandGapService` 임포트 아래):

```python
from domain.market_insight.hub.services.gap_projection_service import (  # noqa: E402
    GapProjectionService,
)
```

`main()` 의 `async with` 블록과 출력을 교체:

```python
    async with AsyncSessionLocal() as session:
        result = await TechDemandGapService(session).refine_and_serve(
            window_days=window, limit=limit
        )
        projected = await GapProjectionService(session).project_and_serve()
    print(f"백필 결과(limit={limit}, window={window}d): {result} | 사영: {projected}")
```

- [ ] **Step 9: 백필 임포트 스모크**

Run: `cd backend && python -c "import scripts.tech_demand_gap_backfill as b; print(hasattr(b, 'GapProjectionService'))"`
Expected: `True`

- [ ] **Step 10: 커밋**

```bash
git add backend/core/scheduler.py backend/api/v1/insight/insight_routor.py backend/scripts/tech_demand_gap_backfill.py
git commit -m "feat(insight): Gap 사영 단일 잡 호출부 이관 — 스케줄러·HTTP·백필 (Phase 2 refine)"
```

---

### Task 3: 프롬프트 앵커 루브릭 + few-shot + PROMPT_VERSION v2

youth_fit 변별의 실제 수정. 의미가 바뀌므로 pv 를 bump 해 v2 로 재추출되게 한다.

**Files:**
- Modify: `backend/core/llm/client.py:32-43` (`_TECH_DEMAND_GAP_SYSTEM_PROMPT`)
- Modify: `backend/domain/market_insight/hub/services/tech_demand_gap_service.py:13-14` (주석 + `PROMPT_VERSION`)

**Interfaces:**
- Produces: `TechDemandGapService.PROMPT_VERSION == "v2"` → `GapProjectionService.TECH_DEMAND_PV == "v2"`.

- [ ] **Step 1: 프롬프트 교체**

`client.py:32-43` 의 `_TECH_DEMAND_GAP_SYSTEM_PROMPT` 전체를 교체:

```python
_TECH_DEMAND_GAP_SYSTEM_PROMPT = (
    "너는 한국 정부·공공기관이 공개한 '기업 수요기술'(기업이 필요로 하나 아직 확보 못한 기술) 설명에서 "
    "'시장의 미해결 갭'과 그로부터 파생되는 '청년의 기회'를 찾는 분석기다. "
    "수요기술이 가리키는 부족한 역량을 미해결 문제(problem)로, 청년이 그 역량을 키워 잡을 수 있는 기회를 opportunity 로 추출하라. "
    "수요기술로 보기 어렵거나 의미가 불명하면 problem 을 null 로 두라(억지 생성 금지). "
    "youth_fit 은 청년 개인이 학습·진입 가능한 정도를 0~1 로 매기되, 반드시 아래 대역 기준으로 점수를 분산시켜라. "
    "0.1~0.3 — 대규모 설비·소재·공정·자본집약·라이선스 장벽이 큰 B2B 기술로 개인 진입이 사실상 불가하다. "
    "0.4~0.6 — 전문성이나 자본이 일부 필요하나 개인이 협업·소규모로 진입할 여지가 있다. "
    "0.8~0.9 — 개인이 학습·포트폴리오로 진입 가능한 소프트웨어·디자인·데이터·서비스 기술이다. "
    "예시 — '반도체 식각 장비 국산화 공정기술'은 0.2(대규모 설비·자본집약)다. "
    "'산업용 IoT 센서 데이터 통합 소프트웨어'는 0.5(개인 진입 여지는 있으나 도메인 전문성 필요)다. "
    "'생성형 AI 기반 고객 응대 서비스 개발'은 0.85(개인이 학습·포트폴리오로 진입 가능)다. "
    "중간값에 몰리지 말고 각 수요기술의 실제 진입장벽을 판단해 대역을 고르라. "
    "problem·opportunity 는 각각 한 문장, detail 은 2~3문장, stakeholders 는 관련 주체 2~4개, "
    "next_actions 는 청년의 실행 액션 2~4개로 적어라. "
    'JSON 객체만 출력하라. 형식: {"problem": <문장 또는 null>, "opportunity": <문장 또는 null>, '
    '"detail": <문자열>, "stakeholders": [<주체>...], "next_actions": [<액션>...], "youth_fit": <0~1 실수>}.'
)
```

- [ ] **Step 2: PROMPT_VERSION bump + 주석 갱신**

`tech_demand_gap_service.py:13-14` 의 주석 한 줄과 상수를 교체:

```python
# tech_demand 전용 pv — GapProjectionService 가 소스별 pv(discourse=v1, innovation=v2)로 재조립한다. 의미 변경 시 bump.
PROMPT_VERSION = "v2"
```

- [ ] **Step 3: 프롬프트·pv 스모크**

Run: `cd backend && python -c "from core.llm.client import _TECH_DEMAND_GAP_SYSTEM_PROMPT as p; print('0.1~0.3' in p and '0.8~0.9' in p and '0.85' in p)" && python -c "from domain.market_insight.hub.services.gap_projection_service import TECH_DEMAND_PV, DISCOURSE_PV; print(DISCOURSE_PV, TECH_DEMAND_PV)"`
Expected: `True` · `v1 v2`

- [ ] **Step 4: 파서 회귀 확인 (형식 불변)**

Run: `cd backend && python scripts/tech_demand_gap_parse_test.py`
Expected: 전 PASS — 출력 JSON 형식 불변이므로 파서 무영향.

- [ ] **Step 5: 커밋**

```bash
git add backend/core/llm/client.py backend/domain/market_insight/hub/services/tech_demand_gap_service.py
git commit -m "feat(insight): 수요기술 youth_fit 앵커 루브릭+few-shot 프롬프트 + pv v2 (Phase 2 refine)"
```

---

### Task 4: 소규모 재추출 + youth_fit 분포 검증 + audit_trail

실제 DB·`OPENAI_API_KEY` 필요. 게이트가 실제로 일부를 거르는지 검증하고 필요시 임계만 재튜닝한다.

**Files:**
- (실행 검증 — 코드 변경 없음, 필요시 `.env` 의 `TECH_DEMAND_YOUTH_FIT_MIN` 조정)
- Modify(승인 후): `backend/domain/market_insight/docs/audit_trail.md`

**Interfaces:**
- Consumes: `tech_demand_gap_backfill.py`(Task 2) · v2 프롬프트(Task 3).

- [ ] **Step 1: v2 소규모 재추출**

Run: `cd backend && python scripts/tech_demand_gap_backfill.py 100`
Expected: `백필 결과(limit=100, window=90d): {'scanned': <N>, 'gaps': <G>, 'skipped': <S>} | 사영: {'issues': <I>}` — `scanned > 0`, `gaps + skipped == scanned`.

scanned == 0 이면 Phase 1 분류 선행 필요 — DB 콘솔에서 확인:

```sql
SELECT count(*) FILTER (WHERE confidence >= 0.6) AS eligible, count(*) AS total
FROM refined_text_sector_class WHERE raw_table_ref = 'raw_innovation_data';
```

- [ ] **Step 2: youth_fit 분포 확인 (게이트 작동 여부)**

DB 콘솔:

```sql
SELECT round(min(youth_fit_score)::numeric, 2) AS min,
       round(max(youth_fit_score)::numeric, 2) AS max,
       round(avg(youth_fit_score)::numeric, 3) AS avg,
       count(*) FILTER (WHERE youth_fit_score < 0.5) AS below_gate,
       count(*) AS total
FROM refined_gap_insights
WHERE data_role = 'TECH_DEMAND_SIGNAL' AND prompt_version = 'v2';
```

Expected: 분포가 실제로 벌어짐(min 이 0.6 → 0.3 이하로 내려감), `below_gate > 0`. 분포가 또 좁으면 Task 3 프롬프트 보강(few-shot 추가·입력 abstract 비중 확인) 후 재실행.

- [ ] **Step 3: Gold 게이트·통합 확인**

DB 콘솔:

```sql
-- 게이트: 임계 미만이 Silver 엔 있고 Gold(evidence) 엔 없는가
SELECT evidence_type, count(*) FROM issue_evidences GROUP BY evidence_type;
-- discourse 무회귀: DISCOURSE_SIGNAL 이 Gold 에 여전히 반영되는가
SELECT data_role, count(*) FROM refined_gap_insights
WHERE prompt_version IN ('v1','v2') GROUP BY data_role;
```

Expected: `evidence_type` 에 `NEWS`(discourse) + `TECH_DEMAND`(innovation) 공존. `below_gate` 행이 `issue_evidences` 의 `TECH_DEMAND` 수에 미반영(Silver below_gate 만큼 차감).

- [ ] **Step 4: (필요시) 임계 재튜닝 — Gold 재사영만**

분포를 보고 `0.5` 가 과하거나 약하면 `.env` 의 `TECH_DEMAND_YOUTH_FIT_MIN` 조정 후 LLM 재실행 없이 사영만 재실행. 두 경로 중 하나:

- 운영 서버: `POST /api/insight/gap/project`(internal token) 호출.
- 로컬: `cd backend && python scripts/tech_demand_gap_backfill.py 0` — limit 0 이라 추출은 0건이고 사영만 재실행된다(`fetch_unprocessed_tech_demand` 가 0행 반환 → refine no-op → projection 실행).

Expected: `사영: {'issues': <I>}` 의 이슈 수가 새 임계에 맞춰 변동.

- [ ] **Step 5: 회귀 테스트 일괄 확인**

Run: `cd backend && python scripts/gap_chunk_test.py && python scripts/gap_projection_test.py && python scripts/tech_demand_gap_parse_test.py`
Expected: 전부 `0 failed`.

- [ ] **Step 6: audit_trail 기록 (경로 승인 후)**

`backend/domain/market_insight/docs/audit_trail.md` 최상단에 항목 추가. **md 작성 전 사용자에게 경로 제시·승인 필요(CLAUDE.md #9).** 형식(CLAUDE.md 작업 기록 규칙):

```markdown
## 2026-06-27 — KIAT Gap youth_fit 변별 개선 + Gold 사영 단일화 (Phase 2 refine)
- **무엇** — youth_fit 앵커 루브릭+few-shot 프롬프트(pv v2), Gold 사영을 GapProjectionService 단일 잡으로 분리(소스별 pv)
- **왜** — youth_fit 0.6~0.7 뭉침으로 게이트 무력 + pv bump 시 공유 사영이 타 소스 Gold 삭제
- **어디** — `core/llm/client.py` · `hub/services/gap_projection_service.py` · `hub/repositories/gap_repository.py:project_to_gold`
- **검증** — gap_chunk/gap_projection/parse 테스트 PASS, v2 재추출 youth_fit 분포 <측정값> below_gate=<n>
- **후속** — 구 v1 tech_demand Silver 정리(선택), 전체 백필(window 확대)
```

- [ ] **Step 7: audit_trail 커밋**

```bash
git add backend/domain/market_insight/docs/audit_trail.md
git commit -m "docs(insight): audit_trail — youth_fit 변별 개선 + 사영 단일화 (Phase 2 refine)"
```

---

## 검증 요약 (전체)

- **단위** — `gap_chunk_test`(refine 사영 미호출, `gold_calls==0`) · `gap_projection_test`(두 pv·fit_min 1회 사영) · `tech_demand_gap_parse_test`(파서 무변경).
- **refactor 무행동변화(Task 1)** — discourse·tech_demand 모두 v1 인 채 사영만 분리 → Gold 출력 동일.
- **youth_fit 변별(Task 3·4)** — v2 재추출 분포가 0.3 이하까지 벌어지고 `below_gate > 0`.
- **무회귀** — discourse `DISCOURSE_SIGNAL` Gold 반영 불변, `/gap/refine` 응답에 `issues` 포함.
- **멱등** — 자연키 `ON CONFLICT DO NOTHING` + 사영 clear/rebuild, 재실행 안전.

## 미해결·후속

- youth_fit 임계 0.5 는 시작값 — Task 4 분포 보고 `TECH_DEMAND_YOUTH_FIT_MIN` 재튜닝(사영만).
- 분포가 또 좁으면 few-shot 보강·입력 텍스트(abstract 비중) 재검토.
- 구 v1 tech_demand Silver 정리·단일 사영 잡 통합 후 gap_refine/tech_demand 잡의 의미 명확화는 추후.
