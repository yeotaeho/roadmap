"""Bronze 시장 시계열 파이프라인 — `raw_market_timeseries` 적재."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from domain.master.hub.repositories.market_timeseries_repository import (
    MarketTimeseriesRepository,
)
from domain.master.hub.services.collectors.economic.yahoo.yahoo_market_timeseries_collector import (
    YahooMarketTimeseriesCollector,
)
from domain.master.models.transfer.market_timeseries_dto import MarketTimeseriesDto

logger = logging.getLogger(__name__)


class BronzeMarketTimeseriesIngestService:
    def __init__(self, session: AsyncSession) -> None:
        self._repo = MarketTimeseriesRepository(session)

    async def ingest_yahoo_timeseries(
        self,
        *,
        period: str | None = None,
        incremental: bool = True,
    ) -> dict[str, Any]:
        """Yahoo Finance 16티커 일별 OHLCV → `raw_market_timeseries` upsert.

        Args:
            period: yfinance period. None이면 incremental=True→1mo, False→1y.
            incremental: False면 초기 backfill(기본 1y).
        """
        collector = YahooMarketTimeseriesCollector()
        rows: list[MarketTimeseriesDto] = []
        failed = 0
        try:
            rows, failed = await collector.collect(
                period=period,
                incremental=incremental,
            )
        except Exception:
            logger.exception("Yahoo market timeseries 수집 실패")

        upserted = await self._repo.upsert_many(rows)

        result: dict[str, Any] = {
            "source": "yahoo_market_timeseries",
            "fetched": len(rows),
            "upserted": upserted,
            "failed_tickers": failed,
            "period": period or ("1mo" if incremental else "1y"),
            "incremental": incremental,
        }
        logger.info("Bronze market timeseries ingest: %s", result)
        return result
