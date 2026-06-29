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
