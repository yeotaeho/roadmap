import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from domain.auth.hub.security.services.jwt import JWTService
from domain.auth.hub.services.auth_profile_service import AuthProfileService
from domain.auth.hub.services.user_service import UserService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/user", tags=["user"])


class SyncProfileUpsertRequest(BaseModel):
    targetJob: Optional[str] = None
    interestKeywords: List[str] = Field(default_factory=list)


async def get_user_services(db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    return {
        "user_service": UserService(db),
        "auth_profile_service": AuthProfileService(db),
        "jwt_service": JWTService(),
        "db": db,
    }


async def get_current_user_id(
    authorization: Optional[str] = Header(None),
    services: Dict[str, Any] = Depends(get_user_services),
) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="인증 토큰이 없습니다.")
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="잘못된 인증 토큰 형식입니다.")

    token = authorization[7:]
    jwt_service: JWTService = services["jwt_service"]
    user_id = jwt_service.extract_user_id(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="유효하지 않은 토큰입니다.")
    if jwt_service.is_token_expired(token):
        raise HTTPException(status_code=401, detail="토큰이 만료되었습니다.")
    return user_id


@router.get("/me")
async def get_current_user(
    user_id: str = Depends(get_current_user_id),
    services: Dict[str, Any] = Depends(get_user_services),
):
    user_service: UserService = services["user_service"]
    user = await user_service.find_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")

    return {
        "id": str(user.id),
        "email": user.email,
        "nickname": user.nickname,
        "profileImage": user.profile_image_url,
        "provider": user.auth_provider,
        "isActive": user.is_active,
    }


@router.put("/me")
async def update_current_user(
    name: Optional[str] = None,
    profileImage: Optional[str] = None,
    user_id: str = Depends(get_current_user_id),
    services: Dict[str, Any] = Depends(get_user_services),
):
    auth_profile_service: AuthProfileService = services["auth_profile_service"]
    try:
        updated_user = await auth_profile_service.update_basic_profile(
            user_id,
            nickname=name,
            profile_image_url=profileImage,
        )
    except ValueError:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
    return {
        "id": str(updated_user.id),
        "email": updated_user.email,
        "nickname": updated_user.nickname,
        "profileImage": updated_user.profile_image_url,
        "provider": updated_user.auth_provider,
        "isActive": updated_user.is_active,
    }


@router.get("/sync-profile")
async def get_sync_profile(
    user_id: str = Depends(get_current_user_id),
    services: Dict[str, Any] = Depends(get_user_services),
):
    auth_profile_service: AuthProfileService = services["auth_profile_service"]
    profile = await auth_profile_service.get_sync_profile(user_id)
    if not profile:
        return {"userId": user_id, "targetJob": None, "interestKeywords": []}
    return {
        "userId": str(profile.user_id),
        "targetJob": profile.target_job,
        "interestKeywords": profile.interest_keywords or [],
    }


@router.put("/sync-profile")
async def upsert_sync_profile(
    request: SyncProfileUpsertRequest,
    user_id: str = Depends(get_current_user_id),
    services: Dict[str, Any] = Depends(get_user_services),
):
    auth_profile_service: AuthProfileService = services["auth_profile_service"]
    profile = await auth_profile_service.upsert_sync_profile(
        user_id,
        target_job=request.targetJob,
        interest_keywords=request.interestKeywords or [],
    )

    return {
        "userId": str(profile.user_id),
        "targetJob": profile.target_job,
        "interestKeywords": profile.interest_keywords or [],
    }
