# 추천 설명 서비스 — 설명 없는 Sync/Chance 상위 항목을 사용자당 LLM 1회로 일괄 설명(일일 배치)

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from core.config.settings import get_settings
from core.llm.client import LlmClient
from domain.market_insight.hub.repositories.recommend_explain_repository import (
    RecommendExplainRepository,
)
from domain.market_insight.hub.services.sync_refine_service import INSUFFICIENT_BADGE
from domain.market_insight.hub.services.user_embed_text import RIASEC_LABEL

logger = logging.getLogger(__name__)

TOP_SYNC = 3
TOP_CHANCE = 10
EVIDENCE_POS = 5
EVIDENCE_DISLIKE = 3
MAX_USERS_PER_RUN = 200


def _is_dislike(ev: dict) -> bool:
    return ev.get("dimension") == "dislike" or ev.get("polarity") == "dislike"


def _build_user_context(ctx_row: dict | None, evidence: list[dict]) -> dict:
    """LLM 프롬프트용 사용자 컨텍스트(순수). 비민감 근거만 받는다는 전제(리포 필터)."""
    ctx = ctx_row or {}
    riasec = ctx.get("riasec")
    codes = riasec.get("top_codes") if isinstance(riasec, dict) else None
    labels = [RIASEC_LABEL[c] for c in codes if c in RIASEC_LABEL] if isinstance(codes, list) else []
    positives = [e["content"] for e in evidence if not _is_dislike(e)][:EVIDENCE_POS]
    dislikes = [e["content"] for e in evidence if _is_dislike(e)][:EVIDENCE_DISLIKE]
    return {
        "target_job": ctx.get("target_job"),
        "interest_keywords": ctx.get("interest_keywords") or [],
        "riasec_labels": labels,
        "narrative": ctx.get("narrative_summary"),
        "positives": positives,
        "dislikes": dislikes,
    }


class RecommendExplainService:
    """설명 없는 오늘 Sync 상위·Chance 상위 항목을 사용자 단위로 묶어 LLM 설명 생성·기록."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = RecommendExplainRepository(session)
        settings = get_settings()
        self._api_key = settings.openai_api_key
        self._model = settings.llm_classify_model
        self._explainer = self._default_explainer

    async def _default_explainer(
        self, user_context: dict, sync_items: list[dict], chance_items: list[dict]
    ) -> dict:
        llm = LlmClient(api_key=self._api_key, model=self._model)
        return await llm.explain_recommendations(user_context, sync_items, chance_items)

    async def explain_pending(self, limit: int = MAX_USERS_PER_RUN) -> dict:
        """설명 대상 사용자를 스캔해 사용자당 1회 생성한다. 건별 실패 격리·멱등."""
        if not self._api_key:
            return {"skipped": True, "reason": "no_api_key"}
        sync_rows = await self.repo.fetch_unexplained_sync(TOP_SYNC, INSUFFICIENT_BADGE)
        match_rows = await self.repo.fetch_unexplained_matches(TOP_CHANCE)

        by_user: dict[str, dict] = {}
        for r in sync_rows:
            by_user.setdefault(str(r.user_id), {"sync": [], "chance": []})["sync"].append(
                {
                    "sector_slug": r.sector_slug,
                    "sector_name": r.sector_name,
                    "score": r.score,
                    "badge": r.badge,
                    "affinity_score": float(r.affinity_score) if r.affinity_score is not None else None,
                    "trend_score": float(r.trend_score) if r.trend_score is not None else None,
                }
            )
        for r in match_rows:
            by_user.setdefault(str(r.user_id), {"sync": [], "chance": []})["chance"].append(
                {
                    "opportunity_id": int(r.opportunity_id),
                    "title": r.title,
                    "opportunity_type": r.opportunity_type,
                    "match_score": r.match_score,
                    "match_reason": r.match_reason,
                }
            )

        uids = list(by_user)[:limit]
        ctx_map = await self.repo.fetch_user_context(uids)
        ev_map = await self.repo.fetch_context_evidence(uids)

        processed = failed = written = 0
        for uid in uids:
            items = by_user[uid]
            try:
                user_context = _build_user_context(ctx_map.get(uid), ev_map.get(uid, []))
                result = await self._explainer(user_context, items["sync"], items["chance"])
                user_written = 0
                for it in result.get("sync", []):
                    await self.repo.update_sync_explanation(uid, it["sector_slug"], it["text"])
                    user_written += 1
                for it in result.get("chance", []):
                    await self.repo.update_match_explanation(uid, it["opportunity_id"], it["text"])
                    user_written += 1
                await self.session.commit()
                # rollback 된 건이 통계에 남지 않도록 커밋 성공 후에만 합산.
                written += user_written
                processed += 1
            except Exception as e:
                await self.session.rollback()
                logger.warning(f"추천 설명 생성 실패(user {uid}): {e}")
                failed += 1
        return {"users": len(uids), "processed": processed, "failed": failed, "written": written}
