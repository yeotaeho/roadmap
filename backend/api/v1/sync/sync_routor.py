# Sync(사용자×트렌드 적합도) HTTP 라우터 — Gold 서빙 + 정제 트리거

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from core.api_guards import require_internal_token
from core.database import get_db
from domain.market_insight.hub.repositories.sync_repository import SyncRepository
from domain.market_insight.hub.services.sync_refine_service import SyncRefineService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sync", tags=["sync"])


@router.get("/scores")
async def get_sync_scores(
    user_id: str = Query(..., description="사용자 UUID"),
    db: AsyncSession = Depends(get_db),
):
    """Sync 탭 서빙 — 사용자별 섹터 적합도 점수(내림차순)."""
    try:
        scores = await SyncRepository(db).fetch_scores(user_id)
        return {"success": True, "scores": scores, "count": len(scores)}
    except Exception as e:
        logger.error(f"Sync 조회 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Sync 조회 실패: {str(e)}")


@router.post("/refine", dependencies=[Depends(require_internal_token)])
async def refine_sync(db: AsyncSession = Depends(get_db)):
    """Sync 정제·서빙 수동 트리거 — 사용자 임베딩×섹터 트렌드 적합도 재계산."""
    try:
        result = await SyncRefineService(db).refine_and_serve()
        return {"success": True, **result}
    except Exception as e:
        logger.error(f"Sync 정제 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Sync 정제 실패: {str(e)}")
