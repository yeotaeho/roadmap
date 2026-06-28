# Roadmap(전략 로드맵) HTTP 라우터 — 여정 개요·성장 아카이브 서빙(목업 수직 슬라이스)

import logging
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from core.api_guards import get_authenticated_user_id, require_internal_token
from core.database import get_db
from domain.hrowth_journey.hub.services.archive_service import ArchiveService
from domain.hrowth_journey.hub.services.journey_service import JourneyService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/roadmap", tags=["roadmap"])


class GrowthLogUpsertRequest(BaseModel):
    completedQuestIds: list[str] = Field(default_factory=list)
    note: str = ""


def _parse_month(month: str | None) -> tuple[int, int]:
    """YYYY-MM → (year, month). 미지정 시 당월."""
    if not month:
        today = date.today()
        return today.year, today.month
    try:
        parts = month.split("-")
        return int(parts[0]), int(parts[1])
    except (ValueError, IndexError):
        raise HTTPException(status_code=400, detail="month 형식은 YYYY-MM 이어야 합니다.")


@router.get("/journey")
async def get_journey(
    user_id: str = Depends(get_authenticated_user_id),
    db: AsyncSession = Depends(get_db),
):
    """여정 개요 — 스킬 트라이앵글·키워드 브릿지 + 퀘스트 트리."""
    try:
        result = await JourneyService(db).get_journey(user_id)
        return {"success": True, **result}
    except Exception as e:
        logger.error(f"Roadmap 여정 조회 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Roadmap 여정 조회 실패: {str(e)}")


@router.get("/archive")
async def get_archive(
    month: str | None = Query(default=None, description="YYYY-MM (미지정 시 당월)"),
    user_id: str = Depends(get_authenticated_user_id),
    db: AsyncSession = Depends(get_db),
):
    """성장 아카이브 — 월별 일별 로그(달력 점 표시용)."""
    year, mon = _parse_month(month)
    try:
        result = await ArchiveService(db).get_month(user_id, year, mon)
        return {"success": True, **result}
    except Exception as e:
        logger.error(f"Roadmap 아카이브 조회 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Roadmap 아카이브 조회 실패: {str(e)}")


@router.put("/archive/{log_date}")
async def upsert_archive_day(
    log_date: str,
    request: GrowthLogUpsertRequest,
    user_id: str = Depends(get_authenticated_user_id),
    db: AsyncSession = Depends(get_db),
):
    """일별 로그 upsert — 달성 퀘스트·자유 기록 영속화."""
    try:
        parsed = datetime.strptime(log_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="날짜 형식은 YYYY-MM-DD 이어야 합니다.")
    try:
        result = await ArchiveService(db).upsert_day(
            user_id, parsed, request.completedQuestIds, request.note
        )
        return {"success": True, **result}
    except Exception as e:
        logger.error(f"Roadmap 아카이브 저장 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Roadmap 아카이브 저장 실패: {str(e)}")


@router.post("/refine", dependencies=[Depends(require_internal_token)])
async def refine_roadmap():
    """페르소나→로드맵 재생성 훅(향후 LLM RoadmapPlanner). 현재는 시드 스크립트로 대체."""
    return {
        "success": True,
        "detail": "목업 단계 — scripts/seed_roadmap_mock.py 로 시드합니다. LLM 생성은 미구현.",
    }
