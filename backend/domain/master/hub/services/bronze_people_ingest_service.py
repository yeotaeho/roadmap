"""사람·역량 수요 컬렉터 실행과 Bronze 적재를 조정한다."""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from domain.master.hub.repositories.people_repository import PeopleRepository
from domain.master.hub.services.collectors.people.hrdnet.hrdnet_training_collector import (
    HrdnetTrainingCollector,
)
from domain.master.hub.services.collectors.people.worknet.worknet_job_info_collector import (
    WorknetJobInfoCollector,
)
from domain.master.hub.services.collectors.people.careernet.careernet_collector import (
    CareernetCollector,
)
from domain.master.hub.services.collectors.people.goyong24.recruit_collector import (
    Goyong24RecruitCollector,
)
from domain.master.hub.services.collectors.people.saramin.saramin_recruit_collector import (
    SaraminRecruitCollector,
)

logger = logging.getLogger(__name__)


class BronzePeopleIngestService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        worknet_api_key: str | None = None,
        hrdnet_api_key: str | None = None,
        saramin_api_key: str | None = None,
        careernet_api_key: str | None = None,
        goyong24_recruit_api_key: str | None = None,
    ) -> None:
        self._repo = PeopleRepository(session)
        self._worknet_api_key = worknet_api_key
        self._hrdnet_api_key = hrdnet_api_key
        self._saramin_api_key = saramin_api_key
        self._careernet_api_key = careernet_api_key
        self._goyong24_recruit_api_key = goyong24_recruit_api_key

    async def ingest_worknet_job_info(self) -> dict[str, Any]:
        if not self._worknet_api_key:
            raise ValueError("WORKNET_API_KEY가 설정되어 있지 않습니다.")
        today = date.today()
        latest = await self._repo.latest_reference_date("PEOPLE_WORKNET_JOB")
        if latest == today:
            return {"source": "worknet_jobs", "fetched": 0, "inserted": 0, "skipped_date": str(today)}
        rows, stats = await WorknetJobInfoCollector(self._worknet_api_key).collect(
            reference_date=today
        )
        inserted = await self._repo.insert_many_skip_duplicates(rows)
        result = {
            "source": "worknet_jobs",
            "fetched": len(rows),
            "inserted": inserted,
            "not_inserted": len(rows) - inserted,
            "stats": stats,
        }
        logger.info("Bronze people WorkNet ingest: %s", result)
        return result

    async def ingest_hrdnet_training(self) -> dict[str, Any]:
        if not self._hrdnet_api_key:
            raise ValueError("HRDNET_API_KEY가 설정되어 있지 않습니다.")
        today = date.today()
        latest = await self._repo.latest_reference_date("PEOPLE_HRDNET_TRAINING")
        if latest == today:
            return {"source": "hrdnet_training", "fetched": 0, "inserted": 0, "skipped_date": str(today)}
        rows, stats = await HrdnetTrainingCollector(self._hrdnet_api_key).collect(
            reference_date=today
        )
        inserted = await self._repo.insert_many_skip_duplicates(rows)
        result = {
            "source": "hrdnet_training",
            "fetched": len(rows),
            "inserted": inserted,
            "not_inserted": len(rows) - inserted,
            "stats": stats,
        }
        logger.info("Bronze people HRD-Net ingest: %s", result)
        return result

    async def ingest_careernet(self) -> dict[str, Any]:
        if not self._careernet_api_key:
            raise ValueError("CAREERNET_API_KEY가 설정되어 있지 않습니다.")
        today = date.today()
        latest = await self._repo.latest_reference_date("PEOPLE_CAREERNET_JOB")
        if latest == today:
            return {"source": "careernet", "fetched": 0, "inserted": 0, "skipped_date": str(today)}
        rows, stats = await CareernetCollector(self._careernet_api_key).collect(
            reference_date=today
        )
        inserted = await self._repo.insert_many_skip_duplicates(rows)
        result = {
            "source": "careernet",
            "fetched": len(rows),
            "inserted": inserted,
            "not_inserted": len(rows) - inserted,
            "stats": stats,
        }
        logger.info("Bronze people Careernet ingest: %s", result)
        return result

    async def ingest_goyong24_recruit(self, *, max_pages: int = 5) -> dict[str, Any]:
        if not self._goyong24_recruit_api_key:
            raise ValueError("GOYONG24_RECRUIT_API_KEY가 설정되어 있지 않습니다.")
        today = date.today()
        latest = await self._repo.latest_reference_date("PEOPLE_GOYONG24_RECRUIT")
        if latest == today:
            return {
                "source": "goyong24_recruit",
                "fetched": 0,
                "inserted": 0,
                "skipped_date": str(today),
            }
        rows, stats = await Goyong24RecruitCollector(
            self._goyong24_recruit_api_key
        ).collect(reference_date=today, max_pages=max_pages)
        inserted = await self._repo.insert_many_skip_duplicates(rows)
        result = {
            "source": "goyong24_recruit",
            "fetched": len(rows),
            "inserted": inserted,
            "not_inserted": len(rows) - inserted,
            "stats": stats,
        }
        logger.info("Bronze people 고용24 채용 ingest: %s", result)
        return result

    async def ingest_saramin_recruit(self) -> dict[str, Any]:
        if not self._saramin_api_key:
            raise ValueError("SARAMIN_ACCESS_KEY가 설정되어 있지 않습니다.")
        today = date.today()
        latest = await self._repo.latest_reference_date("PEOPLE_SARAMIN_RECRUIT")
        if latest == today:
            return {
                "source": "saramin_recruit",
                "fetched": 0,
                "inserted": 0,
                "skipped_date": str(today),
            }
        rows, stats = await SaraminRecruitCollector(self._saramin_api_key).collect(
            reference_date=today
        )
        inserted = await self._repo.insert_many_skip_duplicates(rows)
        result = {
            "source": "saramin_recruit",
            "fetched": len(rows),
            "inserted": inserted,
            "not_inserted": len(rows) - inserted,
            "stats": stats,
        }
        logger.info("Bronze people 사람인 채용 ingest: %s", result)
        return result
