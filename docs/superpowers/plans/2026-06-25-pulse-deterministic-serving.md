# Pulse 결정론 부가 서빙 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `pulse_metrics_log`(Gold) 시계열을 즉석 집계해 제거됐던 PulseTab 시각화(속도계/주간지수·연간 모멘텀 차트·섹터×시간 히트맵·관심 점유율)를 실데이터로 복원한다.

**Architecture:** 읽기 전용 즉석 집계. 라우터 2개 엔드포인트 → `PulseRepository`가 4개 raw SQL 실행 → **DB 비의존 순수함수 `assemble_overview()`** 가 응답 조립. 새 테이블·마이그레이션·스케줄러 잡 없음. 프론트는 TanStack Query 훅으로 라이브 바인딩(mock 폴백 없음).

**Tech Stack:** FastAPI · SQLAlchemy 2.0 async(asyncpg) · PostgreSQL(`pulse_metrics_log`·`sectors`) · Next.js/React 19/TS · TanStack Query · axios.

**Spec:** [docs/superpowers/specs/2026-06-25-pulse-deterministic-serving-design.md](../specs/2026-06-25-pulse-deterministic-serving-design.md)

## Global Constraints

- **브랜치**: `feat/pulse-deterministic-serving` (이미 체크아웃됨).
- **한국어 문장 종결**: `.` `?` `!` 만. `:` 로 끝내지 않기.
- **새 소스 파일 첫 줄**: 한 줄 한국어 주석으로 역할 명시(config 제외).
- **테스트 규약**: `backend/scripts/*_test.py` 독립 실행 스크립트(pytest 아님). 전역 `PASS`/`FAIL` + `check(name, cond)` + `main()`가 `FAIL` 있으면 1 반환. 실행 `python scripts/<name>_test.py`, 기대 `FAIL=0`.
- **asyncpg 함정**: nullable 비교는 `CAST(:p AS …) IS NULL`. 본 작업 SQL은 nullable 바인드가 없으나 정수 윈도우는 `make_interval(weeks => :weeks)` 사용.
- **순수함수 분리**: 비자명 로직은 DB 비의존 순수함수로(기존 `pulse_pipeline.py` 패턴).
- **status_badge 닫힌 집합**: 태풍급/급상승/상승/보합/하락 — 프론트 표시와 동기화.
- **프론트 규약**: mock 폴백 없음. 로딩/에러/빈데이터는 `PanelStatus`. `useQuery`는 `staleTime: STALE(5분)` + `retry: 1`.
- **선결**: Neon에 `pulse_metrics_log` 마이그레이션(head `f8c2e6a0d3b7`) 적용 확인. 미적용이면 기존 `/api/insight/pulse`도 실패.

---

### Task 1: 순수 조립 함수 `assemble_overview()` (TDD)

DB 비의존 결정론 로직. 입력 raw 집계 dict 묶음 → overview 응답 dict.

**Files:**
- Create: `backend/domain/market_insight/hub/services/pulse_overview.py`
- Test: `backend/scripts/pulse_overview_test.py`

**Interfaces:**
- Produces:
  - `assemble_overview(latest: list[dict], monthly: list[dict], weekly: list[dict], daily_avgs: list[dict]) -> dict`
    - `latest` 항목: `{"sector_slug","sector_name","accent_color","score":int,"momentum_pct":float|None}`
    - `monthly` 항목: `{"bucket":"YYYY-MM","value":int}`
    - `weekly` 항목: `{"sector_slug","bucket":"IYYY-Www","score":int}`
    - `daily_avgs` 항목: `{"recorded_date":"YYYY-MM-DD","avg_score":float}` — 최신순(desc), 길이 0~2
    - 반환: `{"gauge":{...}, "momentum_series":[...], "heatmap":{"buckets":[...],"rows":[...]}, "share":[...]}`(스펙 §2.1 형태)

- [ ] **Step 1: 실패하는 테스트 작성**

`backend/scripts/pulse_overview_test.py`:
```python
# Pulse overview 순수 조립 함수 무DB 검증 테스트

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from domain.market_insight.hub.services.pulse_overview import assemble_overview  # noqa: E402

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


def _latest() -> list[dict]:
    return [
        {"sector_slug": "ai-data", "sector_name": "AI·데이터", "accent_color": "#6366f1", "score": 90, "momentum_pct": 40.0},
        {"sector_slug": "fintech", "sector_name": "핀테크", "accent_color": "#10b981", "score": 60, "momentum_pct": 5.0},
    ]


def test_gauge_normal() -> None:
    out = assemble_overview(
        _latest(),
        monthly=[{"bucket": "2026-05", "value": 70}, {"bucket": "2026-06", "value": 75}],
        weekly=[],
        daily_avgs=[{"recorded_date": "2026-06-25", "avg_score": 75.0}, {"recorded_date": "2026-06-24", "avg_score": 60.0}],
    )
    g = out["gauge"]
    check("weekly_index = mean(90,60)=75", g["weekly_index"] == 75)
    check("speed_kmh = round(75*1.8)=135", g["speed_kmh"] == 135)
    check("day_delta_pct = (75-60)/60*100=25.0", g["day_delta_pct"] == 25.0)
    check("top_mover = ai-data(40.0)", g["top_mover"]["sector_slug"] == "ai-data")


def test_momentum_sorted() -> None:
    out = assemble_overview(
        _latest(),
        monthly=[{"bucket": "2026-06", "value": 75}, {"bucket": "2026-04", "value": 60}, {"bucket": "2026-05", "value": 70}],
        weekly=[],
        daily_avgs=[],
    )
    buckets = [p["bucket"] for p in out["momentum_series"]]
    check("momentum 오름차순 정렬", buckets == ["2026-04", "2026-05", "2026-06"])
    check("day_delta 날짜<2 → null", out["gauge"]["day_delta_pct"] is None)


def test_heatmap_pivot_and_null() -> None:
    out = assemble_overview(
        _latest(),
        monthly=[],
        weekly=[
            {"sector_slug": "ai-data", "bucket": "2026-W25", "score": 88},
            {"sector_slug": "ai-data", "bucket": "2026-W24", "score": 80},
            {"sector_slug": "fintech", "bucket": "2026-W25", "score": 55},
        ],
        daily_avgs=[],
    )
    hm = out["heatmap"]
    check("buckets 오름차순 distinct", hm["buckets"] == ["2026-W24", "2026-W25"])
    check("행 순서 = score 내림차순(ai-data 먼저)", hm["rows"][0]["sector_slug"] == "ai-data")
    fin_cells = {c["bucket"]: c["score"] for c in hm["rows"][1]["cells"]}
    check("결측 칸 null(fintech W24)", fin_cells["2026-W24"] is None)
    check("존재 칸 값(fintech W25=55)", fin_cells["2026-W25"] == 55)


def test_share_and_empty() -> None:
    out = assemble_overview(_latest(), monthly=[], weekly=[], daily_avgs=[])
    share = {s["sector_slug"]: s["pct"] for s in out["share"]}
    check("share ai-data = 90/150*100=60.0", share["ai-data"] == 60.0)
    check("share 합 100", round(sum(s["pct"] for s in out["share"]), 1) == 100.0)

    empty = assemble_overview([], monthly=[], weekly=[], daily_avgs=[])
    check("빈 latest → weekly_index null", empty["gauge"]["weekly_index"] is None)
    check("빈 latest → speed_kmh null", empty["gauge"]["speed_kmh"] is None)
    check("빈 latest → top_mover null", empty["gauge"]["top_mover"] is None)
    check("빈 latest → share []", empty["share"] == [])


def test_top_mover_none_momentum() -> None:
    latest = [{"sector_slug": "x", "sector_name": "X", "accent_color": "#000", "score": 50, "momentum_pct": None}]
    out = assemble_overview(latest, monthly=[], weekly=[], daily_avgs=[])
    check("모멘텀 전부 null → top_mover null", out["gauge"]["top_mover"] is None)


def main() -> int:
    test_gauge_normal()
    test_momentum_sorted()
    test_heatmap_pivot_and_null()
    test_share_and_empty()
    test_top_mover_none_momentum()
    print(f"\n결과: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd backend && python scripts/pulse_overview_test.py`
Expected: FAIL — `ModuleNotFoundError: ... pulse_overview` (모듈 미존재).

- [ ] **Step 3: 최소 구현 작성**

`backend/domain/market_insight/hub/services/pulse_overview.py`:
```python
# Pulse overview 결정론 조립 — raw 집계 dict → 대시보드 overview 응답(DB 비의존 순수함수)

from __future__ import annotations

# 주간지수(0~100)를 속도계 km/h(0~180)로 매핑하는 계수. 지수 100 → 180km/h.
_KMH_PER_INDEX = 1.8


def _gauge(latest: list[dict], daily_avgs: list[dict]) -> dict:
    scores = [r["score"] for r in latest]
    weekly_index = round(sum(scores) / len(scores)) if scores else None
    speed_kmh = round(weekly_index * _KMH_PER_INDEX) if weekly_index is not None else None

    day_delta_pct = None
    if len(daily_avgs) >= 2 and daily_avgs[1]["avg_score"]:
        d0, d1 = daily_avgs[0]["avg_score"], daily_avgs[1]["avg_score"]
        day_delta_pct = round((d0 - d1) / d1 * 100, 1)

    movers = [r for r in latest if r.get("momentum_pct") is not None]
    top_mover = None
    if movers:
        top = max(movers, key=lambda r: r["momentum_pct"])
        top_mover = {
            "sector_slug": top["sector_slug"],
            "sector_name": top["sector_name"],
            "momentum_pct": top["momentum_pct"],
        }
    return {
        "weekly_index": weekly_index,
        "speed_kmh": speed_kmh,
        "day_delta_pct": day_delta_pct,
        "top_mover": top_mover,
    }


def _heatmap(rows_latest: list[dict], weekly: list[dict]) -> dict:
    buckets = sorted({w["bucket"] for w in weekly})
    by_sector: dict[str, dict[str, int]] = {}
    for w in weekly:
        by_sector.setdefault(w["sector_slug"], {})[w["bucket"]] = w["score"]
    rows = [
        {
            "sector_slug": r["sector_slug"],
            "sector_name": r["sector_name"],
            "accent_color": r["accent_color"],
            "cells": [
                {"bucket": b, "score": by_sector.get(r["sector_slug"], {}).get(b)} for b in buckets
            ],
        }
        for r in rows_latest
    ]
    return {"buckets": buckets, "rows": rows}


def _share(latest: list[dict]) -> list[dict]:
    total = sum(r["score"] for r in latest)
    if total <= 0:
        return []
    return [
        {
            "sector_slug": r["sector_slug"],
            "sector_name": r["sector_name"],
            "pct": round(r["score"] / total * 100, 1),
        }
        for r in latest
    ]


def assemble_overview(
    latest: list[dict],
    monthly: list[dict],
    weekly: list[dict],
    daily_avgs: list[dict],
) -> dict:
    """raw 집계 입력을 대시보드 overview 응답 형태로 조립한다(결정론·DB 비의존)."""
    rows_latest = sorted(latest, key=lambda r: r["score"], reverse=True)
    momentum_series = sorted(
        ({"bucket": m["bucket"], "value": int(m["value"])} for m in monthly),
        key=lambda p: p["bucket"],
    )
    return {
        "gauge": _gauge(rows_latest, daily_avgs),
        "momentum_series": momentum_series,
        "heatmap": _heatmap(rows_latest, weekly),
        "share": _share(rows_latest),
    }
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd backend && python scripts/pulse_overview_test.py`
Expected: PASS — 마지막 줄 `결과: PASS=14 FAIL=0`.

- [ ] **Step 5: 커밋**

```bash
git add backend/domain/market_insight/hub/services/pulse_overview.py backend/scripts/pulse_overview_test.py
git commit -m "feat(insight): Pulse overview 결정론 조립 순수함수 + 무DB 테스트"
```

---

### Task 2: 리포지토리 집계 메서드 `fetch_overview()` · `fetch_history()`

raw SQL 4종 + 단일 섹터 시계열. `pulse_repository.py`에 추가, Task 1 순수함수로 위임.

**Files:**
- Modify: `backend/domain/market_insight/hub/repositories/pulse_repository.py` (메서드·SQL 상수 추가, 파일 끝)

**Interfaces:**
- Consumes: `assemble_overview(latest, monthly, weekly, daily_avgs)` (Task 1).
- Produces:
  - `PulseRepository.fetch_overview(heatmap_weeks: int = 8, momentum_months: int = 12) -> dict`
  - `PulseRepository.fetch_history(sector_slug: str, weeks: int = 26) -> dict | None` (섹터 미존재 → None)

- [ ] **Step 1: SQL 상수 추가**

`pulse_repository.py` 상단 import 아래에 추가(`from sqlalchemy import text` 는 이미 존재):
```python
# overview 월 버킷 평균 score 시계열.
_OVERVIEW_MONTHLY_SQL = text(
    """
    SELECT to_char(recorded_date, 'YYYY-MM') AS bucket, round(avg(score)) AS value
    FROM pulse_metrics_log
    WHERE recorded_date >= (CURRENT_DATE - make_interval(months => :months))
    GROUP BY 1
    ORDER BY 1
    """
)

# overview 섹터×ISO주 마지막 score(주별 최신 1행).
_OVERVIEW_WEEKLY_SQL = text(
    """
    SELECT DISTINCT ON (sector_slug, date_trunc('week', recorded_date))
        sector_slug,
        to_char(date_trunc('week', recorded_date), 'IYYY-"W"IW') AS bucket,
        score
    FROM pulse_metrics_log
    WHERE recorded_date >= (CURRENT_DATE - make_interval(weeks => :weeks))
    ORDER BY sector_slug, date_trunc('week', recorded_date), recorded_date DESC
    """
)

# overview 전 섹터 일평균 score 최근 2일(전일 대비 변동용).
_OVERVIEW_DAILY_AVG_SQL = text(
    """
    SELECT recorded_date, avg(score) AS avg_score
    FROM pulse_metrics_log
    GROUP BY recorded_date
    ORDER BY recorded_date DESC
    LIMIT 2
    """
)

# 단일 섹터 시계열(드릴다운).
_HISTORY_SQL = text(
    """
    SELECT recorded_date, score, status_badge, momentum_pct
    FROM pulse_metrics_log
    WHERE sector_slug = :slug
      AND recorded_date >= (CURRENT_DATE - make_interval(weeks => :weeks))
    ORDER BY recorded_date ASC
    """
)

# 섹터 메타(이름) 조회 — history 404 판별.
_SECTOR_NAME_SQL = text("SELECT name_ko FROM sectors WHERE slug = :slug")
```

- [ ] **Step 2: 메서드 추가**

`pulse_repository.py` `PulseRepository` 클래스 끝(`fetch_latest_gold` 다음)에 추가:
```python
    async def fetch_overview(self, heatmap_weeks: int = 8, momentum_months: int = 12) -> dict:
        """대시보드 overview 집계 — 최신/월/주/일평균 raw SQL → 순수 조립."""
        from domain.market_insight.hub.services.pulse_overview import assemble_overview

        latest_rows = (await self.session.execute(_LATEST_GOLD_SQL)).all()
        latest = [
            {
                "sector_slug": r.sector_slug,
                "sector_name": r.name_ko,
                "accent_color": r.accent_color,
                "score": r.score,
                "momentum_pct": float(r.momentum_pct) if r.momentum_pct is not None else None,
            }
            for r in latest_rows
        ]
        monthly = [
            {"bucket": r.bucket, "value": int(r.value)}
            for r in (await self.session.execute(_OVERVIEW_MONTHLY_SQL, {"months": momentum_months})).all()
        ]
        weekly = [
            {"sector_slug": r.sector_slug, "bucket": r.bucket, "score": r.score}
            for r in (await self.session.execute(_OVERVIEW_WEEKLY_SQL, {"weeks": heatmap_weeks})).all()
        ]
        daily_avgs = [
            {"recorded_date": r.recorded_date.isoformat(), "avg_score": float(r.avg_score)}
            for r in (await self.session.execute(_OVERVIEW_DAILY_AVG_SQL)).all()
        ]
        return assemble_overview(latest, monthly, weekly, daily_avgs)

    async def fetch_history(self, sector_slug: str, weeks: int = 26) -> dict | None:
        """단일 섹터 Pulse 시계열(날짜 오름차순). 섹터 미존재 시 None."""
        name_row = (await self.session.execute(_SECTOR_NAME_SQL, {"slug": sector_slug})).first()
        if name_row is None:
            return None
        rows = (
            await self.session.execute(_HISTORY_SQL, {"slug": sector_slug, "weeks": weeks})
        ).all()
        points = [
            {
                "recorded_date": r.recorded_date.isoformat(),
                "score": r.score,
                "status_badge": r.status_badge,
                "momentum_pct": float(r.momentum_pct) if r.momentum_pct is not None else None,
            }
            for r in rows
        ]
        return {"sector_slug": sector_slug, "sector_name": name_row.name_ko, "points": points}
```

- [ ] **Step 3: 임포트 검증(구문·순환참조 없음)**

Run: `cd backend && python -c "from domain.market_insight.hub.repositories.pulse_repository import PulseRepository; print('ok')"`
Expected: `ok` (구문 오류·순환 임포트 없음).

- [ ] **Step 4: 기존 단위 테스트 회귀 확인**

Run: `cd backend && python scripts/pulse_scoring_test.py && python scripts/pulse_overview_test.py`
Expected: 둘 다 `FAIL=0`.

- [ ] **Step 5: 커밋**

```bash
git add backend/domain/market_insight/hub/repositories/pulse_repository.py
git commit -m "feat(insight): PulseRepository overview·history 집계 메서드"
```

---

### Task 3: 라우터 엔드포인트 `GET /pulse/overview` · `GET /pulse/{sector}/history`

**Files:**
- Modify: `backend/api/v1/insight/insight_routor.py` (`/pulse/refine` 다음에 추가)

**Interfaces:**
- Consumes: `PulseRepository.fetch_overview(...)`·`fetch_history(...)` (Task 2).
- Produces: HTTP `GET /api/insight/pulse/overview`, `GET /api/insight/pulse/{sector}/history`.

- [ ] **Step 1: 엔드포인트 추가**

`insight_routor.py`의 `refine_pulse` 함수 다음(`@router.get("/gap")` 앞)에 추가:
```python
@router.get("/pulse/overview")
async def get_pulse_overview(
    heatmap_weeks: int = Query(default=8, ge=1, le=52, description="히트맵 주 수"),
    momentum_months: int = Query(default=12, ge=1, le=36, description="모멘텀 차트 월 수"),
    db: AsyncSession = Depends(get_db),
):
    """Pulse overview 서빙 — 속도계·모멘텀 시계열·섹터×시간 히트맵·관심 점유율."""
    try:
        data = await PulseRepository(db).fetch_overview(heatmap_weeks, momentum_months)
        return {"success": True, **data}
    except Exception as e:
        logger.error(f"Pulse overview 조회 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Pulse overview 조회 실패: {str(e)}")


@router.get("/pulse/{sector}/history")
async def get_pulse_history(
    sector: str,
    weeks: int = Query(default=26, ge=1, le=104, description="조회 주 범위"),
    db: AsyncSession = Depends(get_db),
):
    """단일 섹터 Pulse 시계열(드릴다운)."""
    try:
        data = await PulseRepository(db).fetch_history(sector, weeks)
        if data is None:
            raise HTTPException(status_code=404, detail="섹터를 찾을 수 없습니다.")
        return {"success": True, **data}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Pulse history 조회 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Pulse history 조회 실패: {str(e)}")
```

- [ ] **Step 2: 앱 부팅·라우트 등록 확인**

Run: `cd backend && python -c "from main import app; paths=[r.path for r in app.routes]; print('/api/insight/pulse/overview' in paths, '/api/insight/pulse/{sector}/history' in paths)"`
Expected: `True True`.

- [ ] **Step 3: 선결(DB) 확인 + 실 응답 스모크**

서버 기동: `cd backend && python -m uvicorn main:app --port 8000` (별도 셸).
Run: `curl -s http://localhost:8000/api/insight/pulse/overview | python -m json.tool | head -30`
Expected: `"success": true` + `gauge`/`momentum_series`/`heatmap`/`share` 키 존재. (500이면 `pulse_metrics_log` 미마이그레이션 — Global Constraints 선결 확인.)
Run: `curl -s "http://localhost:8000/api/insight/pulse/ai-data/history?weeks=52" | python -m json.tool | head -20`
Expected: `"success": true` + `points` 배열. 없는 섹터는 404: `curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/insight/pulse/nope/history` → `404`.

- [ ] **Step 4: 커밋**

```bash
git add backend/api/v1/insight/insight_routor.py
git commit -m "feat(insight): Pulse overview·history 엔드포인트 2종"
```

---

### Task 4: 프론트 API 클라이언트 + 훅

**Files:**
- Modify: `www.yeotaeho.kr/src/lib/api/dashboard.ts` (파일 끝, `fetchSyncScores` 다음 / `ddayLabel` 앞)
- Modify: `www.yeotaeho.kr/src/hooks/useDashboard.ts`

**Interfaces:**
- Consumes: `GET /api/insight/pulse/overview`·`/{sector}/history` (Task 3).
- Produces: `fetchPulseOverview()`·`fetchPulseHistory(sector)` + `usePulseOverview()`·`usePulseHistory(sector?)`, 타입 `PulseOverview`·`PulseHistory`.

- [ ] **Step 1: `dashboard.ts`에 타입·페처 추가**

`fetchSyncScores` 함수 다음에 추가:
```typescript
export interface PulseGauge {
  weekly_index: number | null;
  speed_kmh: number | null;
  day_delta_pct: number | null;
  top_mover: { sector_slug: string; sector_name: string; momentum_pct: number } | null;
}
export interface PulseMomentumPoint {
  bucket: string;
  value: number;
}
export interface PulseHeatmapCell {
  bucket: string;
  score: number | null;
}
export interface PulseHeatmapRow {
  sector_slug: string;
  sector_name: string;
  accent_color: string;
  cells: PulseHeatmapCell[];
}
export interface PulseShareItem {
  sector_slug: string;
  sector_name: string;
  pct: number;
}
export interface PulseOverview {
  gauge: PulseGauge;
  momentum_series: PulseMomentumPoint[];
  heatmap: { buckets: string[]; rows: PulseHeatmapRow[] };
  share: PulseShareItem[];
}

export async function fetchPulseOverview(): Promise<PulseOverview> {
  const { data } = await apiClient.get('/api/insight/pulse/overview');
  return {
    gauge: data.gauge,
    momentum_series: data.momentum_series ?? [],
    heatmap: data.heatmap ?? { buckets: [], rows: [] },
    share: data.share ?? [],
  };
}

export interface PulseHistoryPoint {
  recorded_date: string;
  score: number;
  momentum_pct: number | null;
  status_badge: string;
}
export interface PulseHistory {
  sector_slug: string;
  sector_name: string;
  points: PulseHistoryPoint[];
}

export async function fetchPulseHistory(sector: string): Promise<PulseHistory> {
  const { data } = await apiClient.get(`/api/insight/pulse/${sector}/history`);
  return data;
}
```

- [ ] **Step 2: `useDashboard.ts`에 훅 추가**

import 블록에 `fetchPulseOverview`·`fetchPulseHistory` 추가하고, 파일 끝에:
```typescript
export function usePulseOverview() {
  return useQuery({
    queryKey: ['pulse-overview'],
    queryFn: fetchPulseOverview,
    staleTime: STALE,
    retry: 1,
  });
}

export function usePulseHistory(sector?: string) {
  return useQuery({
    queryKey: ['pulse-history', sector],
    queryFn: () => fetchPulseHistory(sector as string),
    enabled: !!sector,
    staleTime: STALE,
    retry: 1,
  });
}
```

- [ ] **Step 3: 타입 체크**

Run: `cd www.yeotaeho.kr && pnpm exec tsc --noEmit`
Expected: 오류 없음(종료코드 0).

- [ ] **Step 4: 커밋**

```bash
git add www.yeotaeho.kr/src/lib/api/dashboard.ts www.yeotaeho.kr/src/hooks/useDashboard.ts
git commit -m "feat(web): Pulse overview·history API 클라이언트·훅"
```

---

### Task 5: PulseTab 섹션 복원 (속도계·모멘텀·히트맵·점유율)

기존 PulseTab(섹터 카드)에 4개 섹션을 추가. 라이브 데이터 + 실제 12섹터.

**Files:**
- Modify: `www.yeotaeho.kr/src/components/features/dashboard/PulseTab.tsx`

**Interfaces:**
- Consumes: `usePulseOverview()` (Task 4), `PulseOverview` 타입.

- [ ] **Step 1: PulseTab 전체 교체**

`PulseTab.tsx` 전체를 아래로 교체(기존 섹터 카드 섹션 유지 + overview 섹션 추가):
```tsx
"use client";

/**
 * 실시간 펄스(Pulse) 탭 — 섹터 카드 + 속도계·모멘텀·히트맵·점유율(Pulse Gold 즉석 집계).
 */

import { usePulse, usePulseOverview } from "@/hooks/useDashboard";
import type { PulseHeatmapRow, PulseMomentumPoint } from "@/lib/api/dashboard";
import { PanelStatus } from "./PanelStatus";

function heatTone(score: number | null): string {
  if (score == null) return "bg-slate-100 text-slate-400 dark:bg-slate-700 dark:text-slate-500";
  if (score >= 85) return "bg-indigo-600 text-white";
  if (score >= 70) return "bg-indigo-400 text-white";
  if (score >= 55) return "bg-indigo-200 text-indigo-900";
  return "bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-200";
}

function MomentumChart({ points }: { points: PulseMomentumPoint[] }) {
  if (points.length === 0) {
    return <p className="text-sm text-slate-400">시계열 데이터가 아직 없습니다.</p>;
  }
  const w = 560;
  const h = 160;
  const max = Math.max(...points.map((p) => p.value), 1);
  const min = Math.min(...points.map((p) => p.value), 0);
  const span = max - min || 1;
  const xAt = (i: number) => (points.length === 1 ? w / 2 : (i / (points.length - 1)) * w);
  const yAt = (v: number) => h - ((v - min) / span) * h;
  const line = points.map((p, i) => `${i === 0 ? "M" : "L"}${xAt(i)},${yAt(p.value)}`).join(" ");
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-full h-40" role="img" aria-label="연간 모멘텀 트렌드 차트">
      <path d={`${line} L${xAt(points.length - 1)},${h} L${xAt(0)},${h} Z`} fill="#6366f1" fillOpacity="0.12" />
      <path d={line} fill="none" stroke="#6366f1" strokeWidth="2" />
      {points.map((p, i) => (
        <circle key={p.bucket} cx={xAt(i)} cy={yAt(p.value)} r="2.5" fill="#6366f1" />
      ))}
    </svg>
  );
}

function Heatmap({ buckets, rows }: { buckets: string[]; rows: PulseHeatmapRow[] }) {
  if (buckets.length === 0 || rows.length === 0) {
    return <p className="text-sm text-slate-400">히트맵 데이터가 아직 없습니다.</p>;
  }
  return (
    <div className="overflow-x-auto">
      <table className="border-separate" style={{ borderSpacing: "4px" }}>
        <thead>
          <tr>
            <th className="text-left text-xs font-medium text-slate-400 pr-2" />
            {buckets.map((b) => (
              <th key={b} className="text-[10px] font-medium text-slate-400 text-center">
                {b}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.sector_slug}>
              <td className="text-xs font-medium text-slate-600 dark:text-slate-300 pr-2 whitespace-nowrap">
                {row.sector_name}
              </td>
              {row.cells.map((c) => (
                <td
                  key={`${row.sector_slug}-${c.bucket}`}
                  className={`h-8 w-12 rounded text-center text-[11px] font-semibold ${heatTone(c.score)}`}
                  title={`${row.sector_name} / ${c.bucket} / ${c.score ?? "—"}`}
                >
                  {c.score ?? "—"}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function PulseTab() {
  const { data: livePulse, isLoading, isError } = usePulse();
  const { data: overview, isLoading: ovLoading, isError: ovError } = usePulseOverview();

  const sectorCards = (livePulse ?? []).map((s) => ({
    slug: s.sector_slug,
    title: s.sector_name,
    status: s.status_badge,
    score: s.score,
    momentum: s.momentum_pct,
    accent: s.accent_color as string | null,
  }));

  const g = overview?.gauge;

  return (
    <div className="w-full flex flex-col gap-6 font-sans">
      {/* 1. 속도계 / 주간지수 */}
      <PanelStatus isLoading={ovLoading} isError={ovError} isEmpty={!g} label="트렌드 속도계">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="lg:col-span-1 rounded-2xl bg-indigo-600 text-white p-6 flex flex-col justify-between">
            <span className="text-sm font-medium text-indigo-100">트렌드 속도계</span>
            <div className="flex items-end gap-1 mt-2">
              <span className="text-5xl font-extrabold tracking-tight">{g?.speed_kmh ?? "—"}</span>
              <span className="text-lg mb-1">km/h</span>
            </div>
            <div className="mt-3 flex items-center justify-between text-sm">
              <span>주간 지수 {g?.weekly_index ?? "—"} / 100</span>
              {g?.day_delta_pct != null && (
                <span className={g.day_delta_pct < 0 ? "text-rose-200" : "text-emerald-200"}>
                  {g.day_delta_pct > 0 ? "+" : ""}
                  {g.day_delta_pct}%
                </span>
              )}
            </div>
          </div>
          <div className="lg:col-span-2 rounded-2xl border border-slate-200 dark:border-slate-700 p-6">
            <h3 className="text-sm font-semibold text-slate-500 dark:text-slate-400 mb-1">오늘의 모멘텀 리더</h3>
            {g?.top_mover ? (
              <p className="text-lg font-bold text-slate-800 dark:text-slate-100">
                {g.top_mover.sector_name}{" "}
                <span className="text-emerald-600">+{g.top_mover.momentum_pct}%</span>
              </p>
            ) : (
              <p className="text-sm text-slate-400">모멘텀 신호가 아직 없습니다.</p>
            )}
          </div>
        </div>
      </PanelStatus>

      {/* 2. 연간 모멘텀 + 관심 점유율 */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <section className="lg:col-span-2 rounded-2xl border border-slate-200 dark:border-slate-700 p-6">
          <h2 className="text-md font-bold text-slate-800 dark:text-slate-100 mb-4">연간 모멘텀 트렌드</h2>
          <PanelStatus
            isLoading={ovLoading}
            isError={ovError}
            isEmpty={(overview?.momentum_series.length ?? 0) === 0}
            label="모멘텀"
          >
            <MomentumChart points={overview?.momentum_series ?? []} />
          </PanelStatus>
        </section>
        <section className="rounded-2xl border border-slate-200 dark:border-slate-700 p-6">
          <h2 className="text-md font-bold text-slate-800 dark:text-slate-100 mb-4">관심 점유율</h2>
          <PanelStatus
            isLoading={ovLoading}
            isError={ovError}
            isEmpty={(overview?.share.length ?? 0) === 0}
            label="점유율"
          >
            <div className="flex flex-col gap-2">
              {(overview?.share ?? []).map((s) => (
                <div key={s.sector_slug}>
                  <div className="flex justify-between text-xs text-slate-600 dark:text-slate-300 mb-0.5">
                    <span>{s.sector_name}</span>
                    <span>{s.pct}%</span>
                  </div>
                  <div className="w-full bg-slate-200 dark:bg-slate-700 h-2 rounded-full overflow-hidden">
                    <div className="h-full bg-indigo-500" style={{ width: `${s.pct}%` }} />
                  </div>
                </div>
              ))}
            </div>
          </PanelStatus>
        </section>
      </div>

      {/* 3. 섹터 × 시간 히트맵 */}
      <section className="rounded-2xl border border-slate-200 dark:border-slate-700 p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-md font-bold text-slate-800 dark:text-slate-100">Top 섹터 히트맵</h2>
          <span className="text-xs text-slate-400">분야 × 시간</span>
        </div>
        <PanelStatus
          isLoading={ovLoading}
          isError={ovError}
          isEmpty={(overview?.heatmap.rows.length ?? 0) === 0}
          label="히트맵"
        >
          <Heatmap buckets={overview?.heatmap.buckets ?? []} rows={overview?.heatmap.rows ?? []} />
        </PanelStatus>
      </section>

      {/* 4. 분야별 트렌드 속도 현황 (섹터 카드) */}
      <div>
        <h2 className="text-lg font-bold text-slate-800 dark:text-slate-100">분야별 트렌드 속도 현황</h2>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">섹터별 실시간 트렌드 점수와 모멘텀입니다.</p>
      </div>
      <PanelStatus isLoading={isLoading} isError={isError} isEmpty={sectorCards.length === 0} label="섹터 트렌드">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {sectorCards.map((sector) => (
            <div
              key={sector.slug}
              className="p-4 border border-slate-100 rounded-xl bg-slate-50/50 dark:border-slate-700 dark:bg-slate-900/50"
            >
              <div className="flex justify-between items-center mb-2">
                <span className="font-semibold text-slate-700 dark:text-slate-200">{sector.title}</span>
                <span className="text-xs px-2 py-1 rounded-full bg-indigo-100 text-indigo-600 dark:bg-indigo-900/40 dark:text-indigo-300">
                  {sector.status}
                </span>
              </div>
              <div className="flex items-end justify-between mb-2">
                <span className="text-2xl font-bold text-slate-900 dark:text-slate-100">{sector.score}</span>
                {sector.momentum != null && (
                  <span
                    className={`text-xs font-semibold ${sector.momentum < 0 ? "text-rose-600" : "text-emerald-600"}`}
                  >
                    {sector.momentum > 0 ? "+" : ""}
                    {sector.momentum}%
                  </span>
                )}
              </div>
              <div className="w-full bg-slate-200 h-2 rounded-full overflow-hidden dark:bg-slate-700">
                <div
                  className="h-full bg-indigo-500"
                  style={{ width: `${sector.score}%`, ...(sector.accent ? { backgroundColor: sector.accent } : {}) }}
                />
              </div>
            </div>
          ))}
        </div>
      </PanelStatus>
    </div>
  );
}
```

- [ ] **Step 2: 타입 체크**

Run: `cd www.yeotaeho.kr && pnpm exec tsc --noEmit`
Expected: 오류 없음(종료코드 0).

- [ ] **Step 3: 풀렌더 검증**

백엔드(`uvicorn main:app --port 8000`) + 프론트(`pnpm --dir www.yeotaeho.kr dev`, :3000) 기동 후 preview 도구로 대시보드 Pulse 탭 확인.
Expected: 속도계(km/h·주간지수)·연간 모멘텀 차트·섹터×시간 히트맵·관심 점유율·섹터 카드가 라이브 렌더. 데이터 희소 시 빈/짧은 상태 메시지(에러 아님). 콘솔 에러 없음.

- [ ] **Step 4: 커밋**

```bash
git add www.yeotaeho.kr/src/components/features/dashboard/PulseTab.tsx
git commit -m "feat(web): PulseTab 속도계·모멘텀·히트맵·점유율 라이브 복원"
```

---

## Self-Review 결과

- **Spec coverage**: §2.1 overview(Task 1·2·3) · §2.2 history(Task 2·3) · §3 집계 정의(Task 1 순수함수+테스트) · §4 리포지토리/순수 분리(Task 1·2) · §5 프론트(Task 4·5) · §6 엣지(Task 1 테스트: 희소·단일날짜·전무) · §7 테스트(Task 1 스크립트, Task 3·5 풀렌더) · §8 비범위(복원 섹션에서 인과사슬·크로스오버·티커·키워드 제외). 누락 없음.
- **Placeholder scan**: 모든 코드 단계 실제 코드 포함. "TBD/적절히 처리" 없음.
- **Type consistency**: `assemble_overview(latest, monthly, weekly, daily_avgs)` 시그니처가 Task 1 정의 ↔ Task 2 호출 일치. 응답 키(`gauge`·`momentum_series`·`heatmap`·`share`)가 순수함수 ↔ 프론트 타입(`PulseOverview`) 일치. `fetchPulseOverview`/`usePulseOverview` 명칭 Task 4 정의 ↔ Task 5 사용 일치.
