# Silver — 투자 뉴스 헤드라인에서 투자 금액(자본 흐름 강도)을 LLM 추출해 적재하는 서비스

from __future__ import annotations

import hashlib

from sqlalchemy.ext.asyncio import AsyncSession

from core.config.settings import get_settings
from core.llm.client import LlmClient
from domain.market_insight.hub.repositories.investment_repository import InvestmentRepository

# v2 — 제목만으로는 다이제스트류 금액 추출이 불가해(성공 1/92) 본문을 입력에 포함.
PROMPT_VERSION = "v2"
ACTIVE_WINDOW_DAYS = 90
DEFAULT_LIMIT = 200
MAX_INPUT_CHARS = 1500
# LLM 추출 중간 적재·커밋 주기 — pool_recycle(5분) 초과 방지.
REFINE_CHUNK = 25


class InvestmentFlowRefineService:
    """투자/펀딩/M&A 뉴스 → 금액 추출(refined_investment_flows) 적재. 멱등."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = InvestmentRepository(session)
        settings = get_settings()
        self._model = settings.llm_classify_model
        self._llm = LlmClient(api_key=settings.openai_api_key, model=self._model)

    async def refine_and_serve(
        self, window_days: int = ACTIVE_WINDOW_DAYS, limit: int = DEFAULT_LIMIT
    ) -> dict:
        """미처리 투자뉴스에서 금액을 추출·적재한다. 멱등.

        반환: {"scanned", "extracted"} (extracted = 금액이 잡힌 행 수).
        """
        rows = await self.repo.fetch_unprocessed(PROMPT_VERSION, window_days, limit)
        extracted = 0
        for i, r in enumerate(rows, start=1):
            base = (r.title or "").strip()
            if r.company_hint:
                base = f"{base} ({r.company_hint})"
            body = (r.body or "").strip()
            if body:
                base = f"{base}\n{body}"
            input_text = base[:MAX_INPUT_CHARS]
            result = await self._llm.extract_investment(input_text)
            await self.repo.upsert_silver(
                {
                    "amount_krw": result["amount_krw"],
                    "currency": result["currency"],
                    "series": result["series"],
                    "company": result["company"] or (r.company_hint or None),
                    "ref_date": r.ref_date,
                    "raw_id": r.raw_id,
                    "model_name": self._model,
                    "prompt_version": PROMPT_VERSION,
                    "input_hash": hashlib.sha256(input_text.encode("utf-8")).hexdigest(),
                }
            )
            if result["amount_krw"] is not None:
                extracted += 1
            if i % REFINE_CHUNK == 0:
                await self.session.commit()
        await self.session.commit()
        return {"scanned": len(rows), "extracted": extracted}
