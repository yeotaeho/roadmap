"""Bronze 기회(Opportunity) 파이프라인 — 소스별 Collector 호출 후 `raw_opportunity_data` 적재."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from domain.master.hub.repositories.opportunity_repository import OpportunityRepository
from domain.master.hub.services.collectors.opportunity.smes_collector import (
    SmesOpenAPICollector,
)
from domain.master.models.transfer.opportunity_collect_dto import OpportunityCollectDto

logger = logging.getLogger(__name__)


class BronzeOpportunityIngestService:
    def __init__(self, session: AsyncSession, smes_service_key: str | None):
        self._session = session
        self._smes_key = smes_service_key
        self._opportunity_repo = OpportunityRepository(session)

    async def ingest_smes(
        self,
        *,
        max_items: int = 100,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict[str, Any]:
        """중소벤처기업부 사업공고 수집."""
        if not self._smes_key:
            raise ValueError("SMES_SERVICE_KEY 가 설정되어 있지 않습니다.")

        collector = SmesOpenAPICollector(self._smes_key)
        dtos: list[OpportunityCollectDto] = []
        try:
            dtos = await collector.collect(
                max_items=max_items,
                start_date=start_date,
                end_date=end_date,
            )
        except Exception:
            logger.exception(
                "SMES 사업공고 Bronze 수집 실패(API 오류·네트워크 등). 빈 결과로 진행합니다."
            )

        inserted = await self._opportunity_repo.insert_many_skip_duplicates(dtos)

        result = {
            "source": "smes",
            "fetched": len(dtos),
            "inserted": inserted,
            "not_inserted": max(0, len(dtos) - inserted),
        }
        logger.info("Bronze opportunity SMES ingest: %s", result)
        return result

    async def purge_by_source_type(self, source_type: str) -> dict[str, Any]:
        deleted = await self._opportunity_repo.delete_by_source_type(source_type)
        result = {"source_type": source_type, "deleted": deleted}
        logger.info("Bronze opportunity purge: %s", result)
        return result
