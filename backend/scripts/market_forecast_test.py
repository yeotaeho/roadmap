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
    TickerForecast,
    compute_forecast,
    project_to_gold,
)

import numpy as np  # noqa: E402

from domain.market_insight.spokes.infra.timesfm_forecaster import (  # noqa: E402
    FakeForecaster,
    point_to_return,
    quantile_to_band_rel,
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


def main() -> None:
    test_score_and_badge()
    test_negative_and_neutral()
    test_turnover_weighted_aggregate()
    test_currency_neutral()
    test_confidence_band()
    test_empty_and_unmapped()
    test_project_to_gold()
    test_point_to_return()
    test_quantile_band_rel()
    test_fake_forecaster()
    print(f"\n{PASS} PASS, {FAIL} FAIL")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
