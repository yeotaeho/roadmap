"""담론(Discourse) 컬렉터 실행과 Bronze 적재를 조정한다."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from domain.master.hub.repositories.discourse_repository import DiscourseRepository
from domain.master.hub.services.collectors.discourse.gov_report.gov_report_collector import (
    GovReportCollector,
)
from domain.master.hub.services.collectors.discourse.news_rss.news_rss_collector import (
    NewsRssCollector,
)

logger = logging.getLogger(__name__)


class BronzeDiscourseIngestService:
    def __init__(self, session: AsyncSession) -> None:
        self._repo = DiscourseRepository(session)

    async def ingest_news_rss(self, *, max_items_per_feed: int = 50) -> dict[str, Any]:
        rows, stats = await NewsRssCollector().collect(
            max_items_per_feed=max_items_per_feed
        )
        inserted = await self._repo.insert_many_skip_duplicates(rows)
        result = {
            "source": "news_rss",
            "fetched": len(rows),
            "inserted": inserted,
            "not_inserted": len(rows) - inserted,
            "stats": stats,
        }
        logger.info("Bronze discourse 뉴스 RSS ingest: %s", result)
        return result

    async def ingest_gov_report(self, *, max_items: int = 50) -> dict[str, Any]:
        rows, stats = await GovReportCollector().collect(max_items=max_items)
        inserted = await self._repo.insert_many_skip_duplicates(rows)
        result = {
            "source": "gov_report",
            "fetched": len(rows),
            "inserted": inserted,
            "not_inserted": len(rows) - inserted,
            "stats": stats,
        }
        logger.info("Bronze discourse 정부 보도자료 ingest: %s", result)
        return result
