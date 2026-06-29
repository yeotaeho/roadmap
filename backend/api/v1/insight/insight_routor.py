# Market Insight(Pulse 등) HTTP 라우터 — Gold 서빙 + 정제 트리거

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from core.api_guards import require_internal_token
from core.database import get_db
from domain.market_insight.hub.repositories.briefing_repository import BriefingRepository
from domain.market_insight.hub.repositories.causal_chain_repository import CausalChainRepository
from domain.market_insight.hub.repositories.gap_repository import GapRepository
from domain.market_insight.hub.repositories.pulse_repository import PulseRepository
from domain.market_insight.hub.repositories.forecast_repository import ForecastRepository
from domain.market_insight.hub.repositories.signal_repository import SignalRepository
from domain.market_insight.hub.services.briefing_service import BriefingRefineService
from domain.market_insight.hub.services.causal_chain_service import CausalChainRefineService
from domain.market_insight.hub.services.gap_refine_service import GapRefineService
from domain.market_insight.hub.services.gap_projection_service import GapProjectionService
from domain.market_insight.hub.services.keyword_trends import assemble_keywords
from domain.market_insight.hub.services.pulse_refine_service import PulseRefineService
from domain.market_insight.hub.services.forecast_refine_service import (
    MarketForecastRefineService,
)

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


@router.post("/pulse/refine", dependencies=[Depends(require_internal_token)])
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


@router.get("/pulse/overview")
async def get_pulse_overview(
    heatmap_weeks: int = Query(default=8, ge=1, le=52, description="히트맵 주 수"),
    momentum_months: int = Query(default=12, ge=1, le=36, description="모멘텀 차트 월 수"),
    db: AsyncSession = Depends(get_db),
):
    """Pulse overview 서빙 — 속도계·모멘텀 시계열·섹터×시간 히트맵·관심 점유율."""
    try:
        data = await PulseRepository(db).fetch_overview(heatmap_weeks, momentum_months)
        return {"success": True, **data}
    except Exception as e:
        logger.error(f"Pulse overview 조회 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Pulse overview 조회 실패: {str(e)}")


@router.get("/pulse/{sector}/history")
async def get_pulse_history(
    sector: str,
    weeks: int = Query(default=26, ge=1, le=104, description="조회 주 범위"),
    db: AsyncSession = Depends(get_db),
):
    """단일 섹터 Pulse 시계열(드릴다운)."""
    try:
        data = await PulseRepository(db).fetch_history(sector, weeks)
        if data is None:
            raise HTTPException(status_code=404, detail="섹터를 찾을 수 없습니다.")
        return {"success": True, **data}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Pulse history 조회 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Pulse history 조회 실패: {str(e)}")


@router.get("/pulse/crossover")
async def get_pulse_crossover(
    months: int = Query(default=12, ge=1, le=36, description="시계열 월 수"),
    db: AsyncSession = Depends(get_db),
):
    """세대교체 — 전통 vs 신흥 섹터 월 score 시계열·교차점."""
    try:
        data = await PulseRepository(db).fetch_crossover(months)
        return {"success": True, **data}
    except Exception as e:
        logger.error(f"크로스오버 조회 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"크로스오버 조회 실패: {str(e)}")


@router.get("/forecast")
async def get_market_forecast(db: AsyncSession = Depends(get_db)):
    """시장 전망 탭 서빙 — 섹터별 최신 TimesFM 예측 점수(Gold market_forecast_log)."""
    try:
        forecasts = await ForecastRepository(db).fetch_latest_forecast()
        return {"success": True, "sectors": forecasts, "count": len(forecasts)}
    except Exception as e:
        logger.error(f"시장 전망 조회 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"시장 전망 조회 실패: {str(e)}")


@router.post("/forecast/refine", dependencies=[Depends(require_internal_token)])
async def refine_market_forecast(db: AsyncSession = Depends(get_db)):
    """시장 전망 정제·서빙 수동 트리거 — 티커 시계열 → TimesFM → Silver → Gold 재생성."""
    try:
        result = await MarketForecastRefineService(db).refine_and_serve()
        return {"success": True, **result}
    except Exception as e:
        logger.error(f"시장 전망 정제 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"시장 전망 정제 실패: {str(e)}")


@router.get("/keywords")
async def get_trending_keywords(
    window_days: int = Query(default=30, ge=1, le=365, description="집계 윈도우(일)"),
    cloud_limit: int = Query(default=30, ge=1, le=100, description="클라우드 키워드 수"),
    ticker_limit: int = Query(default=12, ge=1, le=50, description="티커 키워드 수"),
    sector: str | None = Query(default=None, description="섹터 슬러그 필터(기본 전체)"),
    db: AsyncSession = Depends(get_db),
):
    """트렌딩 키워드 서빙 — refined_innovation_signal 키워드 빈도 CLOUD·상승 델타 TICKER."""
    try:
        recent, prior = await SignalRepository(db).fetch_keyword_freqs(window_days, sector)
        data = assemble_keywords(recent, prior, cloud_limit=cloud_limit, ticker_limit=ticker_limit)
        return {"success": True, **data}
    except Exception as e:
        logger.error(f"트렌딩 키워드 조회 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"트렌딩 키워드 조회 실패: {str(e)}")


@router.get("/briefing")
async def get_briefing(db: AsyncSession = Depends(get_db)):
    """3줄 경제 브리핑 서빙 — 최신일 economic_briefings."""
    try:
        data = await BriefingRepository(db).fetch_latest()
        return {"success": True, **data}
    except Exception as e:
        logger.error(f"브리핑 조회 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"브리핑 조회 실패: {str(e)}")


@router.post("/briefing/refine", dependencies=[Depends(require_internal_token)])
async def refine_briefing(
    force: bool = Query(default=False, description="당일 존재해도 재생성"),
    db: AsyncSession = Depends(get_db),
):
    """브리핑 생성·서빙 수동 트리거 — 당일 경제 신호 → LLM/템플릿 3줄."""
    try:
        result = await BriefingRefineService(db).refine_and_serve(force=force)
        return {"success": True, **result}
    except Exception as e:
        logger.error(f"브리핑 정제 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"브리핑 정제 실패: {str(e)}")


@router.get("/causal-chains")
async def get_causal_chains(db: AsyncSession = Depends(get_db)):
    """인과사슬 서빙 — 섹터별 최신 거시→산업→청년기회 카드."""
    try:
        chains = await CausalChainRepository(db).fetch_chains()
        return {"success": True, "chains": chains, "count": len(chains)}
    except Exception as e:
        logger.error(f"인과사슬 조회 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"인과사슬 조회 실패: {str(e)}")


@router.post("/causal-chains/refine", dependencies=[Depends(require_internal_token)])
async def refine_causal_chains(db: AsyncSession = Depends(get_db)):
    """인과사슬 정제·서빙 수동 트리거 — 분류 economic → LLM → Silver → Gold."""
    try:
        result = await CausalChainRefineService(db).refine_and_serve()
        return {"success": True, **result}
    except Exception as e:
        logger.error(f"인과사슬 정제 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"인과사슬 정제 실패: {str(e)}")


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


@router.post("/gap/refine", dependencies=[Depends(require_internal_token)])
async def refine_gap(db: AsyncSession = Depends(get_db)):
    """Gap 정제·서빙 수동 트리거 — discourse → Silver → Gold 재생성."""
    try:
        result = await GapRefineService(db).refine_and_serve()
        projected = await GapProjectionService(db).project_and_serve()
        return {"success": True, **result, **projected}
    except Exception as e:
        logger.error(f"Gap 정제 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Gap 정제 실패: {str(e)}")


@router.post("/gap/project", dependencies=[Depends(require_internal_token)])
async def project_gap(db: AsyncSession = Depends(get_db)):
    """Gap Gold 재사영만 — youth_fit 임계 재튜닝 후 LLM 재실행 없이 Gold 재생성."""
    try:
        result = await GapProjectionService(db).project_and_serve()
        return {"success": True, **result}
    except Exception as e:
        logger.error(f"Gap 사영 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Gap 사영 실패: {str(e)}")
