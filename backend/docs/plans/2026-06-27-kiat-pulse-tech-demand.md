# KIAT 수요기술 → Pulse `tech_demand` 축 연결 (Phase 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** KIAT 수요기술(미소비 dead data 96%)을 LLM 섹터 분류해 Pulse 신규 `tech_demand` 축으로 연결한다.

**Architecture:** 기존 LLM 섹터 분류 인프라(`refined_text_sector_class`)에 `raw_innovation_data`(KIAT·KISTEP만)를 분류 대상으로 추가하고, Pulse text axis 집계에 신규 `tech_demand` 축으로 소비한다. innovation(생산) 축과 분리하고 가중치 0.5를 부여한다.

**Tech Stack:** Python 3.13, SQLAlchemy 2.0(async, `text()` raw SQL), PostgreSQL(Neon), 자체 실행 테스트 스크립트(`scripts/*_test.py`, `check()` 패턴).

## Global Constraints

- 분류 대상은 `INNOVATION_KIAT_TECH_DEMAND`·`INNOVATION_KISTEP_REPORT` source_type **만**. GitHub·ArXiv·Customs·Techblog는 이미 innovation 축에 있으므로 제외(이중집계 방지).
- 신규 축 이름은 `tech_demand`, 가중치 `0.5`.
- `reference_date = COALESCE(published_at::date, collected_at::date)` (KIAT는 published_at 없음).
- 멱등 자연키 `(raw_table_ref, raw_id, prompt_version)` 유지. `raw_table_ref='raw_innovation_data'`.
- 분류 신뢰도 게이팅은 기존 `llm_classify_confidence_min`·축 SQL `:conf_min` 그대로 사용.
- 한국어 주석 종결은 `.` `?` `!` 만.

---

### Task 1: `tech_demand` 축 가중치 추가

**Files:**
- Modify: `backend/domain/market_insight/hub/services/pulse_pipeline.py` (`DEFAULT_AXIS_WEIGHTS`)
- Test: `backend/scripts/pulse_scoring_test.py`

**Interfaces:**
- Consumes: 기존 `fuse_signals(axis_signals, weights=None)` — weight dict로 축별 가중 합산(이미 범용).
- Produces: `DEFAULT_AXIS_WEIGHTS["tech_demand"] == 0.5`. 후속 Task 3의 `tech_demand` 축 신호가 이 가중치로 융합됨.

- [ ] **Step 1: 실패 테스트 작성** — `pulse_scoring_test.py`에 추가

```python
def test_tech_demand_axis_weight() -> None:
    from domain.market_insight.hub.services.pulse_pipeline import (
        AxisSignal, DEFAULT_AXIS_WEIGHTS, fuse_signals,
    )
    check("tech_demand 가중치 0.5 등록", DEFAULT_AXIS_WEIGHTS.get("tech_demand") == 0.5)
    # tech_demand 축 신호가 가중 0.5로 융합되는지(동일 섹터·일자, 값 10)
    fused = fuse_signals([AxisSignal("ai-data", date(2026, 6, 1), 10.0, "tech_demand")])
    check("tech_demand 융합값=10×0.5", fused and abs(fused[0].value - 5.0) < 1e-9)
```

- [ ] **Step 2: 실패 확인** — `DEFAULT_AXIS_WEIGHTS`에 키 없어 첫 check FAIL

Run: `$env:PYTHONIOENCODING='utf-8'; python backend/scripts/pulse_scoring_test.py`
Expected: `[FAIL] tech_demand 가중치 0.5 등록`

> 주의: `AxisSignal` 생성자 인자 순서(`sector_slug, reference_date, value, axis`)를 `pulse_pipeline.py` 정의로 먼저 확인하고 테스트의 인자를 맞춘다. 불일치 시 테스트를 정의에 맞게 수정한다.

- [ ] **Step 3: 가중치 추가** — `DEFAULT_AXIS_WEIGHTS`에 항목 추가

```python
DEFAULT_AXIS_WEIGHTS: dict[str, float] = {
    "innovation": 1.0,
    "economic": 1.0,
    "people": 0.7,
    # ... 기존 항목 유지 ...
    "tech_demand": 0.5,  # KIAT 수요기술 — 생산 신호의 보조(추후 튜닝)
}
```

- [ ] **Step 4: 통과 확인**

Run: `$env:PYTHONIOENCODING='utf-8'; python backend/scripts/pulse_scoring_test.py`
Expected: 전체 PASS (신규 2 check 포함)

- [ ] **Step 5: 커밋**

```bash
git add backend/domain/market_insight/hub/services/pulse_pipeline.py backend/scripts/pulse_scoring_test.py
git commit -m "feat(insight): Pulse tech_demand 축 가중치(0.5) 추가"
```

---

### Task 2: KIAT 분류 대상·fetch SQL 추가

**Files:**
- Modify: `backend/domain/market_insight/hub/services/text_sector_classify_service.py` (`_TARGET_TABLES`)
- Modify: `backend/domain/market_insight/hub/repositories/pulse_repository.py` (신규 `_FETCH_UNCLASSIFIED_INNOVATION` + `fetch_unclassified_text_rows` 분기)
- Test: 실 DB 통합 — `backend/scripts/kiat_pulse_integration_test.py` (신규)

**Interfaces:**
- Consumes: 기존 `PulseRepository.fetch_unclassified_text_rows(table_ref, prompt_version, window_days, limit)` → `list[(raw_id, body)]`. 기존 `_UPSERT_TEXT_SECTOR`.
- Produces: `table_ref='raw_innovation_data'` 호출 시 KIAT·KISTEP 미분류 행의 `(raw_id, title+abstract+keyword)` 반환. Task 3가 적재된 `refined_text_sector_class(raw_table_ref='raw_innovation_data')`를 소비.

- [ ] **Step 1: fetch SQL 신설** — `pulse_repository.py`에 `_FETCH_UNCLASSIFIED_DISCOURSE` 다음 추가

```python
# 미분류 innovation 행(KIAT·KISTEP만). 나머지 innovation 소스는 sector_source_map 으로
# 이미 innovation 축에 있으므로 제외(이중집계 방지). KIAT 는 published_at 없어 collected_at 기준.
_FETCH_UNCLASSIFIED_INNOVATION = text(
    """
    SELECT r.id AS raw_id,
           r.title || E'\\n' ||
           COALESCE(r.abstract_text, '') || E'\\n' ||
           COALESCE(r.raw_metadata->>'keyword', '') AS body
    FROM raw_innovation_data r
    LEFT JOIN refined_text_sector_class c
           ON c.raw_table_ref = 'raw_innovation_data'
          AND c.raw_id = r.id
          AND c.prompt_version = :pv
    WHERE c.id IS NULL
      AND r.source_type IN ('INNOVATION_KIAT_TECH_DEMAND', 'INNOVATION_KISTEP_REPORT')
      AND COALESCE(r.published_at::date, r.collected_at::date) >= CURRENT_DATE - CAST(:win AS INTEGER)
    ORDER BY r.id
    LIMIT :lim
    """
)
```

- [ ] **Step 2: `fetch_unclassified_text_rows` 분기 추가** — 기존 table_ref 분기(`_FETCH_UNCLASSIFIED_ECONOMIC`/`_DISCOURSE` 선택부)에 케이스 추가

```python
# fetch_unclassified_text_rows 내 분기(기존 economic/discourse 매핑에 추가):
_SQL_BY_TABLE = {
    "raw_economic_data": _FETCH_UNCLASSIFIED_ECONOMIC,
    "raw_discourse_data": _FETCH_UNCLASSIFIED_DISCOURSE,
    "raw_innovation_data": _FETCH_UNCLASSIFIED_INNOVATION,
}
```

> 기존 분기 구현 형태(딕셔너리 매핑 vs if/elif)를 먼저 읽고 그 형태에 맞춰 `raw_innovation_data` 케이스만 추가한다. 동일 파라미터(`pv`, `win`, `lim`)를 쓰므로 호출부 변경은 불필요하다.

- [ ] **Step 3: 분류 대상 테이블 추가** — `text_sector_classify_service.py`

```python
_TARGET_TABLES = ("raw_economic_data", "raw_discourse_data", "raw_innovation_data")
```

- [ ] **Step 4: 실 DB 통합 테스트 작성** — `backend/scripts/kiat_pulse_integration_test.py` 신설

```python
# KIAT → Pulse tech_demand 연결 실 DB 통합 검증
from __future__ import annotations
import asyncio, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
from core.database import AsyncSessionLocal
from domain.market_insight.hub.repositories.pulse_repository import PulseRepository

async def main() -> int:
    async with AsyncSessionLocal() as s:
        repo = PulseRepository(s)
        rows = await repo.fetch_unclassified_text_rows("raw_innovation_data", "v1", 3650, 5)
        ok = isinstance(rows, list)
        print(f"[{'PASS' if ok else 'FAIL'}] innovation fetch 반환 {len(rows)}건")
        if rows:
            rid, body = rows[0]
            print(f"  sample raw_id={rid} body_head={body[:80]!r}")
        return 0 if ok else 1

if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
```

- [ ] **Step 5: 통합 테스트 실행** — KIAT 행이 본문 조합으로 반환되는지 확인

Run: `$env:PYTHONIOENCODING='utf-8'; python backend/scripts/kiat_pulse_integration_test.py`
Expected: `[PASS] innovation fetch 반환 N건` (N>0, body에 수요기술명+개요)

- [ ] **Step 6: 커밋**

```bash
git add backend/domain/market_insight/hub/services/text_sector_classify_service.py backend/domain/market_insight/hub/repositories/pulse_repository.py backend/scripts/kiat_pulse_integration_test.py
git commit -m "feat(insight): KIAT·KISTEP 텍스트 섹터 분류 대상 추가(fetch SQL)"
```

---

### Task 3: text axis SQL에 `tech_demand` 축 UNION 추가

**Files:**
- Modify: `backend/domain/market_insight/hub/repositories/pulse_repository.py` (`_TEXT_SECTOR_AXIS_SQL`)
- Test: `backend/scripts/kiat_pulse_integration_test.py` (Task 2 파일에 검증 추가)

**Interfaces:**
- Consumes: Task 2가 적재한 `refined_text_sector_class(raw_table_ref='raw_innovation_data')`. 기존 axis SQL이 반환하는 `(axis, sector_slug, ref_date, count)` 형태.
- Produces: text axis 결과에 `axis='tech_demand'` 행 추가 → `fuse_signals`가 Task 1 가중치(0.5)로 융합.

- [ ] **Step 1: `_TEXT_SECTOR_AXIS_SQL`에 UNION 추가** — 기존 `economic_text`·`discourse` UNION 다음에 추가

```sql
    UNION ALL
    SELECT 'tech_demand' AS axis, c.sector_slug,
           COALESCE(r.published_at::date, r.collected_at::date) AS ref_date,
           COUNT(DISTINCT c.raw_id) AS c
    FROM refined_text_sector_class c
    JOIN raw_innovation_data r ON r.id = c.raw_id
    WHERE c.raw_table_ref = 'raw_innovation_data'
      AND c.sector_slug IS NOT NULL
      AND c.confidence >= :conf_min
    GROUP BY c.sector_slug, ref_date
```

> 기존 두 SELECT가 쓰는 바인드 파라미터(`:pv`, `:conf_min` 등)를 동일하게 맞춘다. `economic_text`/`discourse` 절의 `c.prompt_version = :pv` 조건이 있으면 `tech_demand` 절에도 동일하게 추가한다.

- [ ] **Step 2: 통합 검증 추가** — `kiat_pulse_integration_test.py`의 `main()`에 축 집계 확인 추가

```python
        # tech_demand 축 신호가 분류 적재 후 집계되는지(분류 0건이면 0행 — 백필 후 재확인)
        axis_rows = await repo.fetch_text_sector_axis("v1", 0.6, 3650)
        td = [a for a in axis_rows if getattr(a, "axis", None) == "tech_demand"]
        print(f"[INFO] tech_demand 축 신호 {len(td)}건 (백필 전 0 가능)")
```

> `fetch_text_sector_axis`의 실제 메서드명·시그니처를 `pulse_repository.py`에서 확인해 맞춘다(축 집계를 노출하는 기존 메서드 재사용, 없으면 raw SQL 직접 실행으로 대체).

- [ ] **Step 3: 통합 테스트 실행**

Run: `$env:PYTHONIOENCODING='utf-8'; python backend/scripts/kiat_pulse_integration_test.py`
Expected: `[PASS]` + `[INFO] tech_demand 축 신호 ...건` (백필 전이라 0일 수 있음)

- [ ] **Step 4: 커밋**

```bash
git add backend/domain/market_insight/hub/repositories/pulse_repository.py backend/scripts/kiat_pulse_integration_test.py
git commit -m "feat(insight): Pulse text axis에 tech_demand(KIAT) 축 집계 추가"
```

---

### Task 4: 백필 실행 + 재측정 검증

**Files:**
- 실행만(코드 변경 없음). 검증: `backend/scripts/bronze_null_audit.py`, `kiat_pulse_integration_test.py`

**Interfaces:**
- Consumes: Task 2·3 완료된 분류·축 파이프라인. 기존 `TextSectorClassifyService.classify_unclassified(window_days, limit)`.

- [ ] **Step 1: 백필 1회 실행** — 분류 window를 확대해 KIAT 누적분 분류(멱등)

```python
# 임시 실행(REPL 또는 1회성 스크립트): window 확대로 KIAT 11,226건 분류
# python -c 사용 대신 1회성 스크립트로 실행:
#   classify_unclassified(window_days=3650, limit=2000)을 누적 0건까지 반복
```

실행 1회성 스크립트 `backend/scripts/_kiat_backfill_run.py`(확인 후 삭제):

```python
from __future__ import annotations
import asyncio, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
from core.database import AsyncSessionLocal
from domain.market_insight.hub.services.text_sector_classify_service import TextSectorClassifyService

async def main() -> None:
    total = 0
    while True:
        async with AsyncSessionLocal() as s:
            r = await TextSectorClassifyService(s).classify_unclassified(window_days=3650, limit=1000)
        total += r["scanned"]
        print(r, "누적", total)
        if r["scanned"] == 0:
            break

if __name__ == "__main__":
    asyncio.run(main())
```

Run: `$env:PYTHONIOENCODING='utf-8'; python backend/scripts/_kiat_backfill_run.py`
Expected: scanned 누적 증가 후 0으로 종료(KIAT·KISTEP 분류 완료). ⚠️ gpt-4o-mini 비용 발생.

- [ ] **Step 2: 분류 적재·축 신호 재측정**

Run: `$env:PYTHONIOENCODING='utf-8'; python backend/scripts/kiat_pulse_integration_test.py`
Expected: `[INFO] tech_demand 축 신호 N건` (N>0 — 백필 후 분류 적재됨)

- [ ] **Step 3: dead data 전환 확인** — Bronze 재측정

Run: `$env:PYTHONIOENCODING='utf-8'; python backend/scripts/bronze_null_audit.py`
Expected: `refined_text_sector_class`에 `raw_innovation_data` 분류 다수(이전 0 → 분류됨). innovation 활용률 전환 확인.

- [ ] **Step 4: 1회성 백필 스크립트 삭제 + 커밋**

```bash
rm backend/scripts/_kiat_backfill_run.py
git add -A
git commit -m "chore(insight): KIAT tech_demand 백필 실행(검증 완료)"
```

---

## 검증 요약

- **순수 로직(무DB)**: Task 1 가중치·융합 — `pulse_scoring_test.py`.
- **SQL·파이프라인(실 DB)**: Task 2·3 fetch·축 집계 — `kiat_pulse_integration_test.py`.
- **회귀**: 기존 `pulse_scoring_test.py`·`bronze_expansion_parse_test.py` 전체 PASS 유지(economic/discourse 분류 영향 없음 — `_TARGET_TABLES` 추가만, 기존 SQL 불변).
- **효과 측정**: `bronze_null_audit.py` 전후 비교로 KIAT dead data 전환 확인.
