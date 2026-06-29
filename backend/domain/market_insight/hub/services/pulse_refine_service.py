"""Pulse 정제·서빙 — raw 혁신신호 집계 → Silver 정규화 → Gold 사영(멱등 재생성)."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from core.config.settings import get_settings
from domain.market_insight.hub.repositories.pulse_repository import PulseRepository
from domain.market_insight.hub.services.pulse_pipeline import (
    BaselineMethod,
    compute_silver,
    fuse_signals,
    project_to_gold,
)
from domain.market_insight.hub.services.text_sector_classify_service import PROMPT_VERSION


class PulseRefineService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = PulseRepository(session)

    async def refine_and_serve(
        self,
        window_days: int = 20,
        baseline_method: BaselineMethod = "zscore",
        weights: dict[str, float] | None = None,
        min_history: int = 5,
    ) -> dict:
        """raw 4축 → 가중 융합 → Silver → Gold 한 줄을 실행하고 적재 건수를 반환한다.

        min_history=5: 이력 5점 미만 섹터는 중립(보합) 처리 — 희소 데이터 거짓 급등 차단.
        """
        settings = get_settings()
        axis = await self.repo.fetch_axis_signals(
            text_confidence_min=settings.llm_classify_confidence_min,
            text_prompt_version=PROMPT_VERSION,
        )
        modifiers = await self.repo.fetch_directional_modifiers(
            text_confidence_min=settings.llm_classify_confidence_min,
            text_prompt_version=PROMPT_VERSION,
            center_text=settings.pulse_center_text_sentiment,
        )
        signals = fuse_signals(axis, weights)
        silver = compute_silver(
            signals,
            window_days=window_days,
            baseline_method=baseline_method,
            min_history=min_history,
            modifiers=modifiers,
            sentiment_k=settings.pulse_sentiment_k,
            modifier_window_days=settings.pulse_modifier_window_days,
            modifier_shrink_k=settings.pulse_modifier_shrink_k,
            text_axis_weight=settings.pulse_text_axis_weight,
            market_axis_weight=settings.pulse_market_axis_weight,
        )
        silver_n = await self.repo.replace_silver(silver, baseline_method)
        gold = project_to_gold(silver)
        gold_n = await self.repo.replace_gold(gold)
        await self.session.commit()
        return {
            "axis_signals": len(axis),
            "fused": len(signals),
            "modifiers": len(modifiers),
            "silver": silver_n,
            "gold": gold_n,
        }
