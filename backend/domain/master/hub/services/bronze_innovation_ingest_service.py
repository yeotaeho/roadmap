"""혁신 컬렉터 실행과 Bronze 적재를 조정한다."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from domain.master.hub.repositories.innovation_repository import InnovationRepository
from domain.master.hub.services.collectors.innovation.arxiv.arxiv_papers_collector import (
    ArxivPapersCollector,
    ArxivWatermark,
)
from domain.master.hub.services.collectors.innovation.github.github_trending_collector import (
    GithubTrendingCollector,
    GithubWatermark,
)
from domain.master.hub.services.collectors.innovation.techblog.techblog_kr_collector import (
    TechBlogKrCollector,
)
from domain.master.hub.services.collectors.innovation.customs.customs_export_collector import (
    CustomsExportCollector,
)
from domain.master.hub.services.collectors.innovation.kistep.kistep_report_collector import (
    KistepReportCollector,
)
from domain.master.hub.services.collectors.innovation.kiat.tech_demand_collector import (
    KiatTechDemandCollector,
)

logger = logging.getLogger(__name__)


class BronzeInnovationIngestService:
    def __init__(self, session: AsyncSession, *, github_token: str | None = None) -> None:
        self._repo = InnovationRepository(session)
        self._github_token = github_token

    async def ingest_arxiv(
        self, *, days_back: int = 7, max_results: int = 100, per_category_cap: int = 150
    ) -> dict[str, Any]:
        latest = await self._repo.latest_by_source_type("INNOVATION_ARXIV_KR")
        week_start = (latest.raw_metadata or {}).get("week_start") if latest else None
        collector = ArxivPapersCollector()
        rows, stats = await collector.collect(
            days_back=days_back,
            max_results=max_results,
            per_category_cap=per_category_cap,
            watermark=ArxivWatermark(last_week_start=week_start),
        )
        current_week = str(stats.get("week_start") or "")
        for dto in rows:
            dto.raw_metadata = {**(dto.raw_metadata or {}), "week_start": current_week}
        inserted = await self._repo.insert_many_skip_duplicates(rows)
        result = {
            "source": "arxiv",
            "fetched": len(rows),
            "inserted": inserted,
            "not_inserted": len(rows) - inserted,
            "stats": stats,
        }
        logger.info("Bronze innovation arXiv ingest: %s", result)
        return result

    async def ingest_github_trending(self, *, days_back: int = 7) -> dict[str, Any]:
        latest = await self._repo.latest_by_source_type("INNOVATION_GITHUB_TRENDING")
        week_start = (latest.raw_metadata or {}).get("week_start") if latest else None
        collector = GithubTrendingCollector(self._github_token)
        rows, stats = await collector.collect(
            days_back=days_back,
            watermark=GithubWatermark(last_week_start=week_start),
        )
        inserted = await self._repo.insert_many_skip_duplicates(rows)
        result = {
            "source": "github_trending",
            "fetched": len(rows),
            "inserted": inserted,
            "not_inserted": len(rows) - inserted,
            "stats": stats,
        }
        logger.info("Bronze innovation GitHub ingest: %s", result)
        return result

    async def ingest_techblog_kr(
        self, *, max_items_per_feed: int = 30
    ) -> dict[str, Any]:
        collector = TechBlogKrCollector()
        rows, stats = await collector.collect(max_items_per_feed=max_items_per_feed)
        inserted = await self._repo.insert_many_skip_duplicates(rows)
        result = {
            "source": "techblog_kr",
            "fetched": len(rows),
            "inserted": inserted,
            "not_inserted": len(rows) - inserted,
            "stats": stats,
        }
        logger.info("Bronze innovation TechBlog KR ingest: %s", result)
        return result

    async def ingest_customs_export(
        self,
        *,
        customs_service_key: str,
        yearmonth: str | None = None,
    ) -> dict[str, Any]:
        collector = CustomsExportCollector(customs_service_key)
        rows, stats = await collector.collect(yearmonth=yearmonth)
        inserted = await self._repo.insert_many_skip_duplicates(rows)
        result = {
            "source": "customs_export",
            "fetched": len(rows),
            "inserted": inserted,
            "not_inserted": len(rows) - inserted,
            "stats": stats,
        }
        logger.info("Bronze innovation Customs Export ingest: %s", result)
        return result

    async def ingest_kistep(self) -> dict[str, Any]:
        collector = KistepReportCollector()
        rows, stats = await collector.collect()
        inserted = await self._repo.insert_many_skip_duplicates(rows)
        result = {
            "source": "kistep_report",
            "fetched": len(rows),
            "inserted": inserted,
            "not_inserted": len(rows) - inserted,
            "stats": stats,
        }
        logger.info("Bronze innovation KISTEP ingest: %s", result)
        return result

    async def ingest_kiat_tech_demand(
        self, *, service_key: str, max_items: int = 200
    ) -> dict[str, Any]:
        """KIAT 기술은행 수요기술(기업의 기술 수요 = TECH_DEMAND_SIGNAL) 수집."""
        if not service_key:
            raise ValueError("TECH_DEMAND_SIGNAL(KIAT 수요기술 키)이 설정되어 있지 않습니다.")
        rows, stats = await KiatTechDemandCollector(service_key).collect(max_items=max_items)
        inserted = await self._repo.insert_many_skip_duplicates(rows)
        result = {
            "source": "kiat_tech_demand",
            "fetched": len(rows),
            "inserted": inserted,
            "not_inserted": len(rows) - inserted,
            "stats": stats,
        }
        logger.info("Bronze innovation KIAT 수요기술 ingest: %s", result)
        return result

