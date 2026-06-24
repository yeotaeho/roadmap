"""담론(Discourse) Bronze 데이터의 배치 적재를 담당한다."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from domain.auth.hub.repositories.base_repository import BaseRepository
from domain.master.models.bases.raw_discourse_data import RawDiscourseData
from domain.master.models.transfer.discourse_collect_dto import DiscourseCollectDto


class DiscourseRepository(BaseRepository):
    async def insert_many_skip_duplicates(self, rows: list[DiscourseCollectDto]) -> int:
        """source_url 유니크 기준 ON CONFLICT DO NOTHING (배치 1회 커밋)."""
        seen: set[str] = set()
        payload: list[dict[str, Any]] = []
        for dto in rows:
            url = (dto.source_url or "").strip()
            if not url or url in seen:
                continue
            seen.add(url)
            payload.append(
                {
                    "source_type": dto.source_type[:50],
                    "source_url": url,
                    "headline": dto.headline[:500],
                    "author_or_publisher": dto.author_or_publisher[:255]
                    if dto.author_or_publisher
                    else None,
                    "content_body": dto.content_body,
                    "raw_metadata": dto.raw_metadata,
                    "published_at": dto.published_at,
                }
            )
        if not payload:
            return 0

        def _build(chunk: list[dict[str, Any]]):
            return (
                pg_insert(RawDiscourseData)
                .values(chunk)
                .on_conflict_do_nothing(index_elements=["source_url"])
                .returning(RawDiscourseData.id)
            )

        return await self._execute_with_retry(
            lambda: self._commit_batched_returning(_build, payload)
        )

    async def count_by_source_type(self, source_type: str) -> int:
        stmt = select(func.count(RawDiscourseData.id)).where(
            RawDiscourseData.source_type == source_type
        )
        return int((await self.session.execute(stmt)).scalar_one() or 0)
