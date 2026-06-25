# Market Insight(Pulse 등) HTTP 라우터 — Gold 서빙 + 정제 트리거

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from domain.market_insight.hub.repositories.gap_repository import GapRepository
from domain.market_insight.hub.repositories.pulse_repository import PulseRepository
from domain.market_insight.hub.services.gap_refine_service import GapRefineService
from domain.market_insight.hub.services.pulse_refine_service import PulseRefineService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/insight", tags=["insight"])

_BASELINE_METHODS = ("zscore", "pct_change", "ma_ratio")


@router.get("/pulse")
async def get_pulse(db: AsyncSession = Depends(get_db)):
    """Pulse 탭 서빙 — 섹터별 최신 트렌드 점수(Gold pulse_metrics_log)."""
    try:
        repo = PulseRepository(db)
        sectors = await repo.fetch_latest_gold()
        return {"success": True, "sectors": sectors, "count": len(sectors)}
    except Exception as e:
        logger.error(f"Pulse 조회 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Pulse 조회 실패: {str(e)}")


@router.post("/pulse/refine")
async def refine_pulse(
    window_days: int = Query(default=20, ge=2, le=365, description="모멘텀 윈도우(일)"),
    baseline_method: str = Query(default="zscore", description="zscore|pct_change|ma_ratio"),
    db: AsyncSession = Depends(get_db),
):
    """Pulse 정제·서빙 수동 트리거 — raw 혁신신호 → Silver → Gold 재생성."""
    if baseline_method not in _BASELINE_METHODS:
        raise HTTPException(
            status_code=400,
            detail=f"baseline_method must be one of {_BASELINE_METHODS}",
        )
    try:
        service = PulseRefineService(db)
        result = await service.refine_and_serve(
            window_days=window_days, baseline_method=baseline_method
        )
        return {"success": True, **result}
    except Exception as e:
        logger.error(f"Pulse 정제 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Pulse 정제 실패: {str(e)}")


@router.get("/gap")
async def get_gap(
    sector: str | None = Query(default=None, description="섹터 슬러그 필터"),
    db: AsyncSession = Depends(get_db),
):
    """Gap 탭 서빙 — 활성 이슈 카드 목록(Gold gap_issues)."""
    try:
        issues = await GapRepository(db).fetch_issues(sector)
        return {"success": True, "issues": issues, "count": len(issues)}
    except Exception as e:
        logger.error(f"Gap 조회 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Gap 조회 실패: {str(e)}")


@router.get("/gap/{issue_id}")
async def get_gap_detail(issue_id: int, db: AsyncSession = Depends(get_db)):
    """Gap 이슈 상세 — 문제·기회·이해관계자·액션 + 근거(issue_evidences)."""
    try:
        detail = await GapRepository(db).fetch_issue_detail(issue_id)
        if detail is None:
            raise HTTPException(status_code=404, detail="이슈를 찾을 수 없습니다.")
        return {"success": True, "issue": detail}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Gap 상세 조회 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Gap 상세 조회 실패: {str(e)}")


@router.post("/gap/refine")
async def refine_gap(db: AsyncSession = Depends(get_db)):
    """Gap 정제·서빙 수동 트리거 — discourse → Silver → Gold 재생성."""
    try:
        result = await GapRefineService(db).refine_and_serve()
        return {"success": True, **result}
    except Exception as e:
        logger.error(f"Gap 정제 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Gap 정제 실패: {str(e)}")
