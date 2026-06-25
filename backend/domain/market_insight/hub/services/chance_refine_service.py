# Silver/Gold — opportunity 공고에서 유형·대상·혜택·자격을 LLM 추출해 Chance 공고 카드로 사영하는 서비스

from __future__ import annotations

import hashlib

from sqlalchemy.ext.asyncio import AsyncSession

from core.config.settings import get_settings
from core.llm.client import LlmClient
from domain.market_insight.hub.repositories.chance_repository import ChanceRepository
from domain.market_insight.hub.services.text_sector_classify_service import SECTOR_SLUGS

PROMPT_VERSION = "v1"
ACTIVE_WINDOW_DAYS = 120
DEFAULT_LIMIT = 200
MAX_INPUT_CHARS = 3000


class ChanceRefineService:
    """opportunity → 추출(refined_chance_insights) → chance_opportunities 사영."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = ChanceRepository(session)
        settings = get_settings()
        self._model = settings.llm_classify_model
        self._llm = LlmClient(api_key=settings.openai_api_key, model=self._model)

    async def refine_and_serve(
        self, window_days: int = ACTIVE_WINDOW_DAYS, limit: int = DEFAULT_LIMIT
    ) -> dict:
        """미처리 공고를 추출·적재 후 Gold upsert. 멱등.

        반환: {"scanned", "extracted", "skipped", "opportunities"}.
        """
        rows = await self.repo.fetch_unprocessed(PROMPT_VERSION, window_days, limit)
        extracted = 0
        skipped = 0
        for r in rows:
            input_text = (r.body or "").strip()[:MAX_INPUT_CHARS]
            result = await self._llm.extract_chance(input_text, SECTOR_SLUGS)
            await self.repo.upsert_silver(
                {
                    "sector_slug": result["sector_slug"],
                    "extracted_type": result["type"],
                    "target": result["target"],
                    "benefits": result["benefits"],
                    "qualifications": result["qualifications"],
                    "deadline": r.deadline,
                    "ref_date": r.ref_date,
                    "raw_id": r.raw_id,
                    "model_name": self._model,
                    "prompt_version": PROMPT_VERSION,
                    "input_hash": hashlib.sha256(input_text.encode("utf-8")).hexdigest(),
                }
            )
            if result["type"] is not None:
                extracted += 1
            else:
                skipped += 1
        opportunities = await self.repo.project_to_gold(PROMPT_VERSION)
        await self.session.commit()
        return {
            "scanned": len(rows),
            "extracted": extracted,
            "skipped": skipped,
            "opportunities": opportunities,
        }
