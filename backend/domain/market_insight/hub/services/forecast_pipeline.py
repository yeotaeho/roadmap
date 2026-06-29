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
