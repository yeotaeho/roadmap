"""혁신 Bronze 데이터의 배치 적재와 워터마크 조회를 담당한다."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from domain.auth.hub.repositories.base_repository import BaseRepository
from domain.master.models.bases.raw_innovation_data import RawInnovationData
from domain.master.models.transfer.innovation_collect_dto import InnovationCollectDto


class InnovationRepository(BaseRepository):
    async def insert_many_skip_duplicates(self, rows: list[InnovationCollectDto]) -> int:
        seen: set[str] = set()
        payload: list[dict[str, Any]] = []
        for dto in rows:
            url = (dto.source_url or "").strip()
            if not url or url in seen:
                continue
            seen.add(url)
            payload.append(
                {
                    "source_type": dto.source_type,
                    "source_url": url,
                    "title": dto.title,
                    "author_or_assignee": dto.author_or_assignee,
                    "abstract_text": dto.abstract_text,
                    "raw_metadata": dto.raw_metadata,
                    "published_at": dto.published_at,
                }
            )
        if not payload:
            return 0

        def _build(chunk: list[dict[str, Any]]):
            return (
                pg_insert(RawInnovationData)
                .values(chunk)
                .on_conflict_do_nothing(index_elements=["source_url"])
                .returning(RawInnovationData.id)
            )

        return await self._execute_with_retry(
            lambda: self._commit_batched_returning(_build, payload)
        )

    async def latest_by_source_type(self, source_type: str) -> RawInnovationData | None:
        # published_at은 논문 발행일로 수집 배치 시점과 다를 수 있으므로 collected_at 기준 정렬
        stmt = (
            select(RawInnovationData)
            .where(RawInnovationData.source_type == source_type)
            .order_by(RawInnovationData.collected_at.desc())
            .limit(1)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

