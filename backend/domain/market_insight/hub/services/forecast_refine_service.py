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
