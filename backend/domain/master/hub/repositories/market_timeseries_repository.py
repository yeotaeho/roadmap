"""`raw_market_timeseries` 영속화 — (ticker, trade_date) 멱등 upsert."""

from __future__ import annotations

from typing import Any

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.sql import func

from domain.auth.hub.repositories.base_repository import BaseRepository
from domain.master.models.bases.raw_market_timeseries import RawMarketTimeseries
from domain.master.models.transfer.market_timeseries_dto import MarketTimeseriesDto


class MarketTimeseriesRepository(BaseRepository):
    async def upsert_many(self, rows: list[MarketTimeseriesDto]) -> int:
        """(ticker, trade_date) 기준 INSERT … ON CONFLICT DO UPDATE.

        Returns:
            처리된 행 수(신규+갱신). 배치 내 동일 키는 마지막 값만 반영.
        """
        seen: dict[tuple[str, str], dict[str, Any]] = {}
        for dto in rows:
            key = (dto.ticker.strip(), dto.trade_date.isoformat())
            seen[key] = {
                "ticker": dto.ticker.strip()[:32],
                "trade_date": dto.trade_date,
                "source_type": dto.source_type[:50],
                "asset_name": dto.asset_name[:255],
                "theme": dto.theme[:100] if dto.theme else None,
                "currency": dto.currency[:10],
                "open_price": dto.open_price,
                "high_price": dto.high_price,
                "low_price": dto.low_price,
                "close_price": dto.close_price,
                "volume": dto.volume,
                "turnover_amount": dto.turnover_amount,
                "raw_metadata": dto.raw_metadata,
            }

        payload = list(seen.values())
        if not payload:
            return 0

        stmt = pg_insert(RawMarketTimeseries).values(payload)
        update_cols = {
            "source_type": stmt.excluded.source_type,
            "asset_name": stmt.excluded.asset_name,
            "theme": stmt.excluded.theme,
            "currency": stmt.excluded.currency,
            "open_price": stmt.excluded.open_price,
            "high_price": stmt.excluded.high_price,
            "low_price": stmt.excluded.low_price,
            "close_price": stmt.excluded.close_price,
            "volume": stmt.excluded.volume,
            "turnover_amount": stmt.excluded.turnover_amount,
            "raw_metadata": stmt.excluded.raw_metadata,
            "collected_at": func.now(),
        }
        stmt = stmt.on_conflict_do_update(
            constraint="uq_raw_market_timeseries_ticker_date",
            set_=update_cols,
        ).returning(RawMarketTimeseries.id)

        async def _execute() -> int:
            result = await self.session.execute(stmt)
            count = len(result.scalars().all())
            await self.session.commit()
            return count

        return await self._execute_with_retry(_execute)
