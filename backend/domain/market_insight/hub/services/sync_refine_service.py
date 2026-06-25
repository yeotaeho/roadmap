# Silver/Gold — 사용자 임베딩×섹터 트렌드로 적합도(Sync) 점수를 산출·서빙하는 서비스

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from domain.market_insight.hub.repositories.sync_repository import SyncRepository

PROMPT_VERSION = "v1"
# 적합도(affinity)·트렌드(trend) 융합 가중치.
AFFINITY_WEIGHT = 0.6
TREND_WEIGHT = 0.4


def minmax_normalize(values: list[float]) -> list[float]:
    """값들을 0~100으로 min-max 정규화한다. 전부 동일하면 50(중립). 순수 함수."""
    if not values:
        return []
    lo, hi = min(values), max(values)
    span = hi - lo
    if span == 0:
        return [50.0 for _ in values]
    return [(v - lo) / span * 100.0 for v in values]


def combine_score(affinity_norm: float, trend: float) -> int:
    """정규화 적합도(0~100)와 트렌드(0~100)를 가중 융합해 0~100 정수 점수로 만든다."""
    score = AFFINITY_WEIGHT * affinity_norm + TREND_WEIGHT * trend
    return int(max(0, min(100, round(score))))


def badge(score: int) -> str:
    """적합도 점수를 배지 라벨로 변환한다."""
    if score >= 70:
        return "강한 적합"
    if score >= 45:
        return "적합"
    return "약한 적합"


class SyncRefineService:
    """사용자×섹터 임베딩 코사인 적합도 + Pulse 트렌드 → refined_sync_inputs → sync_scores_daily."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = SyncRepository(session)

    async def refine_and_serve(self) -> dict:
        """모든 임베딩 보유 사용자×섹터 적합도를 재계산·적재한다. 멱등.

        반환: {"users", "scores"}.
        """
        affinity_rows = await self.repo.fetch_affinity()
        trend = await self.repo.fetch_trend()
        user_keywords = await self.repo.fetch_user_keywords()

        # user → [(sector, affinity)] 그룹핑.
        by_user: dict[object, list[tuple[str, float]]] = {}
        for r in affinity_rows:
            by_user.setdefault(r.user_id, []).append((r.sector_slug, float(r.affinity)))

        scores = 0
        for user_id, pairs in by_user.items():
            sectors = [p[0] for p in pairs]
            norm = minmax_normalize([p[1] for p in pairs])
            keywords = user_keywords.get(user_id, [])
            for sector_slug, aff_norm in zip(sectors, norm):
                trend_s = float(trend.get(sector_slug, 50))
                score = combine_score(aff_norm, trend_s)
                await self.repo.upsert_sync_input(
                    {
                        "user_id": user_id,
                        "sector_slug": sector_slug,
                        "affinity_score": round(aff_norm, 2),
                        "trend_score": round(trend_s, 2),
                        "keywords": keywords,
                        "model_name": "text-embedding-3-large",
                        "prompt_version": PROMPT_VERSION,
                    }
                )
                await self.repo.upsert_sync_gold(user_id, sector_slug, score, badge(score))
                scores += 1
        await self.session.commit()
        return {"users": len(by_user), "scores": scores}
