"""사람·역량 Bronze 데이터의 배치 적재와 워터마크 조회를 담당한다."""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from domain.auth.hub.repositories.base_repository import BaseRepository
from domain.master.models.bases.raw_people_data import RawPeopleData
from domain.master.models.transfer.people_collect_dto import PeopleCollectDto


class PeopleRepository(BaseRepository):
    async def insert_many_skip_duplicates(self, rows: list[PeopleCollectDto]) -> int:
        seen: set[tuple[str, str, date | None]] = set()
        payload: list[dict[str, Any]] = []
        for dto in rows:
            key = (dto.source_type, dto.keyword_or_job, dto.reference_date)
            if key in seen:
                continue
            seen.add(key)
            payload.append(
                {
                    "source_type": dto.source_type,
                    "source_url": dto.source_url,
                    "keyword_or_job": dto.keyword_or_job,
                    "search_volume_or_count": dto.search_volume_or_count,
                    "raw_metadata": dto.raw_metadata,
                    "reference_date": dto.reference_date,
                }
            )
        if not payload:
            return 0

        def _build(chunk: list[dict[str, Any]]):
            return (
                pg_insert(RawPeopleData)
                .values(chunk)
                .on_conflict_do_nothing(
                    index_elements=["source_type", "keyword_or_job", "reference_date"]
                )
                .returning(RawPeopleData.id)
            )

        return await self._execute_with_retry(
            lambda: self._commit_batched_returning(_build, payload)
        )

    async def latest_reference_date(self, source_type: str) -> date | None:
        stmt = select(func.max(RawPeopleData.reference_date)).where(
            RawPeopleData.source_type == source_type
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

