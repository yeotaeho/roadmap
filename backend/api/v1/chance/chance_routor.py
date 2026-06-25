# Chance(공고·매칭) HTTP 라우터 — Gold 서빙 + 정제·매칭 트리거

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from domain.market_insight.hub.repositories.chance_repository import ChanceRepository
from domain.market_insight.hub.services.chance_match_service import ChanceMatchService
from domain.market_insight.hub.services.chance_refine_service import ChanceRefineService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chance", tags=["chance"])


@router.get("/opportunities")
async def list_opportunities(
    sector: str | None = Query(default=None, description="섹터 슬러그 필터"),
    db: AsyncSession = Depends(get_db),
):
    """Chance 탭 서빙 — 활성(마감 전) 공고 카드 목록."""
    try:
        items = await ChanceRepository(db).fetch_opportunities(sector)
        return {"success": True, "opportunities": items, "count": len(items)}
    except Exception as e:
        logger.error(f"Chance 조회 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Chance 조회 실패: {str(e)}")


@router.get("/opportunities/{opp_id}")
async def opportunity_detail(opp_id: int, db: AsyncSession = Depends(get_db)):
    """공고 상세 — 혜택·대상·자격·준비 액션."""
    try:
        detail = await ChanceRepository(db).fetch_opportunity_detail(opp_id)
        if detail is None:
            raise HTTPException(status_code=404, detail="공고를 찾을 수 없습니다.")
        return {"success": True, "opportunity": detail}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chance 상세 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Chance 상세 실패: {str(e)}")


@router.get("/matches")
async def user_matches(
    user_id: str = Query(..., description="사용자 UUID"),
    db: AsyncSession = Depends(get_db),
):
    """사용자별 공고 적합도 매칭(점수 내림차순)."""
    try:
        items = await ChanceRepository(db).fetch_matches(user_id)
        return {"success": True, "matches": items, "count": len(items)}
    except Exception as e:
        logger.error(f"Chance 매칭 조회 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Chance 매칭 조회 실패: {str(e)}")


@router.post("/refine")
async def refine_chance(db: AsyncSession = Depends(get_db)):
    """Chance 정제·서빙 수동 트리거 — opportunity → Silver → Gold."""
    try:
        result = await ChanceRefineService(db).refine_and_serve()
        return {"success": True, **result}
    except Exception as e:
        logger.error(f"Chance 정제 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Chance 정제 실패: {str(e)}")


@router.post("/match")
async def match_chance(db: AsyncSession = Depends(get_db)):
    """Chance 매칭 수동 트리거 — 프로필 사용자 × 활성 공고 재계산."""
    try:
        result = await ChanceMatchService(db).match_all()
        return {"success": True, **result}
    except Exception as e:
        logger.error(f"Chance 매칭 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Chance 매칭 실패: {str(e)}")
