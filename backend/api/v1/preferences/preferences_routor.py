# 성향·선호(disposition) HTTP 라우터 — user_intelligence 선택 입력 수집

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from core.api_guards import get_authenticated_user_id
from core.database import get_db
from domain.user_intelligence.hub.services.preference_service import PreferenceService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/preferences", tags=["preferences"])


class PreferenceUpsertRequest(BaseModel):
    workStyle: str | None = None
    companySizePref: str | None = None
    workTypePref: str | None = None
    workValues: list[str] = Field(default_factory=list)


@router.get("")
async def get_preferences(
    user_id: str = Depends(get_authenticated_user_id),
    db: AsyncSession = Depends(get_db),
):
    """현재 사용자 성향·선호 — 없으면 빈 기본값."""
    try:
        preferences = await PreferenceService(db).get_preferences(user_id)
        return {"success": True, "preferences": preferences}
    except Exception as e:
        logger.error(f"성향 조회 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"성향 조회 실패: {str(e)}")


@router.put("")
async def upsert_preferences(
    request: PreferenceUpsertRequest,
    user_id: str = Depends(get_authenticated_user_id),
    db: AsyncSession = Depends(get_db),
):
    """성향·선호 upsert — 폼 저장(전부 선택)."""
    try:
        preferences = await PreferenceService(db).upsert_preferences(
            user_id,
            work_style=request.workStyle,
            company_size_pref=request.companySizePref,
            work_type_pref=request.workTypePref,
            work_values=request.workValues or [],
        )
        return {"success": True, "preferences": preferences}
    except Exception as e:
        logger.error(f"성향 저장 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"성향 저장 실패: {str(e)}")
