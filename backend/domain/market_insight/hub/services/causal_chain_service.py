# Silver/Gold — economic 본문에서 거시→산업→청년기회 인과사슬을 LLM 추출해 카드로 사영하는 서비스

from __future__ import annotations

import hashlib

from sqlalchemy.ext.asyncio import AsyncSession

from core.config.settings import get_settings
from core.llm.client import LlmClient
from domain.market_insight.hub.repositories.causal_chain_repository import (
    CausalChainRepository,
)

PROMPT_VERSION = "v1"
ACTIVE_WINDOW_DAYS = 90
DEFAULT_LIMIT = 200
MAX_INPUT_CHARS = 3000
# LLM 추출 중간 적재·커밋 주기 — pool_recycle(5분) 초과 방지.
REFINE_CHUNK = 25


class CausalChainRefineService:
    """분류된 economic → 인과사슬 추출(refined_causal_chain_insights) → causal_chains 사영."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = CausalChainRepository(session)
        settings = get_settings()
        self._model = settings.llm_classify_model
        self._conf_min = settings.llm_classify_confidence_min
        self._llm = LlmClient(api_key=settings.openai_api_key, model=self._model)

    async def refine_and_serve(
        self, window_days: int = ACTIVE_WINDOW_DAYS, limit: int = DEFAULT_LIMIT
    ) -> dict:
        """미처리 economic을 추출·적재 후 Gold 재생성. 멱등.

        반환: {"scanned", "chains", "gold"}.
        """
        rows = await self.repo.fetch_unprocessed(
            PROMPT_VERSION, self._conf_min, window_days, limit
        )
        chains = 0
        for i, r in enumerate(rows, start=1):
            input_text = (r.body or "").strip()[:MAX_INPUT_CHARS]
            result = await self._llm.extract_causal_chain(input_text)
            await self.repo.upsert_silver(
                {
                    "sector_slug": r.sector_slug,
                    "macro_event": result["macro_event"],
                    "industry_impact": result["industry_impact"],
                    "youth_chance": result["youth_chance"],
                    "ref_date": r.ref_date,
                    "raw_id": r.raw_id,
                    "model_name": self._model,
                    "prompt_version": PROMPT_VERSION,
                    "input_hash": hashlib.sha256(input_text.encode("utf-8")).hexdigest(),
                }
            )
            if result["macro_event"] is not None:
                chains += 1
            if i % REFINE_CHUNK == 0:
                await self.session.commit()
        gold = await self.repo.project_to_gold(PROMPT_VERSION)
        await self.session.commit()
        return {"scanned": len(rows), "chains": chains, "gold": gold}
