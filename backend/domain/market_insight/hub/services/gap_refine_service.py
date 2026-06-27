# Silver/Gold — discourse 본문에서 미해결 문제·기회를 LLM 추출해 Gap 카드로 사영하는 서비스

from __future__ import annotations

import hashlib

from sqlalchemy.ext.asyncio import AsyncSession

from core.config.settings import get_settings
from core.llm.client import LlmClient
from domain.market_insight.hub.repositories.gap_repository import GapRepository

PROMPT_VERSION = "v1"
ACTIVE_WINDOW_DAYS = 90
DEFAULT_LIMIT = 200
MAX_INPUT_CHARS = 3000
# LLM 추출 중간 적재·커밋 주기 — pool_recycle(5분) 초과 방지.
REFINE_CHUNK = 25


class GapRefineService:
    """분류된 discourse → 문제·기회 추출(refined_gap_insights) → gap_issues·issue_evidences 사영."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = GapRepository(session)
        settings = get_settings()
        self._model = settings.llm_classify_model
        self._conf_min = settings.llm_classify_confidence_min
        self._llm = LlmClient(api_key=settings.openai_api_key, model=self._model)

    async def refine_and_serve(
        self, window_days: int = ACTIVE_WINDOW_DAYS, limit: int = DEFAULT_LIMIT
    ) -> dict:
        """미처리 discourse를 추출·적재. 멱등. 사영은 GapProjectionService 에서 수행.

        반환: {"scanned", "gaps", "skipped"}.
        """
        rows = await self.repo.fetch_unprocessed(
            PROMPT_VERSION, self._conf_min, window_days, limit
        )
        gaps = 0
        skipped = 0
        for i, r in enumerate(rows, start=1):
            input_text = (r.body or "").strip()[:MAX_INPUT_CHARS]
            result = await self._llm.extract_gap(input_text)
            await self.repo.upsert_silver(
                {
                    "sector_slug": r.sector_slug,
                    "problem": result["problem"],
                    "opportunity": result["opportunity"],
                    "detail": result["detail"],
                    "stakeholders": result["stakeholders"],
                    "next_actions": result["next_actions"],
                    "ref_date": r.ref_date,
                    "raw_id": r.raw_id,
                    "model_name": self._model,
                    "prompt_version": PROMPT_VERSION,
                    "input_hash": hashlib.sha256(input_text.encode("utf-8")).hexdigest(),
                }
            )
            if result["problem"] is not None:
                gaps += 1
            else:
                skipped += 1
            if i % REFINE_CHUNK == 0:
                await self.session.commit()
        await self.session.commit()
        return {"scanned": len(rows), "gaps": gaps, "skipped": skipped}
