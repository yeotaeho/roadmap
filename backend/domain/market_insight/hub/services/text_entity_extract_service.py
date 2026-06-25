# Silver — 분류된 raw 자유텍스트에서 신호 토픽·키워드를 LLM 추출해 멱등 적재하는 서비스

from __future__ import annotations

import hashlib

from sqlalchemy.ext.asyncio import AsyncSession

from core.config.settings import get_settings
from core.llm.client import LlmClient
from domain.market_insight.hub.repositories.signal_repository import SignalRepository

PROMPT_VERSION = "v1"
ACTIVE_WINDOW_DAYS = 90
DEFAULT_LIMIT = 300
MAX_INPUT_CHARS = 2000

# raw 테이블 → 신호 종류(data_role) 와 리니지 기여 가중치(lead-lag).
_TARGET_TABLES = ("raw_economic_data", "raw_discourse_data")
_DATA_ROLE = {
    "raw_economic_data": "CAPITAL_FLOW_SIGNAL",
    "raw_discourse_data": "DISCOURSE_SIGNAL",
}
_WEIGHT = {"CAPITAL_FLOW_SIGNAL": 0.6, "DISCOURSE_SIGNAL": 0.5}


class TextEntityExtractService:
    """이미 섹터 분류된 행에서 신호 토픽·키워드를 추출해 refined_innovation_signal(+리니지) 적재."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = SignalRepository(session)
        settings = get_settings()
        self._model = settings.llm_classify_model
        self._conf_min = settings.llm_classify_confidence_min
        self._llm = LlmClient(api_key=settings.openai_api_key, model=self._model)

    async def extract_unextracted(
        self, window_days: int = ACTIVE_WINDOW_DAYS, limit: int = DEFAULT_LIMIT
    ) -> dict:
        """분류됐으나 미추출인 행을 추출·적재한다. 멱등(리니지 링크 충돌 무시).

        반환: {"scanned", "signals", "skipped"} — 스캔/신호적재/토픽없음 건수.
        """
        scanned = 0
        signals = 0
        skipped = 0
        for table_ref in _TARGET_TABLES:
            data_role = _DATA_ROLE[table_ref]
            weight = _WEIGHT[data_role]
            rows = await self.repo.fetch_unextracted_rows(
                table_ref, self._conf_min, window_days, limit
            )
            for raw_id, sector_slug, body, ref_date in rows:
                scanned += 1
                input_text = (body or "").strip()[:MAX_INPUT_CHARS]
                result = await self._llm.extract_signal(input_text)
                if result["signal_topic"] is None:
                    skipped += 1
                    continue
                signal_id = await self.repo.upsert_signal(
                    {
                        "sector_slug": sector_slug,
                        "data_role": data_role,
                        "signal_topic": result["signal_topic"],
                        "confidence": result["confidence"],
                        "extracted_keywords": result["extracted_keywords"],
                        "ref_date": ref_date,
                        "model_name": self._model,
                        "prompt_version": PROMPT_VERSION,
                        "input_hash": hashlib.sha256(input_text.encode("utf-8")).hexdigest(),
                    }
                )
                await self.repo.insert_source_link(signal_id, table_ref, raw_id, weight)
                signals += 1
        await self.session.commit()
        return {"scanned": scanned, "signals": signals, "skipped": skipped}
