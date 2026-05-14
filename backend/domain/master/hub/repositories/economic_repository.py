"""`raw_economic_data` 영속화."""

from __future__ import annotations

from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from domain.auth.hub.repositories.base_repository import BaseRepository
from domain.master.models.bases.raw_economic_data import RawEconomicData
from domain.master.models.transfer.economic_collect_dto import EconomicCollectDto


class EconomicRepository(BaseRepository):
    async def delete_by_source_type(self, source_type: str) -> int:
        async def _execute() -> int:
            stmt = delete(RawEconomicData).where(RawEconomicData.source_type == source_type)
            result = await self.session.execute(stmt)
            await self.session.commit()
            return int(result.rowcount or 0)

        return await self._execute_with_retry(_execute)

    async def exists_by_source(self, *, source_type: str, source_url: str | None) -> bool:
        if not source_url:
            return False

        async def _execute() -> bool:
            q = (
                select(RawEconomicData.id)
                .where(RawEconomicData.source_type == source_type)
                .where(RawEconomicData.source_url == source_url)
                .limit(1)
            )
            result = await self.session.execute(q)
            return result.scalar_one_or_none() is not None

        return await self._execute_with_retry(_execute)

    async def insert_many_skip_duplicates(self, rows: list[EconomicCollectDto]) -> int:
        """URL 단위 유니크 제약 기준 ON CONFLICT DO NOTHING (배치 1회 커밋)."""

        seen_batch: set[str] = set()
        payload: list[dict[str, Any]] = []
        for dto in rows:
            url = (dto.source_url or "").strip() or None
            if not url or url in seen_batch:
                continue
            seen_batch.add(url)
            payload.append(
                {
                    "source_type": dto.source_type[:50],
                    "source_url": url,
                    "raw_title": dto.raw_title[:500],
                    "investor_name": (dto.investor_name[:255] if dto.investor_name else None),
                    "target_company_or_fund": (
                        dto.target_company_or_fund[:255] if dto.target_company_or_fund else None
                    ),
                    "investment_amount": dto.investment_amount,
                    "currency": dto.currency[:10],
                    "raw_metadata": dto.raw_metadata,
                    "published_at": dto.published_at,
                }
            )

        if not payload:
            return 0

        stmt = (
            pg_insert(RawEconomicData)
            .values(payload)
            .on_conflict_do_nothing(index_elements=["source_url"])
            .returning(RawEconomicData.id)
        )

        async def _execute() -> int:
            result = await self.session.execute(stmt)
            inserted = len(result.scalars().all())
            await self.session.commit()
            return inserted

        return await self._execute_with_retry(_execute)
