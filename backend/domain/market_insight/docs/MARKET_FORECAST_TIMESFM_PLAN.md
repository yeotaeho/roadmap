# 시장 전망 수직 (TimesFM 14일 예측) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `raw_market_timeseries` 티커 시계열을 TimesFM 2.5로 14일 예측해 섹터별 0~100 전망 점수·방향 배지를 산출하는 독립 '시장 전망' 수직을 추가한다.

**Architecture:** 무거운 모델(spoke/infra)과 순수 산출 로직(hub/services)을 분리한다. 티커별 close_price를 예측해 % 수익률로 바꾸고, 통화 중립 상대 turnover로 섹터 집계한 뒤 0~100으로 매핑한다. 스케줄러 배치가 Silver/Gold를 멱등 재생성하고 API는 Gold만 읽는다. Pulse 점수는 건드리지 않는다.

**Tech Stack:** Python 3.13 / torch313 · FastAPI · SQLAlchemy 2.0 async · Alembic · APScheduler · `timesfm[torch]==2.0.1`(TimesFM 2.5 200M) · numpy

설계 스펙: [MARKET_FORECAST_TIMESFM_DESIGN.md](./MARKET_FORECAST_TIMESFM_DESIGN.md)

## Global Constraints

- **Python 인터프리터** — 모든 테스트·스크립트는 `C:/anaconda3/envs/torch313/python.exe` 로 실행한다(torch·timesfm 설치 환경).
- **새 소스 파일 첫 줄** — 한 줄 한국어 주석으로 역할 명시(config 제외). CLAUDE.md §6.
- **한국어 문장 종결** — `.` `?` `!` 만. `:` 로 끝내지 않는다. CLAUDE.md §5.
- **Surgical edits** — 태스크가 요구하는 줄만 수정, 기존 스타일 유지. CLAUDE.md §3.
- **Semantic commits** — 각 태스크 끝에서 논리 단위로 커밋. CLAUDE.md §7.
- **마이그레이션 head** — 신규 마이그레이션 `down_revision = "d1a2b3c4e5f6"`(현재 단일 head). autogenerate 금지, 수동 작성.
- **티커→섹터 매핑** — `pulse_repository._MARKET_SOURCE_MAP` 재사용(광범위지수 SPY/QQQ/ARKK 제외).
- **서빙 형태** — 라우터는 Pydantic DTO 없이 `{"success": True, ...}` dict 반환(기존 insight 라우터 패턴). 리포지토리는 `list[dict]` 반환.
- **테스트 러너** — 기존 `scripts/*_test.py` 의 `check(name, cond)` 카운터 패턴 사용(pytest 아님).

---

## File Structure

**신규**
- `domain/market_insight/hub/services/forecast_pipeline.py` — 순수 산출(수익률→점수·배지·신뢰도, 섹터 집계, Gold 사영)
- `domain/market_insight/spokes/infra/timesfm_forecaster.py` — Forecaster Protocol + TimesFM 래퍼 + 순수 헬퍼 + FakeForecaster
- `domain/market_insight/hub/services/forecast_refine_service.py` — 오케스트레이션
- `domain/market_insight/hub/repositories/forecast_repository.py` — 티커 시계열 조회·Silver/Gold replace·서빙
- `domain/market_insight/models/bases/refined_market_forecast_silver.py` — Silver ORM
- `domain/market_insight/models/bases/market_forecast_log.py` — Gold ORM
- `alembic/versions/c8f1a2d3e4b5_add_market_forecast_tables.py` — 두 테이블 생성(수동)
- `scripts/market_forecast_test.py` — 순수 단위 테스트(fake forecaster)
- `scripts/market_forecast_refine.py` — 수동/스모크 배치 엔트리

**수정**
- `core/config/settings.py` — `FORECAST_*` 필드
- `api/v1/insight/insight_routor.py` — `GET /insight/forecast` + `POST /insight/forecast/refine`
- `core/scheduler.py` — `_job_market_forecast` + `_REFINE_PIPELINE` 등록
- `alembic/env.py` — 신규 ORM 2개 import 등록
- `requirements.txt` — `timesfm[torch]==2.0.1`

---

## Task 1: 순수 산출 파이프라인 (forecast_pipeline.py)

**Files:**
- Create: `backend/domain/market_insight/hub/services/forecast_pipeline.py`
- Test: `backend/scripts/market_forecast_test.py`

**Interfaces:**
- Produces:
  - `TickerForecast(ticker: str, predicted_return_pct: float, band_rel: float, rel_turnover: float)` (frozen dataclass)
  - `SectorForecastRow(sector_slug, reference_date, horizon_days, target_date, predicted_return_pct, forecast_score, direction_badge, confidence, ticker_count)`
  - `ForecastGoldRow(sector_slug, forecast_date, horizon_days, target_date, score, direction_badge, predicted_return_pct, confidence)`
  - `compute_forecast(forecasts, ticker_sector, reference_date, target_date, horizon_days=14, score_k=5.0, up_threshold=1.5, up_strong_threshold=5.0, band_norm=0.3) -> list[SectorForecastRow]`
  - `project_to_gold(rows) -> list[ForecastGoldRow]`
  - 배지 상수 `BADGE_STRONG_UP="강세 전망"`, `BADGE_UP="상승 전망"`, `BADGE_NEUTRAL="중립 전망"`, `BADGE_DOWN="하락 전망"`, `BADGE_STRONG_DOWN="약세 전망"`

- [ ] **Step 1: 실패하는 테스트 작성**

Create `backend/scripts/market_forecast_test.py`:

```python
# 시장 전망 산출 파이프라인 무DB·무모델 검증 테스트

from __future__ import annotations

import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from domain.market_insight.hub.services.forecast_pipeline import (  # noqa: E402
    BADGE_NEUTRAL,
    BADGE_STRONG_DOWN,
    BADGE_STRONG_UP,
    ForecastGoldRow,
    SectorForecastRow,
    TickerForecast,
    compute_forecast,
    project_to_gold,
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


REF = date(2026, 6, 30)
TGT = date(2026, 7, 20)
MAP = {"AAA": "ai-data", "BBB": "ai-data", "CCC": "semiconductor"}


def test_score_and_badge() -> None:
    # 단일 티커 +10% → score=50+5*10=100, 강세 전망
    rows = compute_forecast(
        [TickerForecast("AAA", 10.0, 0.0, 1.0)], MAP, REF, TGT
    )
    check("섹터 1개 생성", len(rows) == 1)
    r = rows[0]
    check("score=100", r.forecast_score == 100)
    check("배지=강세 전망", r.direction_badge == BADGE_STRONG_UP)
    check("confidence=1.0(밴드0)", r.confidence == 1.0)
    check("ticker_count=1", r.ticker_count == 1)


def test_negative_and_neutral() -> None:
    down = compute_forecast([TickerForecast("CCC", -12.0, 0.0, 1.0)], MAP, REF, TGT)
    check("하락 score 클램프 0", down[0].forecast_score == 0)
    check("약세 전망", down[0].direction_badge == BADGE_STRONG_DOWN)
    # +0.6% → 50 + 5*0.6 = 53.0 (round 모호성 회피: 0.5 는 banker's rounding 함정)
    flat = compute_forecast([TickerForecast("CCC", 0.6, 0.0, 1.0)], MAP, REF, TGT)
    check("소폭 중립 score=53", flat[0].forecast_score == 53)
    check("중립 전망", flat[0].direction_badge == BADGE_NEUTRAL)


def test_turnover_weighted_aggregate() -> None:
    # AAA +10% (가중 3) · BBB -10% (가중 1) → (10*3 + -10*1)/4 = 5.0 → score 75
    rows = compute_forecast(
        [TickerForecast("AAA", 10.0, 0.0, 3.0), TickerForecast("BBB", -10.0, 0.0, 1.0)],
        MAP, REF, TGT,
    )
    ai = [r for r in rows if r.sector_slug == "ai-data"][0]
    check("가중 집계 return=5.0", abs(ai.predicted_return_pct - 5.0) < 1e-9)
    check("가중 집계 score=75", ai.forecast_score == 75)
    check("ticker_count=2", ai.ticker_count == 2)


def test_currency_neutral() -> None:
    # 수익률(무단위) 혼합 — USD ETF(+8%) + KRW 주식(+8%) 동일 가중이면 8% 그대로
    rows = compute_forecast(
        [TickerForecast("AAA", 8.0, 0.0, 1.0), TickerForecast("BBB", 8.0, 0.0, 1.0)],
        MAP, REF, TGT,
    )
    ai = [r for r in rows if r.sector_slug == "ai-data"][0]
    check("통화 중립 집계 return=8.0", abs(ai.predicted_return_pct - 8.0) < 1e-9)


def test_confidence_band() -> None:
    # band_rel=0.15, band_norm 기본 0.3 → conf = 1 - 0.15/0.3 = 0.5
    rows = compute_forecast([TickerForecast("AAA", 2.0, 0.15, 1.0)], MAP, REF, TGT)
    check("confidence=0.5", rows[0].confidence == 0.5)


def test_empty_and_unmapped() -> None:
    check("빈 입력 → 행 0", compute_forecast([], MAP, REF, TGT) == [])
    # 매핑 안 되는 티커만 → 행 0(날조 금지)
    unmapped = compute_forecast([TickerForecast("ZZZ", 5.0, 0.0, 1.0)], MAP, REF, TGT)
    check("미매핑 티커 → 행 0", unmapped == [])
    # 가중 0 → 행 0
    zerow = compute_forecast([TickerForecast("AAA", 5.0, 0.0, 0.0)], MAP, REF, TGT)
    check("가중 0 → 행 0", zerow == [])


def test_project_to_gold() -> None:
    rows = compute_forecast([TickerForecast("AAA", 10.0, 0.0, 1.0)], MAP, REF, TGT)
    gold = project_to_gold(rows)
    check("Gold 1행", len(gold) == 1 and isinstance(gold[0], ForecastGoldRow))
    check("Gold forecast_date=ref", gold[0].forecast_date == REF)
    check("Gold score 매핑", gold[0].score == 100)


def main() -> None:
    test_score_and_badge()
    test_negative_and_neutral()
    test_turnover_weighted_aggregate()
    test_currency_neutral()
    test_confidence_band()
    test_empty_and_unmapped()
    test_project_to_gold()
    print(f"\n{PASS} PASS, {FAIL} FAIL")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `C:/anaconda3/envs/torch313/python.exe backend/scripts/market_forecast_test.py`
Expected: FAIL — `ModuleNotFoundError: forecast_pipeline` (또는 ImportError).

- [ ] **Step 3: 파이프라인 구현**

Create `backend/domain/market_insight/hub/services/forecast_pipeline.py`:

```python
# 시장 전망 산출 결정론적 파이프라인 — 티커 예측 수익률 → 섹터 집계 → 0~100 전망 점수

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

BADGE_STRONG_UP = "강세 전망"
BADGE_UP = "상승 전망"
BADGE_NEUTRAL = "중립 전망"
BADGE_DOWN = "하락 전망"
BADGE_STRONG_DOWN = "약세 전망"


@dataclass(frozen=True)
class TickerForecast:
    """티커 1개 예측 산출 — 래퍼가 만들어 파이프라인에 주입한다."""

    ticker: str
    predicted_return_pct: float
    band_rel: float
    rel_turnover: float


@dataclass(frozen=True)
class SectorForecastRow:
    """refined_market_forecast_silver 1행에 대응하는 산출 결과."""

    sector_slug: str
    reference_date: date
    horizon_days: int
    target_date: date
    predicted_return_pct: float
    forecast_score: int
    direction_badge: str
    confidence: float
    ticker_count: int


@dataclass(frozen=True)
class ForecastGoldRow:
    """market_forecast_log 1행 — Silver 단순 사영."""

    sector_slug: str
    forecast_date: date
    horizon_days: int
    target_date: date
    score: int
    direction_badge: str
    predicted_return_pct: float
    confidence: float


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def return_to_score(sector_return: float, score_k: float) -> int:
    """예측 수익률(%) → 0~100. 0%면 50점."""
    return int(_clamp(round(50 + score_k * sector_return), 0, 100))


def direction_badge(sector_return: float, up: float, up_strong: float) -> str:
    if sector_return >= up_strong:
        return BADGE_STRONG_UP
    if sector_return >= up:
        return BADGE_UP
    if sector_return > -up:
        return BADGE_NEUTRAL
    if sector_return > -up_strong:
        return BADGE_DOWN
    return BADGE_STRONG_DOWN


def band_to_confidence(band_rel: float, band_norm: float) -> float:
    """분위수 상대 밴드폭 → 0~1 신뢰도. 좁을수록 높다."""
    if band_norm <= 0:
        return 0.0
    return round(_clamp(1.0 - band_rel / band_norm, 0.0, 1.0), 2)


def compute_forecast(
    forecasts: list[TickerForecast],
    ticker_sector: dict[str, str],
    reference_date: date,
    target_date: date,
    horizon_days: int = 14,
    score_k: float = 5.0,
    up_threshold: float = 1.5,
    up_strong_threshold: float = 5.0,
    band_norm: float = 0.3,
) -> list[SectorForecastRow]:
    """티커 예측을 섹터로 turnover 가중 집계해 Silver 행을 산출한다. 결정론적.

    가중치(rel_turnover)는 통화 중립 상대유량이고, 수익률은 무단위라 USD·KRW 티커를
    안전하게 합칠 수 있다. 유효 가중이 없는 섹터는 행을 만들지 않는다(날조 금지).
    """
    by_sector: dict[str, list[TickerForecast]] = {}
    for fc in forecasts:
        slug = ticker_sector.get(fc.ticker)
        if slug is None:
            continue
        by_sector.setdefault(slug, []).append(fc)

    rows: list[SectorForecastRow] = []
    for slug, items in sorted(by_sector.items()):
        num = 0.0
        band_num = 0.0
        wsum = 0.0
        for fc in items:
            w = max(0.0, fc.rel_turnover)
            num += fc.predicted_return_pct * w
            band_num += fc.band_rel * w
            wsum += w
        if wsum <= 0:
            continue
        sector_return = num / wsum
        avg_band = band_num / wsum
        rows.append(
            SectorForecastRow(
                sector_slug=slug,
                reference_date=reference_date,
                horizon_days=horizon_days,
                target_date=target_date,
                predicted_return_pct=round(sector_return, 4),
                forecast_score=return_to_score(sector_return, score_k),
                direction_badge=direction_badge(sector_return, up_threshold, up_strong_threshold),
                confidence=band_to_confidence(avg_band, band_norm),
                ticker_count=len(items),
            )
        )
    return rows


def project_to_gold(rows: list[SectorForecastRow]) -> list[ForecastGoldRow]:
    """Silver → Gold(market_forecast_log) 단순 사영. Gold는 계산을 추가하지 않는다."""
    return [
        ForecastGoldRow(
            sector_slug=r.sector_slug,
            forecast_date=r.reference_date,
            horizon_days=r.horizon_days,
            target_date=r.target_date,
            score=r.forecast_score,
            direction_badge=r.direction_badge,
            predicted_return_pct=r.predicted_return_pct,
            confidence=r.confidence,
        )
        for r in rows
    ]
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `C:/anaconda3/envs/torch313/python.exe backend/scripts/market_forecast_test.py`
Expected: `20 PASS, 0 FAIL`

- [ ] **Step 5: 커밋**

```bash
git add backend/domain/market_insight/hub/services/forecast_pipeline.py backend/scripts/market_forecast_test.py
git commit -m "feat(forecast): 시장 전망 순수 산출 파이프라인 — 수익률→점수·배지·신뢰도·섹터 집계"
```

---

## Task 2: Forecaster Protocol + TimesFM 래퍼 순수 헬퍼 (timesfm_forecaster.py)

**Files:**
- Create: `backend/domain/market_insight/spokes/infra/timesfm_forecaster.py`
- Test: `backend/scripts/market_forecast_test.py` (테스트 추가)

**Interfaces:**
- Consumes: 없음(numpy만).
- Produces:
  - `Forecaster` (Protocol) — `forecast_returns(series_by_ticker: dict[str, list[float]], horizon: int) -> dict[str, tuple[float, float]]`
  - `point_to_return(last_close: float, point_path) -> float`
  - `quantile_to_band_rel(point_path, quantile_path, lo_idx: int, hi_idx: int) -> float`
  - `TimesfmForecaster` (실 모델 래퍼, lazy 싱글톤, `unload()`)
  - `FakeForecaster(mapping: dict[str, tuple[float, float]])` — 테스트용 결정론적 주입

- [ ] **Step 1: 실패하는 테스트 추가**

`backend/scripts/market_forecast_test.py` 의 import 블록 아래에 추가:

```python
import numpy as np  # noqa: E402

from domain.market_insight.spokes.infra.timesfm_forecaster import (  # noqa: E402
    FakeForecaster,
    point_to_return,
    quantile_to_band_rel,
)
```

그리고 테스트 함수 추가(`test_project_to_gold` 아래):

```python
def test_point_to_return() -> None:
    check("수익률 +10%", abs(point_to_return(100.0, [101, 105, 110]) - 10.0) < 1e-9)
    check("last_close 0 → 0", point_to_return(0.0, [1, 2, 3]) == 0.0)


def test_quantile_band_rel() -> None:
    # 마지막 스텝 point=100, q[lo]=90 q[hi]=110 → (110-90)/100 = 0.2
    point = [100.0, 100.0]
    quant = [[0.0] * 10, [0.0, 90.0, 0, 0, 0, 0, 0, 0, 0, 110.0]]
    check("band_rel=0.2", abs(quantile_to_band_rel(point, quant, 1, 9) - 0.2) < 1e-9)
    check("point 0 → band 0", quantile_to_band_rel([0.0], [[0.0] * 10], 1, 9) == 0.0)


def test_fake_forecaster() -> None:
    fake = FakeForecaster({"AAA": (10.0, 0.1), "BBB": (-5.0, 0.2)})
    out = fake.forecast_returns({"AAA": [1, 2], "BBB": [3, 4], "CCC": [5, 6]}, 14)
    check("fake 매핑된 2개만", set(out.keys()) == {"AAA", "BBB"})
    check("fake AAA 값", out["AAA"] == (10.0, 0.1))
```

`main()` 에 호출 추가:

```python
    test_point_to_return()
    test_quantile_band_rel()
    test_fake_forecaster()
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `C:/anaconda3/envs/torch313/python.exe backend/scripts/market_forecast_test.py`
Expected: FAIL — `ModuleNotFoundError: timesfm_forecaster`.

- [ ] **Step 3: 래퍼 구현**

Create `backend/domain/market_insight/spokes/infra/timesfm_forecaster.py`:

```python
# TimesFM 시장 시계열 예측 래퍼 — 티커 close_price 배치 예측 → (수익률%, 분위수 밴드폭)

from __future__ import annotations

import logging
from typing import Protocol

import numpy as np

logger = logging.getLogger(__name__)


class Forecaster(Protocol):
    """티커 시계열 → (예측 수익률%, 상대 밴드폭) 매핑. 테스트는 Fake 로 대체한다."""

    def forecast_returns(
        self, series_by_ticker: dict[str, list[float]], horizon: int
    ) -> dict[str, tuple[float, float]]:
        ...


def point_to_return(last_close: float, point_path) -> float:
    """예측 마지막 스텝 대비 % 수익률. last_close<=0 이면 0(가드)."""
    if last_close <= 0:
        return 0.0
    return (float(point_path[-1]) - last_close) / last_close * 100.0


def quantile_to_band_rel(point_path, quantile_path, lo_idx: int, hi_idx: int) -> float:
    """마지막 스텝 (q_hi − q_lo)/|point| 상대 밴드폭. point 0 이면 0(가드)."""
    last_point = abs(float(point_path[-1]))
    if last_point <= 0:
        return 0.0
    q = np.asarray(quantile_path)
    return max(0.0, (float(q[-1, hi_idx]) - float(q[-1, lo_idx])) / last_point)


class FakeForecaster:
    """결정론적 주입용 — 무모델 테스트·E2E 스모크에서 TimesfmForecaster 를 대체한다."""

    def __init__(self, mapping: dict[str, tuple[float, float]]) -> None:
        self._mapping = mapping

    def forecast_returns(
        self, series_by_ticker: dict[str, list[float]], horizon: int
    ) -> dict[str, tuple[float, float]]:
        return {t: self._mapping[t] for t in series_by_ticker if t in self._mapping}


class TimesfmForecaster:
    """TimesFM 2.5(torch) lazy 싱글톤 래퍼. 모든 티커를 단일 forecast 호출로 배치한다."""

    _DEFAULT_REPO = "google/timesfm-2.5-200m-pytorch"
    # 분위수 10열 중 내부 밴드 인덱스(0.1·0.9 근사). Step 4 에서 실제 배열로 확인·조정.
    _Q_LO_IDX = 1
    _Q_HI_IDX = 9

    def __init__(
        self,
        repo_id: str | None = None,
        max_context: int = 512,
        min_history: int = 64,
    ) -> None:
        self._repo_id = repo_id or self._DEFAULT_REPO
        self._max_context = max_context
        self._min_history = min_history
        self._model = None

    def _ensure(self, horizon: int) -> None:
        if self._model is not None:
            return
        import timesfm

        model = timesfm.TimesFM_2p5_200M_torch.from_pretrained(self._repo_id)
        model.compile(
            timesfm.ForecastConfig(
                max_context=self._max_context,
                max_horizon=max(64, horizon),
                normalize_inputs=True,
                use_continuous_quantile_head=True,
                fix_quantile_crossing=True,
            )
        )
        self._model = model
        logger.info("[forecast] TimesFM loaded repo=%s", self._repo_id)

    def forecast_returns(
        self, series_by_ticker: dict[str, list[float]], horizon: int
    ) -> dict[str, tuple[float, float]]:
        usable = {
            t: s for t, s in series_by_ticker.items() if len(s) >= self._min_history
        }
        if not usable:
            return {}
        self._ensure(horizon)
        tickers = list(usable.keys())
        inputs = [np.asarray(usable[t], dtype=np.float32) for t in tickers]
        point, quantile = self._model.forecast(horizon=horizon, inputs=inputs)
        point = np.asarray(point)
        quantile = np.asarray(quantile)
        out: dict[str, tuple[float, float]] = {}
        for i, t in enumerate(tickers):
            ret = point_to_return(float(usable[t][-1]), point[i])
            band = quantile_to_band_rel(point[i], quantile[i], self._Q_LO_IDX, self._Q_HI_IDX)
            if np.isfinite(ret) and np.isfinite(band):
                out[t] = (ret, band)
        return out

    def unload(self) -> None:
        """배치 종료 후 모델 해제 — API 프로세스 영구 상주 회피."""
        self._model = None
```

- [ ] **Step 4: 테스트 통과 + 분위수 인덱스 확인**

Run: `C:/anaconda3/envs/torch313/python.exe backend/scripts/market_forecast_test.py`
Expected: `26 PASS, 0 FAIL`

분위수 인덱스 실측(1회): 아래를 실행해 `quantile` 마지막 차원 10열의 분위수 레벨을 확인하고, `_Q_LO_IDX`/`_Q_HI_IDX` 가 0.1·0.9(또는 가장 넓은 내부 밴드)에 대응하는지 점검한다. 다르면 두 상수만 수정한다.

```bash
C:/anaconda3/envs/torch313/python.exe -c "import numpy as np, timesfm; m=timesfm.TimesFM_2p5_200M_torch.from_pretrained('google/timesfm-2.5-200m-pytorch'); m.compile(timesfm.ForecastConfig(max_context=128,max_horizon=16,use_continuous_quantile_head=True,fix_quantile_crossing=True)); p,q=m.forecast(horizon=4,inputs=[np.arange(100,dtype=np.float32)]); print('quantile shape', np.asarray(q).shape); print('last-step 10열', np.round(np.asarray(q)[0,-1],2))"
```

Expected: `quantile shape (1, 4, 10)` 출력 + 10열이 단조 증가(오름차순 분위수). 오름차순이면 인덱스 1·9가 내부 밴드로 유효.

- [ ] **Step 5: 커밋**

```bash
git add backend/domain/market_insight/spokes/infra/timesfm_forecaster.py backend/scripts/market_forecast_test.py
git commit -m "feat(forecast): TimesFM 래퍼 + Forecaster Protocol + 순수 헬퍼(수익률·밴드폭)"
```

---

## Task 3: ORM 모델 (Silver + Gold) + env.py 등록

**Files:**
- Create: `backend/domain/market_insight/models/bases/refined_market_forecast_silver.py`
- Create: `backend/domain/market_insight/models/bases/market_forecast_log.py`
- Modify: `backend/alembic/env.py:80` (import 추가)
- Test: `backend/scripts/market_forecast_test.py` (메타데이터 점검 추가)

**Interfaces:**
- Produces: `RefinedMarketForecastSilver` (table `refined_market_forecast_silver`), `MarketForecastLog` (table `market_forecast_log`)

- [ ] **Step 1: Silver ORM 작성**

Create `backend/domain/market_insight/models/bases/refined_market_forecast_silver.py`:

```python
# Silver — 섹터×기준일 시장 전망(TimesFM 예측) 시계열을 저장하는 ORM 모델

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from core.database import Base


class RefinedMarketForecastSilver(Base):
    __tablename__ = "refined_market_forecast_silver"
    __table_args__ = (
        CheckConstraint(
            "forecast_score BETWEEN 0 AND 100", name="ck_market_forecast_silver_score"
        ),
        Index(
            "ix_market_forecast_silver_sector_date",
            "sector_slug",
            text("reference_date DESC"),
        ),
        Index(
            "uq_market_forecast_silver_natural",
            "sector_slug",
            "reference_date",
            "horizon_days",
            unique=True,
        ),
        {"comment": "Silver — 섹터×기준일 시장 전망 시계열 (Gold market_forecast_log 입력, 멱등)"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    sector_slug: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("sectors.slug", name="fk_market_forecast_silver_sector"),
        nullable=False,
    )
    reference_date: Mapped[date] = mapped_column(Date, nullable=False, comment="예측 기준일(최신 거래일)")
    horizon_days: Mapped[int] = mapped_column(Integer, nullable=False, comment="예측 스텝 수(거래일)")
    target_date: Mapped[date] = mapped_column(Date, nullable=False, comment="정보용 라벨(영업일 근사)")
    predicted_return_pct: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 4), nullable=True, comment="섹터 예측 수익률(%)"
    )
    forecast_score: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="0~100 전망 점수"
    )
    direction_badge: Mapped[str | None] = mapped_column(String(20), nullable=True)
    confidence: Mapped[Decimal | None] = mapped_column(
        Numeric(3, 2), nullable=True, comment="0~1 신뢰도(분위수 밴드 기반)"
    )
    ticker_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
```

- [ ] **Step 2: Gold ORM 작성**

Create `backend/domain/market_insight/models/bases/market_forecast_log.py`:

```python
# Gold — 시장 전망 탭 섹터별 기준일 예측 점수를 저장하는 ORM 모델

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from core.database import Base


class MarketForecastLog(Base):
    __tablename__ = "market_forecast_log"
    __table_args__ = (
        CheckConstraint("score BETWEEN 0 AND 100", name="ck_market_forecast_log_score"),
        Index("idx_market_forecast_date_sector", "forecast_date", "sector_slug"),
        Index(
            "uq_market_forecast_log_natural",
            "sector_slug",
            "forecast_date",
            "horizon_days",
            unique=True,
        ),
        {"comment": "Gold — 시장 전망 섹터별 기준일 예측 점수 (멱등 재생성)"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    sector_slug: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("sectors.slug", name="fk_market_forecast_log_sector"),
        nullable=False,
    )
    forecast_date: Mapped[date] = mapped_column(Date, nullable=False, comment="예측 기준일")
    horizon_days: Mapped[int] = mapped_column(Integer, nullable=False)
    target_date: Mapped[date] = mapped_column(Date, nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False, comment="0~100 전망 점수")
    direction_badge: Mapped[str] = mapped_column(String(20), nullable=False)
    predicted_return_pct: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(3, 2), nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
```

- [ ] **Step 3: env.py 에 모델 등록**

Modify `backend/alembic/env.py` — line 79(`from domain.master.models.bases.ncs_competency_master import NcsCompetencyMaster  # NCS 마스터`) 아래, line 81(`target_metadata = Base.metadata`) 위에 추가:

```python
from domain.market_insight.models.bases.refined_market_forecast_silver import (  # Silver
    RefinedMarketForecastSilver,
)
from domain.market_insight.models.bases.market_forecast_log import (  # Gold
    MarketForecastLog,
)
```

- [ ] **Step 4: 메타데이터 점검 테스트 추가**

`backend/scripts/market_forecast_test.py` import 블록에 추가:

```python
from domain.market_insight.models.bases.market_forecast_log import MarketForecastLog  # noqa: E402
from domain.market_insight.models.bases.refined_market_forecast_silver import (  # noqa: E402
    RefinedMarketForecastSilver,
)
```

테스트 함수 추가 + `main()` 등록:

```python
def test_orm_tables() -> None:
    check("Silver 테이블명", RefinedMarketForecastSilver.__tablename__ == "refined_market_forecast_silver")
    check("Gold 테이블명", MarketForecastLog.__tablename__ == "market_forecast_log")
    cols = set(RefinedMarketForecastSilver.__table__.columns.keys())
    check("Silver 필수 컬럼", {"sector_slug", "reference_date", "forecast_score", "confidence"} <= cols)
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `C:/anaconda3/envs/torch313/python.exe backend/scripts/market_forecast_test.py`
Expected: `29 PASS, 0 FAIL`

- [ ] **Step 6: 커밋**

```bash
git add backend/domain/market_insight/models/bases/refined_market_forecast_silver.py backend/domain/market_insight/models/bases/market_forecast_log.py backend/alembic/env.py backend/scripts/market_forecast_test.py
git commit -m "feat(forecast): Silver/Gold ORM 모델 + alembic env 등록"
```

---

## Task 4: 마이그레이션 (두 테이블 생성)

**Files:**
- Create: `backend/alembic/versions/c8f1a2d3e4b5_add_market_forecast_tables.py`

**Interfaces:**
- Consumes: Task 3 ORM 스키마
- Produces: 물리 테이블 `refined_market_forecast_silver`, `market_forecast_log`

- [ ] **Step 1: 마이그레이션 작성**

Create `backend/alembic/versions/c8f1a2d3e4b5_add_market_forecast_tables.py`:

```python
"""시장 전망 수직 — refined_market_forecast_silver·market_forecast_log 테이블 생성(TimesFM 예측)."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "c8f1a2d3e4b5"
down_revision: Union[str, None] = "d1a2b3c4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "refined_market_forecast_silver",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("sector_slug", sa.String(length=50), nullable=False),
        sa.Column("reference_date", sa.Date(), nullable=False),
        sa.Column("horizon_days", sa.Integer(), nullable=False),
        sa.Column("target_date", sa.Date(), nullable=False),
        sa.Column("predicted_return_pct", sa.Numeric(precision=8, scale=4), nullable=True),
        sa.Column("forecast_score", sa.Integer(), nullable=True),
        sa.Column("direction_badge", sa.String(length=20), nullable=True),
        sa.Column("confidence", sa.Numeric(precision=3, scale=2), nullable=True),
        sa.Column("ticker_count", sa.Integer(), nullable=True),
        sa.Column("model_name", sa.String(length=120), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.CheckConstraint("forecast_score BETWEEN 0 AND 100", name="ck_market_forecast_silver_score"),
        sa.ForeignKeyConstraint(["sector_slug"], ["sectors.slug"], name="fk_market_forecast_silver_sector"),
        sa.PrimaryKeyConstraint("id"),
        comment="Silver — 섹터×기준일 시장 전망 시계열 (Gold market_forecast_log 입력, 멱등)",
    )
    op.create_index(
        "ix_market_forecast_silver_sector_date",
        "refined_market_forecast_silver",
        ["sector_slug", sa.text("reference_date DESC")],
    )
    op.create_index(
        "uq_market_forecast_silver_natural",
        "refined_market_forecast_silver",
        ["sector_slug", "reference_date", "horizon_days"],
        unique=True,
    )

    op.create_table(
        "market_forecast_log",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("sector_slug", sa.String(length=50), nullable=False),
        sa.Column("forecast_date", sa.Date(), nullable=False),
        sa.Column("horizon_days", sa.Integer(), nullable=False),
        sa.Column("target_date", sa.Date(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("direction_badge", sa.String(length=20), nullable=False),
        sa.Column("predicted_return_pct", sa.Numeric(precision=8, scale=4), nullable=True),
        sa.Column("confidence", sa.Numeric(precision=3, scale=2), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.CheckConstraint("score BETWEEN 0 AND 100", name="ck_market_forecast_log_score"),
        sa.ForeignKeyConstraint(["sector_slug"], ["sectors.slug"], name="fk_market_forecast_log_sector"),
        sa.PrimaryKeyConstraint("id"),
        comment="Gold — 시장 전망 섹터별 기준일 예측 점수 (멱등 재생성)",
    )
    op.create_index(
        "idx_market_forecast_date_sector",
        "market_forecast_log",
        ["forecast_date", "sector_slug"],
    )
    op.create_index(
        "uq_market_forecast_log_natural",
        "market_forecast_log",
        ["sector_slug", "forecast_date", "horizon_days"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_table("market_forecast_log")
    op.drop_table("refined_market_forecast_silver")
```

- [ ] **Step 2: 마이그레이션 적용**

Run: `cd backend && C:/anaconda3/envs/torch313/python.exe -m alembic.config upgrade head` 가 안 되면 `python -c "from alembic.config import main; main(['upgrade','head'])"` 사용. 또는 프로젝트 표준대로 `alembic upgrade head`(backend 디렉터리에서).
Expected: `Running upgrade d1a2b3c4e5f6 -> c8f1a2d3e4b5` 로그.

- [ ] **Step 3: 테이블 존재 확인**

Run:
```bash
cd backend && C:/anaconda3/envs/torch313/python.exe -c "import asyncio; from sqlalchemy import text; from core.database import AsyncSessionLocal
async def m():
    async with AsyncSessionLocal() as s:
        for t in ('refined_market_forecast_silver','market_forecast_log'):
            r=(await s.execute(text('SELECT to_regclass(:t)'),{'t':t})).scalar()
            print(t, '존재' if r else '없음')
asyncio.run(m())"
```
Expected: 두 테이블 모두 `존재`.

- [ ] **Step 4: 커밋**

```bash
git add backend/alembic/versions/c8f1a2d3e4b5_add_market_forecast_tables.py
git commit -m "feat(forecast): 마이그레이션 — 시장 전망 Silver/Gold 테이블 생성"
```

---

## Task 5: 리포지토리 (forecast_repository.py)

**Files:**
- Create: `backend/domain/market_insight/hub/repositories/forecast_repository.py`

**Interfaces:**
- Consumes: `_MARKET_SOURCE_MAP`(pulse_repository), `TickerForecast`/`SectorForecastRow`/`ForecastGoldRow`(forecast_pipeline)
- Produces:
  - `fetch_ticker_series() -> tuple[dict[str,list[float]], dict[str,str], dict[str,float], date | None]` (series, ticker_sector, ticker_weight, reference_date)
  - `replace_silver(rows: list[SectorForecastRow], model_name: str) -> int`
  - `replace_gold(rows: list[ForecastGoldRow]) -> int`
  - `fetch_latest_forecast() -> list[dict]`

- [ ] **Step 1: 리포지토리 작성**

Create `backend/domain/market_insight/hub/repositories/forecast_repository.py`:

```python
# 시장 전망 리포지토리 — 티커 시계열 조회, Silver/Gold 멱등 replace, Gold 서빙

from __future__ import annotations

from datetime import date

from sqlalchemy import text

from domain.auth.hub.repositories.base_repository import BaseRepository
from domain.market_insight.hub.repositories.pulse_repository import _MARKET_SOURCE_MAP
from domain.market_insight.hub.services.forecast_pipeline import (
    ForecastGoldRow,
    SectorForecastRow,
)

# 티커별 close_price 시계열(거래일 오름차순) + 티커 기간 평균 거래대금(상대 가중 산출용).
_TICKER_SERIES_SQL = text(
    """
    SELECT source_type, ticker, trade_date, close_price,
           COALESCE(turnover_amount, volume * close_price) AS tv
    FROM raw_market_timeseries
    ORDER BY ticker, trade_date
    """
)

_INSERT_SILVER = text(
    """
    INSERT INTO refined_market_forecast_silver
        (sector_slug, reference_date, horizon_days, target_date, predicted_return_pct,
         forecast_score, direction_badge, confidence, ticker_count, model_name)
    VALUES
        (:sector_slug, :reference_date, :horizon_days, :target_date, :predicted_return_pct,
         :forecast_score, :direction_badge, :confidence, :ticker_count, :model_name)
    """
)

_INSERT_GOLD = text(
    """
    INSERT INTO market_forecast_log
        (sector_slug, forecast_date, horizon_days, target_date, score, direction_badge,
         predicted_return_pct, confidence)
    VALUES
        (:sector_slug, :forecast_date, :horizon_days, :target_date, :score, :direction_badge,
         :predicted_return_pct, :confidence)
    """
)

# 섹터별 최신 기준일 1행 + 섹터 메타. 시장 전망 탭 서빙 쿼리.
_LATEST_FORECAST_SQL = text(
    """
    SELECT DISTINCT ON (g.sector_slug)
        g.sector_slug, s.name_ko, s.accent_color,
        g.forecast_date, g.target_date, g.score, g.direction_badge,
        g.predicted_return_pct, g.confidence
    FROM market_forecast_log g
    JOIN sectors s ON s.slug = g.sector_slug
    ORDER BY g.sector_slug, g.forecast_date DESC
    """
)


class ForecastRepository(BaseRepository):
    async def fetch_ticker_series(
        self,
    ) -> tuple[dict[str, list[float]], dict[str, str], dict[str, float], date | None]:
        """티커별 종가 시계열·섹터 매핑·상대 turnover 가중·최신 기준일을 모은다.

        섹터 매핑은 _MARKET_SOURCE_MAP(광범위지수 제외)을 따른다. 상대 가중은
        티커 최신 거래대금 ÷ 그 티커 기간 평균(통화 중립). reference_date 는 전 티커 최신 거래일.
        """
        series: dict[str, list[float]] = {}
        ticker_sector: dict[str, str] = {}
        tv_sum: dict[str, float] = {}
        tv_cnt: dict[str, int] = {}
        last_tv: dict[str, float] = {}
        ref_date: date | None = None

        for r in (await self.session.execute(_TICKER_SERIES_SQL)).all():
            slug = _MARKET_SOURCE_MAP.get(r.source_type)
            if slug is None:
                continue
            t = r.ticker
            series.setdefault(t, []).append(float(r.close_price))
            ticker_sector[t] = slug
            tv = float(r.tv) if r.tv is not None else 0.0
            tv_sum[t] = tv_sum.get(t, 0.0) + tv
            tv_cnt[t] = tv_cnt.get(t, 0) + 1
            last_tv[t] = tv  # 오름차순이라 마지막이 최신
            if ref_date is None or r.trade_date > ref_date:
                ref_date = r.trade_date

        weight: dict[str, float] = {}
        for t in series:
            avg = tv_sum[t] / tv_cnt[t] if tv_cnt.get(t) else 0.0
            weight[t] = (last_tv[t] / avg) if avg > 0 else 0.0
        return series, ticker_sector, weight, ref_date

    async def replace_silver(self, rows: list[SectorForecastRow], model_name: str) -> int:
        """해당 기준일·horizon 의 Silver 를 통째로 재기록한다(멱등)."""
        if not rows:
            return 0
        ref = rows[0].reference_date
        hor = rows[0].horizon_days
        await self.session.execute(
            text(
                "DELETE FROM refined_market_forecast_silver "
                "WHERE reference_date = :ref AND horizon_days = :hor"
            ),
            {"ref": ref, "hor": hor},
        )
        payload = [
            {
                "sector_slug": r.sector_slug,
                "reference_date": r.reference_date,
                "horizon_days": r.horizon_days,
                "target_date": r.target_date,
                "predicted_return_pct": r.predicted_return_pct,
                "forecast_score": r.forecast_score,
                "direction_badge": r.direction_badge,
                "confidence": r.confidence,
                "ticker_count": r.ticker_count,
                "model_name": model_name,
            }
            for r in rows
        ]
        await self.session.execute(_INSERT_SILVER, payload)
        return len(payload)

    async def replace_gold(self, rows: list[ForecastGoldRow]) -> int:
        """해당 기준일·horizon 의 Gold 를 통째로 재생성한다(멱등)."""
        if not rows:
            return 0
        ref = rows[0].forecast_date
        hor = rows[0].horizon_days
        await self.session.execute(
            text(
                "DELETE FROM market_forecast_log "
                "WHERE forecast_date = :ref AND horizon_days = :hor"
            ),
            {"ref": ref, "hor": hor},
        )
        payload = [
            {
                "sector_slug": r.sector_slug,
                "forecast_date": r.forecast_date,
                "horizon_days": r.horizon_days,
                "target_date": r.target_date,
                "score": r.score,
                "direction_badge": r.direction_badge,
                "predicted_return_pct": r.predicted_return_pct,
                "confidence": r.confidence,
            }
            for r in rows
        ]
        await self.session.execute(_INSERT_GOLD, payload)
        return len(payload)

    async def fetch_latest_forecast(self) -> list[dict]:
        """섹터별 최신 전망 1행씩 (점수 내림차순)."""
        rows = (await self.session.execute(_LATEST_FORECAST_SQL)).all()
        result = [
            {
                "sector_slug": r.sector_slug,
                "sector_name": r.name_ko,
                "accent_color": r.accent_color,
                "forecast_date": r.forecast_date.isoformat()
                if isinstance(r.forecast_date, date)
                else r.forecast_date,
                "target_date": r.target_date.isoformat()
                if isinstance(r.target_date, date)
                else r.target_date,
                "score": r.score,
                "direction_badge": r.direction_badge,
                "predicted_return_pct": float(r.predicted_return_pct)
                if r.predicted_return_pct is not None
                else None,
                "confidence": float(r.confidence) if r.confidence is not None else None,
            }
            for r in rows
        ]
        result.sort(key=lambda x: x["score"], reverse=True)
        return result
```

- [ ] **Step 2: DB 스모크 — 티커 시계열 조회 확인**

Run:
```bash
cd backend && C:/anaconda3/envs/torch313/python.exe -c "import asyncio; from core.database import AsyncSessionLocal; from domain.market_insight.hub.repositories.forecast_repository import ForecastRepository
async def m():
    async with AsyncSessionLocal() as s:
        series, secmap, weight, ref = await ForecastRepository(s).fetch_ticker_series()
        print('티커수', len(series), 'ref_date', ref)
        ex = next(iter(series)) if series else None
        if ex: print('예시', ex, '→', secmap[ex], 'len', len(series[ex]), 'w', round(weight[ex],3))
asyncio.run(m())"
```
Expected: 티커수 ≥ 1, ref_date 출력, 예시 티커가 섹터로 매핑되고 시계열 길이가 수십~수백.

- [ ] **Step 3: 커밋**

```bash
git add backend/domain/market_insight/hub/repositories/forecast_repository.py
git commit -m "feat(forecast): 리포지토리 — 티커 시계열 조회·Silver/Gold replace·서빙"
```

---

## Task 6: 설정값 + 오케스트레이션 서비스 (forecast_refine_service.py)

**Files:**
- Modify: `backend/core/config/settings.py:184` (FORECAST_* 추가)
- Create: `backend/domain/market_insight/hub/services/forecast_refine_service.py`

**Interfaces:**
- Consumes: `ForecastRepository`, `Forecaster`/`TimesfmForecaster`(timesfm_forecaster), `compute_forecast`/`project_to_gold`(forecast_pipeline), `get_settings`
- Produces: `MarketForecastRefineService(session, forecaster=None).refine_and_serve(horizon_days=None) -> dict`

- [ ] **Step 1: 설정 필드 추가**

Modify `backend/core/config/settings.py` — line 184 (`pulse_center_text_sentiment` Field 닫는 `)`) 다음, line 186 (`# Open DART`) 앞에 추가:

```python

    # 시장 전망(TimesFM 14일 예측) 튜닝 — 실사용 후 .env 로 재조정.
    forecast_horizon_days: int = Field(default=14, validation_alias="FORECAST_HORIZON_DAYS")
    forecast_score_k: float = Field(default=5.0, validation_alias="FORECAST_SCORE_K")
    forecast_up_threshold: float = Field(default=1.5, validation_alias="FORECAST_UP_THRESHOLD")
    forecast_up_strong_threshold: float = Field(
        default=5.0, validation_alias="FORECAST_UP_STRONG_THRESHOLD"
    )
    forecast_min_history: int = Field(default=64, validation_alias="FORECAST_MIN_HISTORY")
    forecast_band_norm: float = Field(default=0.3, validation_alias="FORECAST_BAND_NORM")
    forecast_model_repo: str = Field(
        default="google/timesfm-2.5-200m-pytorch", validation_alias="FORECAST_MODEL_REPO"
    )
```

- [ ] **Step 2: 서비스 작성**

Create `backend/domain/market_insight/hub/services/forecast_refine_service.py`:

```python
# 시장 전망 정제·서빙 — 티커 시계열 → TimesFM 예측 → Silver → Gold(멱등 재생성)

from __future__ import annotations

from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from core.config.settings import get_settings
from domain.market_insight.hub.repositories.forecast_repository import ForecastRepository
from domain.market_insight.hub.services.forecast_pipeline import (
    TickerForecast,
    compute_forecast,
    project_to_gold,
)
from domain.market_insight.spokes.infra.timesfm_forecaster import (
    Forecaster,
    TimesfmForecaster,
)

_MODEL_NAME = "timesfm-2.5-200m"


class MarketForecastRefineService:
    def __init__(self, session: AsyncSession, forecaster: Forecaster | None = None):
        self.session = session
        self.repo = ForecastRepository(session)
        self._forecaster = forecaster  # None → lazy TimesfmForecaster(배치 종료 시 해제)

    async def refine_and_serve(self, horizon_days: int | None = None) -> dict:
        """티커 시계열 → 14일 예측 → 섹터 전망 점수 → Silver/Gold 한 줄 실행. 적재 건수 반환."""
        settings = get_settings()
        horizon = horizon_days or settings.forecast_horizon_days
        series, ticker_sector, weight, ref_date = await self.repo.fetch_ticker_series()
        if not series or ref_date is None:
            return {"tickers": 0, "predicted": 0, "silver": 0, "gold": 0}

        owns = self._forecaster is None
        forecaster = self._forecaster or TimesfmForecaster(
            repo_id=settings.forecast_model_repo,
            min_history=settings.forecast_min_history,
        )
        try:
            preds = forecaster.forecast_returns(series, horizon)
        finally:
            if owns:
                forecaster.unload()

        forecasts = [
            TickerForecast(t, ret, band, weight.get(t, 0.0))
            for t, (ret, band) in preds.items()
        ]
        # 거래일 horizon 의 영업일 근사(주말 보정): horizon × 7/5.
        target_date = ref_date + timedelta(days=horizon * 7 // 5)
        rows = compute_forecast(
            forecasts,
            ticker_sector,
            reference_date=ref_date,
            target_date=target_date,
            horizon_days=horizon,
            score_k=settings.forecast_score_k,
            up_threshold=settings.forecast_up_threshold,
            up_strong_threshold=settings.forecast_up_strong_threshold,
            band_norm=settings.forecast_band_norm,
        )
        silver_n = await self.repo.replace_silver(rows, model_name=_MODEL_NAME)
        gold = project_to_gold(rows)
        gold_n = await self.repo.replace_gold(gold)
        await self.session.commit()
        return {
            "tickers": len(series),
            "predicted": len(preds),
            "silver": silver_n,
            "gold": gold_n,
        }
```

- [ ] **Step 3: E2E 스모크 — FakeForecaster 로 refine → Gold 확인**

Run:
```bash
cd backend && C:/anaconda3/envs/torch313/python.exe -c "import asyncio; from core.database import AsyncSessionLocal; from domain.market_insight.hub.repositories.forecast_repository import ForecastRepository; from domain.market_insight.hub.services.forecast_refine_service import MarketForecastRefineService; from domain.market_insight.spokes.infra.timesfm_forecaster import FakeForecaster
async def m():
    async with AsyncSessionLocal() as s:
        series,_,_,_ = await ForecastRepository(s).fetch_ticker_series()
        fake = FakeForecaster({t:(3.0,0.1) for t in series})  # 전 티커 +3% 모의
        res = await MarketForecastRefineService(s, forecaster=fake).refine_and_serve()
        print('refine', res)
        latest = await ForecastRepository(s).fetch_latest_forecast()
        print('서빙 섹터수', len(latest))
        if latest: print('예시', latest[0]['sector_slug'], latest[0]['score'], latest[0]['direction_badge'])
asyncio.run(m())"
```
Expected: `refine {'tickers': N, 'predicted': N, 'silver': M, 'gold': M}` (M = 매핑된 섹터 수), 서빙 섹터수 = M, 예시 섹터 score=65(50+5*3), 배지='상승 전망'.

- [ ] **Step 4: 커밋**

```bash
git add backend/core/config/settings.py backend/domain/market_insight/hub/services/forecast_refine_service.py
git commit -m "feat(forecast): 오케스트레이션 서비스 + FORECAST_* 설정값"
```

---

## Task 7: 라우터 + 스케줄러 + requirements

**Files:**
- Modify: `backend/api/v1/insight/insight_routor.py` (import + 2 엔드포인트)
- Modify: `backend/core/scheduler.py` (잡 + 파이프라인 등록)
- Modify: `backend/requirements.txt` (timesfm 핀)

**Interfaces:**
- Consumes: `ForecastRepository`, `MarketForecastRefineService`
- Produces: `GET /api/insight/forecast`, `POST /api/insight/forecast/refine`, 스케줄러 `market_forecast` 스텝

- [ ] **Step 1: 라우터 import 추가**

Modify `backend/api/v1/insight/insight_routor.py` — line 13 (`from ...pulse_repository import PulseRepository`) 아래에 추가:

```python
from domain.market_insight.hub.repositories.forecast_repository import ForecastRepository
```

line 20 (`from ...pulse_refine_service import PulseRefineService`) 아래에 추가:

```python
from domain.market_insight.hub.services.forecast_refine_service import (
    MarketForecastRefineService,
)
```

- [ ] **Step 2: 엔드포인트 추가**

Modify `backend/api/v1/insight/insight_routor.py` — `get_pulse_crossover` 함수 끝(line 109 `)` 다음, line 112 `@router.get("/keywords")` 앞)에 추가:

```python


@router.get("/forecast")
async def get_market_forecast(db: AsyncSession = Depends(get_db)):
    """시장 전망 탭 서빙 — 섹터별 최신 TimesFM 예측 점수(Gold market_forecast_log)."""
    try:
        forecasts = await ForecastRepository(db).fetch_latest_forecast()
        return {"success": True, "sectors": forecasts, "count": len(forecasts)}
    except Exception as e:
        logger.error(f"시장 전망 조회 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"시장 전망 조회 실패: {str(e)}")


@router.post("/forecast/refine", dependencies=[Depends(require_internal_token)])
async def refine_market_forecast(db: AsyncSession = Depends(get_db)):
    """시장 전망 정제·서빙 수동 트리거 — 티커 시계열 → TimesFM → Silver → Gold 재생성."""
    try:
        result = await MarketForecastRefineService(db).refine_and_serve()
        return {"success": True, **result}
    except Exception as e:
        logger.error(f"시장 전망 정제 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"시장 전망 정제 실패: {str(e)}")
```

- [ ] **Step 3: 스케줄러 잡 + 파이프라인 등록**

Modify `backend/core/scheduler.py` — `_job_pulse_refine` 함수(line 671~675) 다음에 잡 본문 추가:

```python


async def _job_market_forecast() -> dict[str, Any] | None:
    """티커 시계열 → TimesFM 14일 예측 → 시장 전망 Silver/Gold 재생성(멱등). timesfm 없으면 스킵."""
    try:
        import timesfm  # noqa: F401
    except ImportError:
        logger.warning("[scheduler] timesfm 미설치 — 시장 전망 스킵")
        return None
    from domain.market_insight.hub.services.forecast_refine_service import (
        MarketForecastRefineService,
    )

    async with AsyncSessionLocal() as session:
        return await MarketForecastRefineService(session).refine_and_serve()
```

`_REFINE_PIPELINE` 튜플(line 702~717) 의 `("pulse_refine", _job_pulse_refine),` 다음 줄에 추가:

```python
    ("market_forecast",   _job_market_forecast),
```

- [ ] **Step 4: requirements 핀 추가**

Modify `backend/requirements.txt` — line 76 (`tenacity>=8.2.0`) 다음에 추가:

```
# 시장 전망 — TimesFM 2.5(torch 백엔드, JAX 불필요). 모델 체크포인트는 huggingface 캐시.
timesfm[torch]==2.0.1
```

- [ ] **Step 5: 라우터 등록 회귀 확인**

Run:
```bash
cd backend && C:/anaconda3/envs/torch313/python.exe -c "from api.v1.insight.insight_routor import router; paths=[r.path for r in router.routes]; print('forecast' , '/insight/forecast' in paths, '| refine', '/insight/forecast/refine' in paths)"
```
Expected: `forecast True | refine True`

- [ ] **Step 6: 스케줄러 파이프라인 등록 확인**

Run:
```bash
cd backend && C:/anaconda3/envs/torch313/python.exe -c "from core.scheduler import _REFINE_PIPELINE; names=[n for n,_ in _REFINE_PIPELINE]; print('market_forecast 위치', names.index('market_forecast'), 'pulse_refine 위치', names.index('pulse_refine'))"
```
Expected: `market_forecast 위치` 가 `pulse_refine 위치` 보다 1 큼(직후).

- [ ] **Step 7: 커밋**

```bash
git add backend/api/v1/insight/insight_routor.py backend/core/scheduler.py backend/requirements.txt
git commit -m "feat(forecast): 라우터 GET/POST + 스케줄러 잡 + timesfm 의존성 핀"
```

---

## Task 8: 배치 스크립트 + 실모델 스모크

**Files:**
- Create: `backend/scripts/market_forecast_refine.py`

**Interfaces:**
- Consumes: `MarketForecastRefineService`(실 TimesfmForecaster)
- Produces: 수동/cron 실행 엔트리 (`--smoke` 옵션)

- [ ] **Step 1: 배치 스크립트 작성**

Create `backend/scripts/market_forecast_refine.py`:

```python
# 시장 전망 수동/스모크 배치 엔트리 — 실 TimesFM 으로 Silver/Gold 재생성

from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import AsyncSessionLocal  # noqa: E402
from domain.market_insight.hub.repositories.forecast_repository import (  # noqa: E402
    ForecastRepository,
)
from domain.market_insight.hub.services.forecast_refine_service import (  # noqa: E402
    MarketForecastRefineService,
)


async def main() -> None:
    async with AsyncSessionLocal() as session:
        result = await MarketForecastRefineService(session).refine_and_serve()
        print("[market_forecast] refine:", result)
        latest = await ForecastRepository(session).fetch_latest_forecast()
        print(f"[market_forecast] 서빙 섹터 {len(latest)}개")
        for row in latest[:12]:
            print(
                f"  {row['sector_slug']:<16} score={row['score']:>3} "
                f"{row['direction_badge']} ret={row['predicted_return_pct']} "
                f"conf={row['confidence']}"
            )


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: 실모델 스모크 실행(수동 게이트)**

Run: `cd backend && C:/anaconda3/envs/torch313/python.exe scripts/market_forecast_refine.py`
Expected: 최초 1회 모델 로드(~85s) 후 `refine: {'tickers': N, 'predicted': N, 'silver': M, 'gold': M}` + 섹터별 점수·배지·수익률·신뢰도 출력. 점수는 0~100, 배지는 5종 중 하나, 신뢰도 0~1.

- [ ] **Step 3: 라이브 서빙 확인(백엔드 가동 중일 때)**

Run: `C:/anaconda3/envs/torch313/python.exe -c "import urllib.request, json; print(json.load(urllib.request.urlopen('http://localhost:8000/api/insight/forecast'))['count'])"`
Expected: 0 이상(섹터 수). 백엔드 미가동 시 이 스텝은 건너뛴다.

- [ ] **Step 4: 커밋**

```bash
git add backend/scripts/market_forecast_refine.py
git commit -m "feat(forecast): 수동/스모크 배치 엔트리 — 실 TimesFM Silver/Gold 재생성"
```

---

## Self-Review (작성자 점검 결과)

**1. 스펙 커버리지** — 스펙 §4~13 전부 태스크에 매핑됨.
- §4 아키텍처(spoke/hub 분리) → Task 1·2 · §5 데이터 흐름 → Task 5·6 · §6 스키마 → Task 3·4 · §7 산출 수식 → Task 1 · §8 모델 래퍼 → Task 2·8 · §9 컴포넌트 → 전 태스크 · §10 운영/스케줄러 → Task 7 · §11 에러 처리(빈/미매핑/가중0/NaN 가드) → Task 1 Step1 test_empty_and_unmapped + Task 2 헬퍼 가드 · §12 설정 → Task 6 · §13 테스트 → Task 1·2 순수 + 5·6·8 스모크.

**2. Placeholder 스캔** — 없음. 모든 코드 스텝은 완전한 코드. 분위수 인덱스만 Task 2 Step 4 에서 실측 확인(기본값 1·9 제공, 다르면 두 상수만 조정 — 실행 가능한 검증 절차이지 placeholder 아님).

**3. 타입 일관성** — `forecast_returns` 반환 `dict[str, tuple[float,float]]` 가 Task 2(정의)·5(미사용)·6(소비) 일치. `TickerForecast`/`SectorForecastRow`/`ForecastGoldRow` 필드명이 Task 1 정의와 Task 5·6 사용처 일치. `compute_forecast`/`project_to_gold` 시그니처가 Task 1 정의와 Task 6 호출 일치. 배지 상수 5종이 Task 1 정의와 Task 1 테스트 일치.
