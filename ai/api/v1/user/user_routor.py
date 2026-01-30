from fastapi import APIRouter, HTTPException, Depends, Header
from typing import Optional, Dict, Any
import logging
from sqlalchemy.ext.asyncio import AsyncSession

# Domain imports
from domain.oauth.config.database import get_db
from domain.oauth.service.user_service import UserService
from domain.oauth.util.jwt import JWTService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/user", tags=["user"])


# Dependency: Services
async def get_user_services(
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """사용자 서비스 의존성 주입"""
    user_service = UserService(db)
    jwt_service = JWTService()
    
    return {
        "user_service": user_service,
        "jwt_service": jwt_service
    }


# Dependency: Current User (JWT 토큰에서 사용자 ID 추출)
async def get_current_user_id(
    authorization: Optional[str] = Header(None),
    services: Dict[str, Any] = Depends(get_user_services)
) -> int:
    """JWT 토큰에서 사용자 ID 추출"""
    if not authorization:
        raise HTTPException(status_code=401, detail="인증 토큰이 없습니다.")
    
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="잘못된 인증 토큰 형식입니다.")
    
    token = authorization[7:]  # "Bearer " 제거
    jwt_service = services["jwt_service"]
    
    # 토큰 검증 및 사용자 ID 추출
    user_id = jwt_service.extract_user_id(token)
    
    if not user_id:
        raise HTTPException(status_code=401, detail="유효하지 않은 토큰입니다.")
    
    # 토큰 만료 확인
    if jwt_service.is_token_expired(token):
        raise HTTPException(status_code=401, detail="토큰이 만료되었습니다.")
    
    return user_id


# ========== User Info ==========
@router.get("/me")
async def get_current_user(
    user_id: int = Depends(get_current_user_id),
    services: Dict[str, Any] = Depends(get_user_services)
):
    """현재 로그인한 사용자 정보 조회"""
    try:
        user_service = services["user_service"]
        
        # 사용자 정보 조회
        user = await user_service.find_by_id(user_id)
        
        if not user:
            raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
        
        logger.info(f"사용자 정보 조회 성공: userId={user_id}")
        
        return {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "nickname": user.nickname,
            "profileImage": user.profile_image,
            "provider": user.provider
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"사용자 정보 조회 실패: userId={user_id}, error={e}", exc_info=True)
        raise HTTPException(status_code=500, detail="사용자 정보 조회 중 오류가 발생했습니다.")


@router.put("/me")
async def update_current_user(
    name: Optional[str] = None,
    profileImage: Optional[str] = None,
    user_id: int = Depends(get_current_user_id),
    services: Dict[str, Any] = Depends(get_user_services)
):
    """현재 로그인한 사용자 프로필 정보 업데이트"""
    try:
        user_service = services["user_service"]
        
        # 사용자 정보 조회
        user = await user_service.find_by_id(user_id)
        
        if not user:
            raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
        
        # 정보 업데이트
        if name is not None:
            user.name = name
        if profileImage is not None:
            user.profile_image = profileImage
        
        # 저장
        updated_user = await user_service.save(user)
        
        logger.info(f"사용자 정보 업데이트 성공: userId={user_id}")
        
        return {
            "id": updated_user.id,
            "name": updated_user.name,
            "email": updated_user.email,
            "nickname": updated_user.nickname,
            "profileImage": updated_user.profile_image,
            "provider": updated_user.provider
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"사용자 정보 업데이트 실패: userId={user_id}, error={e}", exc_info=True)
        raise HTTPException(status_code=500, detail="사용자 정보 업데이트 중 오류가 발생했습니다.")

