"""Pulse 정제·서빙 — raw 혁신신호 집계 → Silver 정규화 → Gold 사영(멱등 재생성)."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from domain.market_insight.hub.repositories.pulse_repository import PulseRepository
from domain.market_insight.hub.services.pulse_pipeline import (
    BaselineMethod,
    compute_silver,
    project_to_gold,
)


class PulseRefineService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = PulseRepository(session)

    async def refine_and_serve(
        self,
        window_days: int = 20,
        baseline_method: BaselineMethod = "zscore",
    ) -> dict:
        """raw → Silver → Gold 한 줄을 실행하고 적재 건수를 반환한다."""
        signals = await self.repo.fetch_innovation_signals()
        silver = compute_silver(signals, window_days=window_days, baseline_method=baseline_method)
        silver_n = await self.repo.replace_silver(silver, baseline_method)
        gold = project_to_gold(silver)
        gold_n = await self.repo.replace_gold(gold)
        await self.session.commit()
        return {"signals": len(signals), "silver": silver_n, "gold": gold_n}
