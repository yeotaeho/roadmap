# 추천 설명 서비스 — 설명 없는 Sync/Chance 상위 항목을 사용자당 LLM 1회로 일괄 설명(일일 배치).

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

TRAIT_MARGIN = 12  # display 점수가 50±이 값 밖일 때만 뚜렷한 특질로 서술(중립 스킵).

_BIG_FIVE_TRAIT_DESC = {
    "O": ("새로움·아이디어에 개방적", "익숙함·실용을 선호"),
    "C": ("체계적이고 성실함", "유연하고 즉흥적"),
    "E": ("사람과 교류에서 에너지를 얻음", "혼자 깊이 집중하는 걸 선호"),
    "A": ("협력적이고 배려심 있음", "독립적이고 솔직함"),
}
# 신경성 N 은 정서안정성(100-N) 관점으로만 — 병리·약점 규정 금지.
_STABILITY_DESC = ("차분하고 정서적으로 안정적", "신중하게 위험을 살핌")


def _is_dislike(ev: dict) -> bool:
    return ev.get("dimension") == "dislike" or ev.get("polarity") == "dislike"


def big_five_traits(big_five: dict | None) -> list[str]:
    """Big Five 점수에서 뚜렷한 축만 강점·중립 서술어로 변환한다. 순수·결정론.

    각 축 점수가 50±TRAIT_MARGIN 밖일 때만 서술(중립 스킵). N 은 정서안정성(100-N) 관점으로만.
    """
    scores = big_five.get("scores") if isinstance(big_five, dict) else None
    if not isinstance(scores, dict):
        return []
    traits: list[str] = []
    for code in ("O", "C", "E", "A"):
        v = scores.get(code)
        if not isinstance(v, (int, float)) or isinstance(v, bool):
            continue
        if v >= 50 + TRAIT_MARGIN:
            traits.append(_BIG_FIVE_TRAIT_DESC[code][0])
        elif v <= 50 - TRAIT_MARGIN:
            traits.append(_BIG_FIVE_TRAIT_DESC[code][1])
    n = scores.get("N")
    if isinstance(n, (int, float)) and not isinstance(n, bool):
        stability = 100 - n
        if stability >= 50 + TRAIT_MARGIN:
            traits.append(_STABILITY_DESC[0])
        elif stability <= 50 - TRAIT_MARGIN:
            traits.append(_STABILITY_DESC[1])
    return traits


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
        "personality_traits": big_five_traits(ctx.get("big_five")),
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
        # 사용자 캡을 SQL 에서 먼저 적용 — 대상이 많아도 페치가 캡된 집합만 스캔한다.
        uids = await self.repo.fetch_pending_user_ids(INSUFFICIENT_BADGE, limit)
        if not uids:
            return {"users": 0, "processed": 0, "failed": 0, "written": 0}
        sync_rows = await self.repo.fetch_unexplained_sync(uids, TOP_SYNC, INSUFFICIENT_BADGE)
        match_rows = await self.repo.fetch_unexplained_matches(uids, TOP_CHANCE)

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

        ctx_map = await self.repo.fetch_user_context(uids)
        ev_map = await self.repo.fetch_context_evidence(uids)

        processed = failed = written = 0
        for uid in uids:
            # 선별과 페치 사이의 경합(설명이 그새 채워짐 등)으로 항목이 비면 건너뛴다.
            items = by_user.get(uid)
            if items is None:
                continue
            try:
                user_context = _build_user_context(ctx_map.get(uid), ev_map.get(uid, []))
                result = await self._explainer(user_context, items["sync"], items["chance"])
                # 파서가 입력에 있던 slug/id 만 돌려주므로 원본 항목 조회는 항상 성공한다.
                sync_by_slug = {i["sector_slug"]: i for i in items["sync"]}
                chance_by_id = {i["opportunity_id"]: i for i in items["chance"]}
                user_written = 0
                for it in result.get("sync", []):
                    src = sync_by_slug[it["sector_slug"]]
                    user_written += await self.repo.update_sync_explanation(
                        uid, it["sector_slug"], it["text"], src["score"], src["badge"]
                    )
                for it in result.get("chance", []):
                    src = chance_by_id[it["opportunity_id"]]
                    user_written += await self.repo.update_match_explanation(
                        uid, it["opportunity_id"], it["text"],
                        src["match_score"], src["match_reason"],
                    )
                await self.session.commit()
                # rollback 된 건이 통계에 남지 않도록 커밋 성공 후에만 합산.
                written += user_written
                processed += 1
            except Exception as e:
                await self.session.rollback()
                logger.warning(f"추천 설명 생성 실패(user {uid}): {e}")
                failed += 1
        return {"users": len(uids), "processed": processed, "failed": failed, "written": written}
