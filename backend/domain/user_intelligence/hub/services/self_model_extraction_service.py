# 자기모델 추출 서비스 — 코치 대화(최근 미추출분)에서 자기모델 신호를 증분 추출·반영

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from core.config.settings import get_settings
from core.llm.client import LlmClient
from domain.user_intelligence.hub.repositories.consult_session_repository import ConsultSessionRepository
from domain.user_intelligence.hub.services.self_model_service import SelfModelService

logger = logging.getLogger(__name__)

MIN_NEW = 6
SOURCE = "consult_extraction"
NARRATIVE_DEFAULT_CONFIDENCE = 0.6  # LLM이 narrative 를 non-null 로 낸 것 자체가 최소 신뢰 신호(riasec 무관, gate 통과 보장)


class SelfModelExtractionService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.coach_repo = ConsultSessionRepository(db)
        settings = get_settings()
        self._api_key = settings.openai_api_key
        self._model = settings.llm_classify_model
        self._extractor = self._default_extractor

    async def _default_extractor(self, messages: list[dict]) -> dict:
        llm = LlmClient(api_key=self._api_key, model=self._model)
        return await llm.extract_self_model(messages)

    async def extract_session(self, user_id: str, session_id: str) -> dict:
        """세션의 미추출 대화에서 자기모델을 갱신한다. 신규 메시지 부족 시 스킵."""
        sess = await self.coach_repo.get_session(session_id)
        if sess is None:
            return {"skipped": True, "reason": "no_session"}
        extracted_until = sess["extracted_until"]
        msgs = await self.coach_repo.fetch_messages(session_id)
        cutoff = len(msgs)
        new_msgs = msgs[extracted_until:cutoff]
        if len(new_msgs) < MIN_NEW:
            return {"skipped": True, "reason": "insufficient"}

        result = await self._extractor(new_msgs)
        svc = SelfModelService(self.db)
        r_conf = result["riasec_axis_confidence"]
        bf_conf = result["big_five_axis_confidence"]
        axis_confidence = {
            "riasec": sum(r_conf.values()) / len(r_conf) if r_conf else 0.0,
            "big_five": sum(bf_conf.values()) / len(bf_conf) if bf_conf else 0.0,
        }
        if result["narrative"]:
            axis_confidence["narrative_summary"] = max(axis_confidence["riasec"], NARRATIVE_DEFAULT_CONFIDENCE)
        incoming = {
            "riasec": {"window_scores": result["riasec_scores"], "window_conf": r_conf},
            "big_five": {"window_scores": result["big_five_scores"], "window_conf": bf_conf},
            "narrative_summary": result["narrative"],
            "axis_confidence": axis_confidence,
        }
        await svc.upsert_structured(user_id, incoming, SOURCE)
        n_ev = await svc.append_evidence(user_id, result["evidence"], SOURCE)
        await self.coach_repo.update_extracted(session_id, cutoff)
        return {"extracted": len(new_msgs), "evidence": n_ev, "riasec": True, "big_five": True}

    async def extract_pending(self, limit: int = 20) -> dict:
        """신규 메시지 충분한 세션을 스캔해 각각 추출한다. 건별 실패 격리."""
        rows = await self.coach_repo.fetch_extractable_sessions(MIN_NEW, limit)
        processed = 0
        for r in rows:
            try:
                res = await self.extract_session(r["user_id"], r["id"])
                if not res.get("skipped"):
                    processed += 1
            except Exception as e:
                logger.warning(f"자기모델 추출 실패(session {r['id']}): {e}")
        return {"sessions": len(rows), "processed": processed}
