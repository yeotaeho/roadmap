# NCS 역량 온톨로지 마스터 수집/적재 서비스

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from domain.master.hub.repositories.ncs_master_repository import NcsMasterRepository
from domain.master.hub.services.collectors.people.ncs.ncs_info_collector import NcsInfoCollector
from domain.master.hub.services.collectors.people.ncs.ncs_standard_collector import (
    NcsStandardCollector,
)
from domain.master.models.transfer.ncs_master_dto import NcsMasterDto

logger = logging.getLogger(__name__)


class BronzeNcsIngestService:
    """NCS 국가직무능력표준 역량 온톨로지 마스터 수집 → `ncs_competency_master` UPSERT 서비스."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        ncs_standard_key: str | None = None,
        ncs_info_key: str | None = None,
    ) -> None:
        self._ncs_standard_key = ncs_standard_key
        self._ncs_info_key = ncs_info_key
        self._repo = NcsMasterRepository(session)

    async def ingest_ncs_standard(self, *, max_depth: int = 5) -> dict[str, Any]:
        """NCS 기준정보 API (15128213) 수집 → ncs_competency_master UPSERT."""
        if not self._ncs_standard_key:
            raise ValueError("NCS_STANDARD_SERVICE_KEY 가 설정되어 있지 않습니다.")

        collector = NcsStandardCollector(self._ncs_standard_key)
        dtos: list[NcsMasterDto] = []
        stats: dict[str, int] = {}
        try:
            dtos, stats = await collector.collect(max_depth=max_depth)
        except Exception:
            logger.exception(
                "NCS Standard Bronze 수집 실패(API 오류·네트워크 등). 빈 결과로 진행합니다."
            )

        upserted = await self._repo.upsert_many(dtos)

        result: dict[str, Any] = {
            "source": "ncs_standard",
            "fetched": len(dtos),
            "upserted": upserted,
            "level_stats": stats,
        }
        logger.info("Bronze NCS Standard ingest: %s", result)
        return result

    async def ingest_ncs_info(self) -> dict[str, Any]:
        """NCS 관련 정보 API (15063879) 보충 수집 → ncs_competency_master UPSERT.

        NcsInfoCollector 구현 완료 전까지 NotImplementedError 가 발생한다.
        """
        if not self._ncs_info_key:
            raise ValueError("NCS_INFO_SERVICE_KEY 가 설정되어 있지 않습니다.")

        collector = NcsInfoCollector(self._ncs_info_key)
        dtos: list[NcsMasterDto] = []
        stats: dict[str, int] = {}
        try:
            dtos, stats = await collector.collect()
        except NotImplementedError:
            raise
        except Exception:
            logger.exception(
                "NCS Info Bronze 수집 실패(API 오류·네트워크 등). 빈 결과로 진행합니다."
            )

        upserted = await self._repo.upsert_many(dtos)

        result: dict[str, Any] = {
            "source": "ncs_info",
            "fetched": len(dtos),
            "upserted": upserted,
            "level_stats": stats,
        }
        logger.info("Bronze NCS Info ingest: %s", result)
        return result


__all__ = ["BronzeNcsIngestService"]
