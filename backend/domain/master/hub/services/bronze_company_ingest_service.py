"""검증 기업 마스터(Company Master) 컬렉터 실행과 Bronze 적재를 조정한다."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from domain.master.hub.repositories.company_master_repository import (
    CompanyMasterRepository,
)
from domain.master.hub.services.collectors.company.venture_list.venture_list_collector import (
    VentureListCollector,
)

logger = logging.getLogger(__name__)


class BronzeCompanyIngestService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        venture_list_service_key: str | None = None,
    ) -> None:
        self._repo = CompanyMasterRepository(session)
        self._venture_list_key = venture_list_service_key

    async def ingest_venture_list(
        self,
        *,
        max_items: int = 1000,
        resource: str | None = None,
        file_version: str | None = None,
    ) -> dict[str, Any]:
        """중소벤처기업부 벤처기업명단을 verified_company_master에 적재(UPSERT)."""
        if not self._venture_list_key:
            raise ValueError("VENTURE_LIST_SERVICE_KEY 가 설정되어 있지 않습니다.")
        rows, stats = await VentureListCollector(
            self._venture_list_key, resource=resource
        ).collect(max_items=max_items, file_version=file_version)
        upsert = await self._repo.upsert_many(rows)
        result = {
            "source": "venture_list",
            "fetched": len(rows),
            "inserted": upsert["inserted_new"] + upsert["upserted"],
            "not_inserted": max(0, len(rows) - upsert["inserted_new"] - upsert["upserted"]),
            "stats": {**stats, **upsert},
        }
        logger.info("Bronze company 벤처기업명단 ingest: %s", result)
        return result
