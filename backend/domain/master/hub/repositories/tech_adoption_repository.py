# raw_tech_adoption_data DB 접근 레이어

from __future__ import annotations

import logging
from typing import Sequence

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from domain.master.models.bases.raw_tech_adoption_data import RawTechAdoptionData
from domain.master.models.transfer.tech_adoption_collect_dto import TechAdoptionCollectDto

logger = logging.getLogger(__name__)


class TechAdoptionRepository:
    """raw_tech_adoption_data CRUD + upsert."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_many(self, dtos: Sequence[TechAdoptionCollectDto]) -> int:
        """UPSERT — (ecosystem, package_name, week_start_date) 충돌 시 weekly_downloads·raw_metadata 갱신."""
        if not dtos:
            return 0
        rows = [
            {
                "ecosystem": dto.ecosystem,
                "package_name": dto.package_name,
                "sector": dto.sector,
                "weekly_downloads": dto.weekly_downloads,
                "week_start_date": dto.week_start_date,
                "raw_metadata": dto.raw_metadata,
                "collected_at": dto.collected_at,
            }
            for dto in dtos
        ]
        stmt = insert(RawTechAdoptionData).values(rows)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_raw_tech_adoption_ecosystem_pkg_week",
            set_={
                "weekly_downloads": stmt.excluded.weekly_downloads,
                "raw_metadata": stmt.excluded.raw_metadata,
                "collected_at": stmt.excluded.collected_at,
            },
        )
        result = await self._session.execute(stmt)
        await self._session.commit()
        return result.rowcount or len(rows)

    async def count_by_ecosystem(self, ecosystem: str) -> int:
        result = await self._session.execute(
            select(RawTechAdoptionData).where(RawTechAdoptionData.ecosystem == ecosystem)
        )
        return len(result.scalars().all())
