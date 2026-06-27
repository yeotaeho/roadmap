# KIAT 수요기술 → Gap 청년 기회 신호 (Phase 2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** KIAT 수요기술(Phase 1 분류 결과)을 LLM 추출해 "기업 미확보 기술 → 청년 기회" Gap 신호로 변환하고, youth_fit 게이트로 청년 무관 항목을 배제해 Gap 탭에 통합 노출한다.

**Architecture:** 신규 `TechDemandGapService`가 KIAT 전용 추출·프롬프트를 격리하고, Silver(`refined_gap_insights`)·Gold(`gap_issues`)·`GapRepository`는 공유한다. `GapRepository`를 소스-인지(discourse/innovation)로 일반화하되 discourse 경로는 기본값으로 무회귀를 보장한다.

**Tech Stack:** FastAPI · SQLAlchemy 2.0(async) · Alembic · PostgreSQL(Neon) · OpenAI `gpt-4o-mini` · 커스텀 `check()` 파싱 테스트 스크립트.

## Global Constraints

- 설계 SSOT: `backend/docs/specs/2026-06-27-kiat-gap-tech-demand-phase2-design.md`.
- 새 소스 파일 첫 줄: 한 줄 한국어 역할 주석(CLAUDE.md #6).
- 한국어 문장 종결은 `.` `?` `!` 만(CLAUDE.md #5).
- 멱등 자연키: `refined_gap_insights (raw_table_ref, raw_id, prompt_version)`.
- KIAT/KISTEP source_type 상수: `'INNOVATION_KIAT_TECH_DEMAND'`, `'INNOVATION_KISTEP_REPORT'`.
- `TechDemandGapService.PROMPT_VERSION = "v1"` — discourse gap과 같은 pv. 공유 Gold 사영(`project_to_gold`, pv 필터)이 discourse+tech_demand 두 소스를 함께 재조립하기 위함. **이 값을 다르게 두면 마지막 사영 잡이 다른 소스를 삭제하므로 절대 변경 금지.**
- youth_fit 임계 기본값 0.5(`settings.tech_demand_youth_fit_min`).
- 모든 작업 단위 커밋 직후 audit_trail 기록(CLAUDE.md #9) — 단, md 작성 전 사용자 경로 승인 필요.

---

### Task 1: 설정·모델·마이그레이션 (youth_fit_score 컬럼 + 임계 설정)

**Files:**
- Modify: `backend/core/config/settings.py:161` (llm 설정 블록 끝에 추가)
- Modify: `backend/domain/market_insight/models/bases/refined_gap_insights.py:7,28`
- Create: `backend/alembic/versions/d7a1f3c9e2b5_add_youth_fit_score.py`

**Interfaces:**
- Produces: `settings.tech_demand_youth_fit_min: float`(기본 0.5) · `refined_gap_insights.youth_fit_score`(FLOAT nullable) 컬럼.

- [ ] **Step 1: settings 에 임계 필드 추가**

`backend/core/config/settings.py` 의 `llm_classify_confidence_min` 필드 바로 아래(`llm_embed_model` 위)에 추가:

```python
    tech_demand_youth_fit_min: float = Field(
        default=0.5, validation_alias="TECH_DEMAND_YOUTH_FIT_MIN"
    )
```

- [ ] **Step 2: 모델에 컬럼 추가**

`refined_gap_insights.py` 임포트 줄에 `Float` 추가:

```python
from sqlalchemy import BigInteger, Date, DateTime, Float, ForeignKey, Index, String, Text
```

`input_hash` 컬럼 정의 아래에 추가:

```python
    youth_fit_score: Mapped[float | None] = mapped_column(Float, nullable=True)
```

- [ ] **Step 3: 마이그레이션 파일 작성**

`backend/alembic/versions/d7a1f3c9e2b5_add_youth_fit_score.py`:

```python
"""refined_gap_insights 에 youth_fit_score 컬럼 추가(KIAT Gap 적합도 게이트)."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d7a1f3c9e2b5"
down_revision: Union[str, None] = "c5f9a3b7d1e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "refined_gap_insights",
        sa.Column("youth_fit_score", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("refined_gap_insights", "youth_fit_score")
```

- [ ] **Step 4: 마이그레이션 적용**

Run: `cd backend && alembic upgrade head`
Expected: `Running upgrade c5f9a3b7d1e2 -> d7a1f3c9e2b5, add youth_fit_score`

- [ ] **Step 5: 설정·모델 임포트 스모크**

Run: `cd backend && python -c "from core.config.settings import get_settings; from domain.market_insight.models.bases.refined_gap_insights import RefinedGapInsights as R; print(get_settings().tech_demand_youth_fit_min, hasattr(R, 'youth_fit_score'))"`
Expected: `0.5 True`

- [ ] **Step 6: 커밋**

```bash
git add backend/core/config/settings.py backend/domain/market_insight/models/bases/refined_gap_insights.py backend/alembic/versions/d7a1f3c9e2b5_add_youth_fit_score.py
git commit -m "feat(insight): refined_gap_insights youth_fit_score 컬럼 + 임계 설정 (Phase 2)"
```

---

### Task 2: LLM 추출 — extract_tech_demand_gap + 프롬프트 + 파서

**Files:**
- Modify: `backend/core/llm/client.py` (프롬프트 상수 `_GAP_SYSTEM_PROMPT` 아래, 파서 `_parse_gap` 아래, 메서드 `extract_gap` 아래)
- Create: `backend/scripts/tech_demand_gap_parse_test.py`

**Interfaces:**
- Produces: `LlmClient.extract_tech_demand_gap(text: str) -> dict` 반환 `{problem, opportunity, detail, stakeholders, next_actions, youth_fit}`. `_parse_tech_demand_gap(raw: str | None) -> dict` 동일 키. problem·opportunity 둘 다 있어야 유효, 아니면 전부 None + youth_fit 0.0.

- [ ] **Step 1: 파싱 회귀 테스트 작성(실패)**

`backend/scripts/tech_demand_gap_parse_test.py`:

```python
# KIAT 수요기술 Gap 추출 파서 무네트워크 회귀 테스트

from __future__ import annotations

import json
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

from core.llm.client import _parse_tech_demand_gap  # noqa: E402

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


def test_valid() -> None:
    raw = json.dumps({
        "problem": "기업이 엣지 AI 경량화 인력을 못 구한다",
        "opportunity": "온디바이스 모델 최적화 역량을 키우면 진입할 수 있다",
        "detail": "수요는 크나 공급이 부족하다. 개인 학습으로 진입 가능하다.",
        "stakeholders": ["AI 스타트업", "디바이스 제조사"],
        "next_actions": ["경량화 프레임워크 학습", "포트폴리오 구축"],
        "youth_fit": 0.8,
    })
    r = _parse_tech_demand_gap(raw)
    check("valid problem", r["problem"].startswith("기업이"))
    check("valid youth_fit", r["youth_fit"] == 0.8)
    check("valid stakeholders len", len(r["stakeholders"]) == 2)


def test_missing_opportunity_voids() -> None:
    raw = json.dumps({"problem": "문제만 있음", "opportunity": None, "youth_fit": 0.9})
    r = _parse_tech_demand_gap(raw)
    check("void problem None", r["problem"] is None)
    check("void youth_fit 0", r["youth_fit"] == 0.0)


def test_youth_fit_clamped() -> None:
    raw = json.dumps({"problem": "p", "opportunity": "o", "youth_fit": 5})
    check("clamp high", _parse_tech_demand_gap(raw)["youth_fit"] == 1.0)
    raw2 = json.dumps({"problem": "p", "opportunity": "o", "youth_fit": "bad"})
    check("bad youth_fit -> 0", _parse_tech_demand_gap(raw2)["youth_fit"] == 0.0)


def test_malformed() -> None:
    check("none raw", _parse_tech_demand_gap(None)["problem"] is None)
    check("bad json", _parse_tech_demand_gap("{not json")["problem"] is None)


if __name__ == "__main__":
    test_valid()
    test_missing_opportunity_voids()
    test_youth_fit_clamped()
    test_malformed()
    print(f"\n{PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd backend && python scripts/tech_demand_gap_parse_test.py`
Expected: FAIL — `ImportError: cannot import name '_parse_tech_demand_gap'`

- [ ] **Step 3: 프롬프트 상수 추가**

`client.py` 의 `_GAP_SYSTEM_PROMPT = (...)` 정의 바로 아래에 추가:

```python
_TECH_DEMAND_GAP_SYSTEM_PROMPT = (
    "너는 한국 정부·공공기관이 공개한 '기업 수요기술'(기업이 필요로 하나 아직 확보 못한 기술) 설명에서 "
    "'시장의 미해결 갭'과 그로부터 파생되는 '청년의 기회'를 찾는 분석기다. "
    "수요기술이 가리키는 부족한 역량을 미해결 문제(problem)로, 청년이 그 역량을 키워 잡을 수 있는 기회를 opportunity 로 추출하라. "
    "youth_fit 은 청년 개인이 학습·진입 가능한 정도를 0~1 로 매겨라 — 대규모 설비·자본집약·라이선스 장벽이 큰 B2B 기술이면 낮게, "
    "개인이 역량·포트폴리오로 진입 가능한 소프트웨어·디자인·서비스 기술이면 높게. "
    "수요기술로 보기 어렵거나 의미가 불명하면 problem 을 null 로 두라(억지 생성 금지). "
    "problem·opportunity 는 각각 한 문장, detail 은 2~3문장, stakeholders 는 관련 주체 2~4개, "
    "next_actions 는 청년의 실행 액션 2~4개로 적어라. "
    'JSON 객체만 출력하라. 형식: {"problem": <문장 또는 null>, "opportunity": <문장 또는 null>, '
    '"detail": <문자열>, "stakeholders": [<주체>...], "next_actions": [<액션>...], "youth_fit": <0~1 실수>}.'
)
```

- [ ] **Step 4: 파서 함수 추가**

`client.py` 의 `_parse_gap` 함수 정의 바로 아래에 추가:

```python
def _parse_tech_demand_gap(raw: str | None) -> dict:
    """수요기술 Gap 추출 응답을 검증된 결과로 파싱한다. 무네트워크 순수 함수.

    problem·opportunity 둘 다 있어야 유효. 하나라도 없으면 전부 None + youth_fit 0.0(무귀속).
    youth_fit 은 0~1 로 클램프, 파싱 실패 시 0.0.
    """
    empty = {
        "problem": None, "opportunity": None, "detail": None,
        "stakeholders": [], "next_actions": [], "youth_fit": 0.0,
    }
    try:
        obj = json.loads(raw) if raw else {}
    except (json.JSONDecodeError, TypeError):
        return empty
    if not isinstance(obj, dict):
        return empty

    problem = obj.get("problem")
    problem = problem.strip() if isinstance(problem, str) and problem.strip() else None
    opp = obj.get("opportunity")
    opp = opp.strip() if isinstance(opp, str) and opp.strip() else None
    if problem is None or opp is None:
        return empty

    detail = obj.get("detail")
    detail = detail.strip() if isinstance(detail, str) and detail.strip() else None
    try:
        fit = float(obj.get("youth_fit"))
    except (TypeError, ValueError):
        fit = 0.0
    fit = max(0.0, min(1.0, fit))
    return {
        "problem": problem,
        "opportunity": opp,
        "detail": detail,
        "stakeholders": _str_list(obj.get("stakeholders"), 6),
        "next_actions": _str_list(obj.get("next_actions"), 6),
        "youth_fit": fit,
    }
```

- [ ] **Step 5: LLM 메서드 추가**

`client.py` 의 `extract_gap` 메서드 정의 바로 아래에 추가:

```python
    async def extract_tech_demand_gap(self, text: str) -> dict:
        """KIAT 수요기술에서 미해결 갭·청년 기회·youth_fit 을 추출한다. problem None 이면 무귀속."""
        resp = await self._client.chat.completions.create(
            model=self._model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": _TECH_DEMAND_GAP_SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
        )
        return _parse_tech_demand_gap(resp.choices[0].message.content)
```

- [ ] **Step 6: 테스트 통과 확인**

Run: `cd backend && python scripts/tech_demand_gap_parse_test.py`
Expected: `9 passed, 0 failed`

- [ ] **Step 7: 커밋**

```bash
git add backend/core/llm/client.py backend/scripts/tech_demand_gap_parse_test.py
git commit -m "feat(insight): LLM extract_tech_demand_gap + youth_fit 파서 (Phase 2)"
```

---

### Task 3: GapRepository 소스-인지 일반화

**Files:**
- Modify: `backend/domain/market_insight/hub/repositories/gap_repository.py`

**Interfaces:**
- Consumes: `refined_gap_insights.youth_fit_score`(Task 1) · `settings.tech_demand_youth_fit_min`(Task 1).
- Produces:
  - `GapRepository.fetch_unprocessed_tech_demand(prompt_version, conf_min, window_days, limit) -> list` — 행 속성 `raw_id, sector_slug, title, url, body, ref_date`.
  - `GapRepository.upsert_silver(payload)` — `data_role`(기본 `'DISCOURSE_SIGNAL'`)·`raw_table_ref`(기본 `'raw_discourse_data'`)·`youth_fit_score`(기본 None) 파라미터 수용. discourse 호출부 무변경.
  - `GapRepository.project_to_gold(prompt_version, fit_min)` — 소스별 evidence join + youth_fit 게이트.

- [ ] **Step 1: `_UPSERT_SILVER` 파라미터화**

`gap_repository.py` 의 `_UPSERT_SILVER` 를 교체 — `data_role`·`raw_table_ref` 하드코딩을 바인드로, `youth_fit_score` 컬럼 추가:

```python
_UPSERT_SILVER = text(
    """
    INSERT INTO refined_gap_insights
        (sector_slug, data_role, extracted_problem, extracted_opportunity, detail_summary,
         stakeholders, next_actions, reference_date, raw_table_ref, raw_id,
         model_name, prompt_version, input_hash, youth_fit_score)
    VALUES
        (:sector_slug, :data_role, :problem, :opportunity, :detail,
         CAST(:stakeholders AS JSONB), CAST(:next_actions AS JSONB), :ref_date, :raw_table_ref, :raw_id,
         :model_name, :prompt_version, :input_hash, :youth_fit_score)
    ON CONFLICT (raw_table_ref, raw_id, prompt_version) DO NOTHING
    """
)
```

- [ ] **Step 2: `upsert_silver` 메서드에 기본값 주입**

`upsert_silver` 메서드를 교체 — discourse 호출부가 새 키를 안 보내도 동작하도록 기본값 설정:

```python
    async def upsert_silver(self, payload: dict) -> None:
        params = dict(payload)
        params.setdefault("data_role", "DISCOURSE_SIGNAL")
        params.setdefault("raw_table_ref", "raw_discourse_data")
        params.setdefault("youth_fit_score", None)
        params["stakeholders"] = json.dumps(payload.get("stakeholders") or [])
        params["next_actions"] = json.dumps(payload.get("next_actions") or [])
        await self.session.execute(_UPSERT_SILVER, params)
```

- [ ] **Step 3: KIAT fetch SQL + 메서드 추가**

`_FETCH_UNPROCESSED` 정의 아래에 추가:

```python
# 이미 분류된 KIAT/KISTEP 행 중 아직 tech_demand gap 처리 안 된 행(refined_gap_insights 없음).
_FETCH_UNPROCESSED_TECH_DEMAND = text(
    """
    SELECT c.raw_id AS raw_id, c.sector_slug AS sector_slug,
           i.title AS title, i.source_url AS url,
           i.title || E'\n' || COALESCE(i.abstract_text, '') || E'\n'
                  || COALESCE(i.raw_metadata->>'keyword', '') AS body,
           COALESCE(i.published_at::date, i.collected_at::date) AS ref_date
    FROM refined_text_sector_class c
    JOIN raw_innovation_data i ON i.id = c.raw_id
    LEFT JOIN refined_gap_insights g
           ON g.raw_table_ref = 'raw_innovation_data' AND g.raw_id = c.raw_id AND g.prompt_version = :pv
    WHERE c.raw_table_ref = 'raw_innovation_data'
      AND c.sector_slug IS NOT NULL
      AND c.confidence >= :conf_min
      AND i.source_type IN ('INNOVATION_KIAT_TECH_DEMAND', 'INNOVATION_KISTEP_REPORT')
      AND g.id IS NULL
      AND COALESCE(i.published_at::date, i.collected_at::date) >= CURRENT_DATE - CAST(:win AS INTEGER)
    ORDER BY c.confidence DESC
    LIMIT :lim
    """
)
```

`GapRepository.fetch_unprocessed` 메서드 아래에 추가:

```python
    async def fetch_unprocessed_tech_demand(
        self, prompt_version: str, conf_min: float, window_days: int, limit: int
    ) -> list:
        rows = (
            await self.session.execute(
                _FETCH_UNPROCESSED_TECH_DEMAND,
                {"pv": prompt_version, "conf_min": conf_min, "win": window_days, "lim": limit},
            )
        ).all()
        return list(rows)
```

- [ ] **Step 4: Gold fetch 소스-인지 일반화 + youth_fit 게이트**

`_FETCH_SILVER_FOR_GOLD` 를 교체 — 두 raw 테이블에서 evidence COALESCE, innovation 행에 youth_fit 게이트:

```python
# 유효 gap(문제 있음) Silver + 원천 메타(근거용). 소스(discourse/innovation)별 evidence COALESCE.
# innovation(tech_demand) 행은 youth_fit_score >= :fit_min 만 통과(discourse 는 NULL 이라 무조건 통과).
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
    WHERE g.prompt_version = :pv
      AND g.extracted_problem IS NOT NULL
      AND (g.raw_table_ref <> 'raw_innovation_data' OR g.youth_fit_score >= :fit_min)
    ORDER BY g.reference_date DESC NULLS LAST, g.id DESC
    """
)
```

- [ ] **Step 5: `_INSERT_EVIDENCE` 의 evidence_type 파라미터화**

`_INSERT_EVIDENCE` 를 교체 — type 하드코딩 제거:

```python
_INSERT_EVIDENCE = text(
    """
    INSERT INTO issue_evidences (issue_id, evidence_type, title, url, raw_table_ref, raw_id)
    VALUES (:issue_id, :evidence_type, :title, :url, :raw_table_ref, :raw_id)
    """
)
```

- [ ] **Step 6: `project_to_gold` 시그니처·게이트·evidence_type 도출**

`project_to_gold` 메서드를 교체 — `fit_min` 인자 추가, evidence_type 을 raw_table_ref 로 도출:

```python
    async def project_to_gold(self, prompt_version: str, fit_min: float = 0.0) -> int:
        """유효 gap Silver → gap_issues + issue_evidences 멱등 재생성. 적재 이슈 수 반환.

        discourse·innovation(tech_demand) 두 소스를 함께 재조립한다.
        innovation 행은 youth_fit_score >= fit_min 만 Gold 통과.
        """
        await self.session.execute(_CLEAR_GOLD)
        rows = (
            await self.session.execute(
                _FETCH_SILVER_FOR_GOLD, {"pv": prompt_version, "fit_min": fit_min}
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

- [ ] **Step 7: 기존 discourse gap 무회귀 확인 (호출부 점검)**

`GapRefineService.refine_and_serve` 는 `project_to_gold(PROMPT_VERSION)` 를 인자 없이 호출한다 — `fit_min` 기본 0.0 이라 discourse 행 무조건 통과(무회귀). 변경 불필요함을 확인.

Run: `cd backend && grep -rn "project_to_gold" domain/ scripts/`
Expected: `gap_refine_service.py` 의 호출이 `project_to_gold(PROMPT_VERSION)` (인자 1개) — 신규 기본값과 호환.

- [ ] **Step 8: 임포트·구문 스모크**

Run: `cd backend && python -c "from domain.market_insight.hub.repositories.gap_repository import GapRepository; print('ok', hasattr(GapRepository, 'fetch_unprocessed_tech_demand'))"`
Expected: `ok True`

- [ ] **Step 9: 커밋**

```bash
git add backend/domain/market_insight/hub/repositories/gap_repository.py
git commit -m "feat(insight): GapRepository 소스-인지 일반화 + youth_fit 게이트 (Phase 2)"
```

---

### Task 4: TechDemandGapService

**Files:**
- Create: `backend/domain/market_insight/hub/services/tech_demand_gap_service.py`

**Interfaces:**
- Consumes: `GapRepository.fetch_unprocessed_tech_demand` · `upsert_silver` · `project_to_gold`(Task 3) · `LlmClient.extract_tech_demand_gap`(Task 2) · `settings.tech_demand_youth_fit_min`(Task 1).
- Produces: `TechDemandGapService(session).refine_and_serve(window_days=90, limit=200) -> dict` 반환 `{"scanned", "gaps", "skipped", "issues"}`. `PROMPT_VERSION = "v1"`.

- [ ] **Step 1: 서비스 작성**

`backend/domain/market_insight/hub/services/tech_demand_gap_service.py`:

```python
# Silver/Gold — KIAT 수요기술에서 기업 미확보 갭·청년 기회를 LLM 추출해 Gap 카드로 사영하는 서비스

from __future__ import annotations

import hashlib

from sqlalchemy.ext.asyncio import AsyncSession

from core.config.settings import get_settings
from core.llm.client import LlmClient
from domain.market_insight.hub.repositories.gap_repository import GapRepository

# discourse gap 과 같은 pv — 공유 project_to_gold(pv 필터)가 두 소스를 함께 재조립하기 위함. 변경 금지.
PROMPT_VERSION = "v1"
ACTIVE_WINDOW_DAYS = 90
DEFAULT_LIMIT = 200
MAX_INPUT_CHARS = 3000
# LLM 추출 중간 적재·커밋 주기 — pool_recycle(5분) 초과 방지.
REFINE_CHUNK = 25


class TechDemandGapService:
    """분류된 KIAT/KISTEP → 미해결 갭·청년 기회 추출(refined_gap_insights) → gap_issues 사영."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = GapRepository(session)
        settings = get_settings()
        self._model = settings.llm_classify_model
        self._conf_min = settings.llm_classify_confidence_min
        self._fit_min = settings.tech_demand_youth_fit_min
        self._llm = LlmClient(api_key=settings.openai_api_key, model=self._model)

    async def refine_and_serve(
        self, window_days: int = ACTIVE_WINDOW_DAYS, limit: int = DEFAULT_LIMIT
    ) -> dict:
        """미처리 KIAT 을 추출·적재(전량) 후 Gold 재생성(youth_fit 게이트). 멱등.

        반환: {"scanned", "gaps", "skipped", "issues"}.
        """
        rows = await self.repo.fetch_unprocessed_tech_demand(
            PROMPT_VERSION, self._conf_min, window_days, limit
        )
        gaps = 0
        skipped = 0
        for i, r in enumerate(rows, start=1):
            input_text = (r.body or "").strip()[:MAX_INPUT_CHARS]
            result = await self._llm.extract_tech_demand_gap(input_text)
            await self.repo.upsert_silver(
                {
                    "sector_slug": r.sector_slug,
                    "data_role": "TECH_DEMAND_SIGNAL",
                    "problem": result["problem"],
                    "opportunity": result["opportunity"],
                    "detail": result["detail"],
                    "stakeholders": result["stakeholders"],
                    "next_actions": result["next_actions"],
                    "ref_date": r.ref_date,
                    "raw_table_ref": "raw_innovation_data",
                    "raw_id": r.raw_id,
                    "model_name": self._model,
                    "prompt_version": PROMPT_VERSION,
                    "input_hash": hashlib.sha256(input_text.encode("utf-8")).hexdigest(),
                    "youth_fit_score": result["youth_fit"],
                }
            )
            if result["problem"] is not None:
                gaps += 1
            else:
                skipped += 1
            if i % REFINE_CHUNK == 0:
                await self.session.commit()
        issues = await self.repo.project_to_gold(PROMPT_VERSION, self._fit_min)
        await self.session.commit()
        return {"scanned": len(rows), "gaps": gaps, "skipped": skipped, "issues": issues}
```

- [ ] **Step 2: 임포트 스모크**

Run: `cd backend && python -c "from domain.market_insight.hub.services.tech_demand_gap_service import TechDemandGapService, PROMPT_VERSION; print('ok', PROMPT_VERSION)"`
Expected: `ok v1`

- [ ] **Step 3: 커밋**

```bash
git add backend/domain/market_insight/hub/services/tech_demand_gap_service.py
git commit -m "feat(insight): TechDemandGapService — KIAT 수요기술 Gap 추출 (Phase 2)"
```

---

### Task 5: 스케줄러 잡 등록

**Files:**
- Modify: `backend/core/scheduler.py` (임포트, `_job_tech_demand_gap` 신설, `_REFINE_PIPELINE` 등록)

**Interfaces:**
- Consumes: `TechDemandGapService`(Task 4).
- Produces: `_job_tech_demand_gap()` 잡 · `_REFINE_PIPELINE` 의 `gap_refine` 다음 스텝.

- [ ] **Step 1: 임포트 추가**

`scheduler.py` 의 `GapRefineService` 임포트 줄 아래에 추가:

```python
from domain.market_insight.hub.services.tech_demand_gap_service import TechDemandGapService
```

- [ ] **Step 2: 잡 함수 추가**

`_job_gap_refine` 정의 바로 아래에 추가:

```python
async def _job_tech_demand_gap() -> dict[str, Any] | None:
    """분류 KIAT → 기업 미확보 갭·청년 기회 추출 → Gap 카드 재생성(youth_fit 게이트, 멱등). 키 없으면 스킵."""
    settings = get_settings()
    if not settings.openai_api_key:
        logger.warning("[scheduler] openai_api_key 없음 — 수요기술 Gap 정제 스킵")
        return None
    async with AsyncSessionLocal() as session:
        return await TechDemandGapService(session).refine_and_serve()
```

- [ ] **Step 3: 파이프라인 등록**

`_REFINE_PIPELINE` 튜플에서 `("gap_refine", _job_gap_refine),` 바로 아래에 추가:

```python
    ("tech_demand_gap",   _job_tech_demand_gap),
```

- [ ] **Step 4: 임포트·등록 스모크**

Run: `cd backend && python -c "from core.scheduler import _REFINE_PIPELINE; names=[n for n,_ in _REFINE_PIPELINE]; print('tech_demand_gap' in names, names.index('tech_demand_gap') == names.index('gap_refine')+1)"`
Expected: `True True`

- [ ] **Step 5: 커밋**

```bash
git add backend/core/scheduler.py
git commit -m "feat(insight): 수요기술 Gap 정제 잡 파이프라인 등록 (Phase 2)"
```

---

### Task 6: 소규모 백필 + 통합 검증

**Files:**
- Create: `backend/scripts/tech_demand_gap_backfill.py`

**Interfaces:**
- Consumes: `TechDemandGapService`(Task 4).

- [ ] **Step 1: 백필 스크립트 작성**

`backend/scripts/tech_demand_gap_backfill.py`:

```python
# KIAT 수요기술 Gap 소규모 백필 — limit 만큼 추출·youth_fit 분포 확인

from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import AsyncSessionLocal  # noqa: E402
from domain.market_insight.hub.services.tech_demand_gap_service import (  # noqa: E402
    TechDemandGapService,
)


async def main() -> None:
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    window = int(sys.argv[2]) if len(sys.argv) > 2 else 90
    async with AsyncSessionLocal() as session:
        result = await TechDemandGapService(session).refine_and_serve(
            window_days=window, limit=limit
        )
    print(f"백필 결과(limit={limit}, window={window}d): {result}")


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: 소규모 백필 실행**

Run: `cd backend && python scripts/tech_demand_gap_backfill.py 100`
Expected: `백필 결과(...): {'scanned': <N>, 'gaps': <G>, 'skipped': <S>, 'issues': <I>}` — scanned > 0(분류된 KIAT 존재 시), gaps + skipped == scanned.

주의: Phase 1 분류 백필이 선행돼야 입력이 있다. scanned == 0 이면 DB 콘솔에서 `refined_text_sector_class` 에 `raw_table_ref='raw_innovation_data'` 분류 행이 있는지 먼저 확인하고(없으면 Phase 1 백필 선행), confidence 게이트(`llm_classify_confidence_min`) 통과분이 있는지 본다:

```sql
SELECT count(*) FILTER (WHERE confidence >= 0.6) AS eligible, count(*) AS total
FROM refined_text_sector_class WHERE raw_table_ref = 'raw_innovation_data';
```

- [ ] **Step 3: Gold 통합·youth_fit 게이트 검증**

DB 콘솔에서 확인:

```sql
-- TECH_DEMAND evidence 가 Gold 에 통합됐는가
SELECT evidence_type, count(*) FROM issue_evidences GROUP BY evidence_type;
-- youth_fit 게이트: 임계 미만이 Silver 엔 있고 Gold 엔 없는가
SELECT count(*) FILTER (WHERE youth_fit_score < 0.5) AS below,
       count(*) FILTER (WHERE youth_fit_score >= 0.5) AS above
FROM refined_gap_insights WHERE data_role = 'TECH_DEMAND_SIGNAL';
```
Expected: `evidence_type` 에 `TECH_DEMAND` 행 존재(gaps>0 시), `below` 행이 Gold gap_issues 에는 미반영.

- [ ] **Step 4: discourse gap 무회귀 확인**

Run: `cd backend && python scripts/tech_demand_gap_parse_test.py`
Expected: `10 passed, 0 failed`

DB 콘솔: `SELECT data_role, count(*) FROM refined_gap_insights GROUP BY data_role;` — `DISCOURSE_SIGNAL` 건수가 백필 전후 동일(감소 없음).

- [ ] **Step 5: 커밋**

```bash
git add backend/scripts/tech_demand_gap_backfill.py
git commit -m "feat(insight): 수요기술 Gap 소규모 백필 스크립트 (Phase 2)"
```

- [ ] **Step 6: audit_trail 기록 (경로 승인 후)**

`backend/domain/market_insight/hub/docs/audit_trail.md` (또는 insight 도메인 audit_trail) 최상단에 Phase 2 항목 추가. **md 작성 전 사용자에게 경로 제시·승인 필요(CLAUDE.md #9).**

---

## 검증 요약 (전체)

- **단위** — `tech_demand_gap_parse_test.py` 9 PASS (파서·youth_fit 클램프·무귀속).
- **소스 disjoint** — `fetch_unprocessed_tech_demand` 가 KIAT/KISTEP innovation 만 반환(SQL `source_type IN`).
- **youth_fit 게이트** — Silver 전량 적재, Gold 는 `>= fit_min` 만(SQL 검증 Step 3).
- **무회귀** — discourse `DISCOURSE_SIGNAL` 건수 불변, `project_to_gold` 기본 `fit_min=0.0` 으로 discourse 무조건 통과.
- **멱등** — 자연키 `ON CONFLICT DO NOTHING`, 재실행 안전.

## 미해결·후속

- youth_fit 임계 0.5 는 시작값 — Step 3 분포 보고 `TECH_DEMAND_YOUTH_FIT_MIN` 재튜닝(Gold 재사영만, LLM 재실행 불필요).
- 전체 백필(window 확대)은 소규모 검증·튜닝 후 별도 실행.
- Gold 이중 사영(gap_refine·tech_demand 각각 project_to_gold) 단일화는 추후 검토(현재 멱등이라 무해).
