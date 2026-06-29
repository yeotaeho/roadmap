"""Bronze 기회(Opportunity) 파이프라인 — 소스별 Collector 호출 후 `raw_opportunity_data` 적재."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from domain.master.hub.repositories.opportunity_repository import OpportunityRepository
from domain.master.hub.services.collectors.opportunity.smes_collector import (
    SmesOpenAPICollector,
)
from domain.master.hub.services.collectors.opportunity.kstartup.kstartup_collector import (
    KStartupCollector,
)
from domain.master.hub.services.collectors.opportunity.narajangteo.narajangteo_collector import (
    NarajangteoCollector,
)
from domain.master.hub.services.collectors.opportunity.youth.youth_policy_collector import (
    YouthPolicyCollector,
)
from domain.master.hub.services.collectors.opportunity.youth.youth_center_collector import (
    YouthCenterCollector,
)
from domain.master.hub.services.collectors.opportunity.youth.youth_content_collector import (
    YouthContentCollector,
)
from domain.master.hub.services.collectors.opportunity.youth.youth_policy_direction_collector import (
    YouthPolicyDirectionCollector,
)
from domain.master.models.transfer.opportunity_collect_dto import OpportunityCollectDto

logger = logging.getLogger(__name__)


class BronzeOpportunityIngestService:
    def __init__(
        self,
        session: AsyncSession,
        smes_service_key: str | None = None,
        *,
        kstartup_service_key: str | None = None,
        narajangteo_service_key: str | None = None,
        youth_policy_service_key: str | None = None,
    ):
        self._session = session
        self._smes_key = smes_service_key
        self._kstartup_key = kstartup_service_key
        self._narajangteo_key = narajangteo_service_key
        self._youth_policy_key = youth_policy_service_key
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

    async def ingest_kstartup(self, *, max_items: int = 100) -> dict[str, Any]:
        """창업진흥원 K-Startup 통합공고 수집."""
        if not self._kstartup_key:
            raise ValueError("KSTARTUP_SERVICE_KEY 가 설정되어 있지 않습니다.")
        dtos: list[OpportunityCollectDto] = []
        try:
            dtos = await KStartupCollector(self._kstartup_key).collect(max_items=max_items)
        except Exception:
            logger.exception("K-Startup 공고 Bronze 수집 실패. 빈 결과로 진행합니다.")
        inserted = await self._opportunity_repo.insert_many_skip_duplicates(dtos)
        result = {
            "source": "kstartup",
            "fetched": len(dtos),
            "inserted": inserted,
            "not_inserted": max(0, len(dtos) - inserted),
        }
        logger.info("Bronze opportunity K-Startup ingest: %s", result)
        return result

    async def ingest_narajangteo(self, *, max_items: int = 100) -> dict[str, Any]:
        """조달청 나라장터 입찰공고 수집 (정부→민간 자본 흐름 신호)."""
        if not self._narajangteo_key:
            raise ValueError("NARAJANGTEO_SERVICE_KEY 가 설정되어 있지 않습니다.")
        dtos: list[OpportunityCollectDto] = []
        try:
            dtos = await NarajangteoCollector(self._narajangteo_key).collect(max_items=max_items)
        except Exception:
            logger.exception("나라장터 입찰공고 Bronze 수집 실패. 빈 결과로 진행합니다.")
        inserted = await self._opportunity_repo.insert_many_skip_duplicates(dtos)
        result = {
            "source": "narajangteo",
            "fetched": len(dtos),
            "inserted": inserted,
            "not_inserted": max(0, len(dtos) - inserted),
        }
        logger.info("Bronze opportunity 나라장터 ingest: %s", result)
        return result

    async def ingest_youth_policy(self, *, max_items: int = 200) -> dict[str, Any]:
        """온통청년 청년정책(일자리·주거·교육·복지) 수집."""
        if not self._youth_policy_key:
            raise ValueError("YOUTH_POLICY_SERVICE_KEY 가 설정되어 있지 않습니다.")
        dtos: list[OpportunityCollectDto] = []
        try:
            dtos = await YouthPolicyCollector(self._youth_policy_key).collect(max_items=max_items)
        except Exception:
            logger.exception("온통청년 청년정책 Bronze 수집 실패. 빈 결과로 진행합니다.")
        inserted = await self._opportunity_repo.insert_many_skip_duplicates(dtos)
        result = {
            "source": "youth_policy",
            "fetched": len(dtos),
            "inserted": inserted,
            "not_inserted": max(0, len(dtos) - inserted),
        }
        logger.info("Bronze opportunity 온통청년 청년정책 ingest: %s", result)
        return result

    async def ingest_youth_center(self, *, max_items: int = 200) -> dict[str, Any]:
        """온통청년 청년센터(오프라인 지원기관 마스터) 수집."""
        if not self._youth_policy_key:
            raise ValueError("YOUTH_POLICY_SERVICE_KEY 가 설정되어 있지 않습니다.")
        dtos: list[OpportunityCollectDto] = []
        try:
            dtos = await YouthCenterCollector(self._youth_policy_key).collect(max_items=max_items)
        except Exception:
            logger.exception("온통청년 청년센터 Bronze 수집 실패. 빈 결과로 진행합니다.")
        inserted = await self._opportunity_repo.insert_many_skip_duplicates(dtos)
        result = {
            "source": "youth_center",
            "fetched": len(dtos),
            "inserted": inserted,
            "not_inserted": max(0, len(dtos) - inserted),
        }
        logger.info("Bronze opportunity 온통청년 청년센터 ingest: %s", result)
        return result

    async def ingest_youth_content(self, *, max_items: int = 200) -> dict[str, Any]:
        """온통청년 청년콘텐츠(청년 대상 아티클·콘텐츠) 수집."""
        if not self._youth_policy_key:
            raise ValueError("YOUTH_POLICY_SERVICE_KEY 가 설정되어 있지 않습니다.")
        dtos: list[OpportunityCollectDto] = []
        try:
            dtos = await YouthContentCollector(self._youth_policy_key).collect(max_items=max_items)
        except Exception:
            logger.exception("온통청년 청년콘텐츠 Bronze 수집 실패. 빈 결과로 진행합니다.")
        inserted = await self._opportunity_repo.insert_many_skip_duplicates(dtos)
        result = {
            "source": "youth_content",
            "fetched": len(dtos),
            "inserted": inserted,
            "not_inserted": max(0, len(dtos) - inserted),
        }
        logger.info("Bronze opportunity 온통청년 청년콘텐츠 ingest: %s", result)
        return result

    async def ingest_youth_policy_direction(self, *, max_items: int = 100) -> dict[str, Any]:
        """온통청년 기본계획정책방향(거시 신호) 수집."""
        if not self._youth_policy_key:
            raise ValueError("YOUTH_POLICY_SERVICE_KEY 가 설정되어 있지 않습니다.")
        dtos: list[OpportunityCollectDto] = []
        try:
            dtos = await YouthPolicyDirectionCollector(self._youth_policy_key).collect(
                max_items=max_items
            )
        except Exception:
            logger.exception("온통청년 기본계획정책방향 Bronze 수집 실패. 빈 결과로 진행합니다.")
        inserted = await self._opportunity_repo.insert_many_skip_duplicates(dtos)
        result = {
            "source": "youth_policy_direction",
            "fetched": len(dtos),
            "inserted": inserted,
            "not_inserted": max(0, len(dtos) - inserted),
        }
        logger.info("Bronze opportunity 온통청년 기본계획정책방향 ingest: %s", result)
        return result

    async def purge_by_source_type(self, source_type: str) -> dict[str, Any]:
        deleted = await self._opportunity_repo.delete_by_source_type(source_type)
        result = {"source_type": source_type, "deleted": deleted}
        logger.info("Bronze opportunity purge: %s", result)
        return result
