# Silver/Gold — 사용자 임베딩×섹터 트렌드로 적합도(Sync) 점수를 산출·서빙하는 서비스

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from domain.market_insight.hub.repositories.sync_repository import SyncRepository

PROMPT_VERSION = "v2"
# 적합도(affinity)·트렌드(trend) 융합 가중치.
AFFINITY_WEIGHT = 0.6
TREND_WEIGHT = 0.4

# 코사인 적합도 → 0~100 매핑 전역 고정 앵커(휴리스틱, 실데이터로 튜닝 대상).
#   사용자별 min-max 스트레치를 쓰지 않으므로 빈약한 밴드가 "강한 적합"으로 위장되지 않는다.
AFFINITY_LO = 0.05
AFFINITY_HI = 0.45
# 섹터 간 코사인 스프레드가 이 값 미만이면 섹터가 사실상 구분되지 않음 → 데이터 부족 처리.
MIN_AFFINITY_SPREAD = 0.03
INSUFFICIENT_BADGE = "데이터 부족"
NEUTRAL_SCORE = 50


def scale_affinity(cosine: float) -> float:
    """원시 코사인을 전역 고정 기준으로 0~100 절대 스케일(사용자별 스트레치 없음). 순수 함수."""
    span = AFFINITY_HI - AFFINITY_LO
    if span <= 0:
        return float(NEUTRAL_SCORE)
    pct = (cosine - AFFINITY_LO) / span * 100.0
    return max(0.0, min(100.0, pct))


def has_sufficient_signal(cosines: list[float]) -> bool:
    """섹터 간 코사인 스프레드가 임계 이상일 때만 유의미한 적합 신호로 본다."""
    if len(cosines) < 2:
        return False
    return (max(cosines) - min(cosines)) >= MIN_AFFINITY_SPREAD


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
            cosines = [p[1] for p in pairs]
            sufficient = has_sufficient_signal(cosines)
            keywords = user_keywords.get(user_id, [])
            for sector_slug, cosine in pairs:
                trend_s = float(trend.get(sector_slug, 50))
                if sufficient:
                    score = combine_score(scale_affinity(cosine), trend_s)
                    badge_label = badge(score)
                else:
                    # 섹터가 구분되지 않으면 노이즈를 확신 배지로 포장하지 않고 중립 처리.
                    score = NEUTRAL_SCORE
                    badge_label = INSUFFICIENT_BADGE
                await self.repo.upsert_sync_input(
                    {
                        "user_id": user_id,
                        "sector_slug": sector_slug,
                        # 감사 가능하도록 원시 코사인을 보존(서빙엔 Gold score 사용).
                        "affinity_score": round(cosine, 2),
                        "trend_score": round(trend_s, 2),
                        "keywords": keywords,
                        "model_name": "text-embedding-3-large",
                        "prompt_version": PROMPT_VERSION,
                    }
                )
                await self.repo.upsert_sync_gold(user_id, sector_slug, score, badge_label)
                scores += 1
        await self.session.commit()
        return {"users": len(by_user), "scores": scores}
