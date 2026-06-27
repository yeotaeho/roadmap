# Gold 사영 — discourse·tech_demand Silver 를 소스별 pv 로 단일 재조립하는 서비스

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from core.config.settings import get_settings
from domain.market_insight.hub.repositories.gap_repository import GapRepository
from domain.market_insight.hub.services.gap_refine_service import (
    PROMPT_VERSION as DISCOURSE_PV,
)
from domain.market_insight.hub.services.tech_demand_gap_service import (
    PROMPT_VERSION as TECH_DEMAND_PV,
)


class GapProjectionService:
    """discourse(disc_pv)+tech_demand(td_pv) Silver → gap_issues 단일 재조립(youth_fit 게이트)."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = GapRepository(session)
        self._fit_min = get_settings().tech_demand_youth_fit_min

    async def project_and_serve(self) -> dict:
        """전소스 Gold 재생성 후 commit. 멱등. 반환: {"issues"}."""
        issues = await self.repo.project_to_gold(
            DISCOURSE_PV, TECH_DEMAND_PV, self._fit_min
        )
        await self.session.commit()
        return {"issues": issues}
