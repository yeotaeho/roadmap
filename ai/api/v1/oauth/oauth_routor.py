from fastapi import APIRouter, HTTPException, Depends, Request, Response, Cookie, Path
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any
import httpx
import redis.asyncio as redis
import logging
from sqlalchemy.ext.asyncio import AsyncSession

# Domain imports
from domain.oauth.config.settings import settings
from domain.oauth.config.database import get_db
from domain.oauth.service.google_oauth_service import GoogleOAuthService
from domain.oauth.service.kakao_oauth_service import KakaoOAuthService
from domain.oauth.service.naver_oauth_service import NaverOAuthService
from domain.oauth.service.user_service import UserService
from domain.oauth.service.refresh_token_service import RefreshTokenService
from domain.oauth.util.jwt import JWTService
from domain.oauth.util.signup_token import SignupTokenService
from domain.oauth.util.state import OAuthStateService
from domain.oauth.util.pkce import PKCEService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/oauth", tags=["oauth"])

# Request Models
class OAuthCallbackRequest(BaseModel):
    code: str
    state: str


class SignupRequest(BaseModel):
    signupToken: str


# Dependency: Redis Client
async def get_redis_client() -> redis.Redis:
    """Redis 클라이언트 생성"""
    return redis.Redis(
        host=settings.redis_host,
        port=settings.redis_port,
        password=settings.redis_password,
        ssl=settings.redis_ssl_enabled,
        decode_responses=False
    )


# Dependency: HTTP Client
async def get_http_client() -> httpx.AsyncClient:
    """HTTP 클라이언트 생성"""
    return httpx.AsyncClient(timeout=30.0)


# Dependency: Services
async def get_services(
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis_client),
    http_client: httpx.AsyncClient = Depends(get_http_client)
) -> Dict[str, Any]:
    """모든 서비스 의존성 주입"""
    state_service = OAuthStateService(redis_client)
    pkce_service = PKCEService(redis_client)
    jwt_service = JWTService()
    signup_token_service = SignupTokenService()
    refresh_token_service = RefreshTokenService(redis_client)
    user_service = UserService(db)
    
    google_service = GoogleOAuthService(state_service, pkce_service, http_client)
    kakao_service = KakaoOAuthService(state_service, pkce_service, http_client)
    naver_service = NaverOAuthService(state_service, http_client)
    
    return {
        "google_service": google_service,
        "kakao_service": kakao_service,
        "naver_service": naver_service,
        "user_service": user_service,
        "refresh_token_service": refresh_token_service,
        "jwt_service": jwt_service,
        "signup_token_service": signup_token_service
    }


def create_refresh_token_cookie(refresh_token: str) -> str:
    """리프레시 토큰 쿠키 생성"""
    return (
        f"refreshToken={refresh_token}; "
        f"HttpOnly; "
        f"Secure; "
        f"SameSite=None; "
        f"Path=/; "
        f"Max-Age={settings.jwt_refresh_expiration // 1000}"
    )


def create_delete_refresh_token_cookie() -> str:
    """리프레시 토큰 쿠키 삭제"""
    return "refreshToken=; HttpOnly; Secure; SameSite=None; Path=/; Max-Age=0"


# ========== Google OAuth ==========
@router.get("/google/login")
async def get_google_login_url(services: Dict[str, Any] = Depends(get_services)):
    """구글 로그인 URL 요청 (State 및 PKCE 포함)"""
    logger.info("구글 로그인 URL 요청")
    
    google_service = services["google_service"]
    auth_data = await google_service.get_authorization_url()
    
    return {
        "authUrl": auth_data["authUrl"],
        "state": auth_data["state"],
        "message": "구글 로그인 페이지로 이동하세요"
    }


@router.post("/google/callback")
async def google_callback(
    request: OAuthCallbackRequest,
    response: Response,
    services: Dict[str, Any] = Depends(get_services)
):
    """구글 로그인 콜백 처리"""
    logger.info(f"구글 로그인 콜백 처리 시작: code={request.code}, state={request.state}")
    
    try:
        if not request.state:
            raise HTTPException(status_code=400, detail="State 파라미터가 누락되었습니다.")
        
        google_service = services["google_service"]
        user_service = services["user_service"]
        jwt_service = services["jwt_service"]
        refresh_token_service = services["refresh_token_service"]
        signup_token_service = services["signup_token_service"]
        
        # OAuth 플로우 실행
        user_info = await google_service.process_oauth(request.code, request.state)
        
        # 사용자 정보 추출
        provider_id = user_info.get("id")
        email = user_info.get("email")
        name = user_info.get("name")
        profile_image = user_info.get("picture")
        
        # 사용자 조회 (생성하지 않음)
        existing_user = await user_service.find_user("google", provider_id)
        
        if not existing_user:
            # 신규 사용자 - 회원가입 필요
            signup_token = signup_token_service.generate_signup_token(
                "google", provider_id, email, name, None, profile_image
            )
            
            logger.info(f"신규 사용자 감지 (회원가입 토큰 발급): provider=google, providerId={provider_id}")
            return {
                "success": False,
                "isNewUser": True,
                "message": "회원가입이 필요합니다.",
                "signupToken": signup_token
            }
        
        # 기존 사용자 - 로그인 처리
        user = existing_user
        user.email = email
        user.name = name
        user.profile_image = profile_image
        user = await user_service.save(user)
        
        # JWT 토큰 생성
        access_token = jwt_service.generate_token(user.id, "google", email, name)
        refresh_token = jwt_service.generate_refresh_token(user.id, "google", email, name)
        
        # 리프레시 토큰 저장
        await refresh_token_service.save_refresh_token(user.id, refresh_token)
        
        # 쿠키 설정
        response.set_cookie(
            key="refreshToken",
            value=refresh_token,
            httponly=True,
            secure=True,
            samesite="none",
            path="/",
            max_age=settings.jwt_refresh_expiration // 1000
        )
        
        logger.info(f"구글 로그인 성공: userId={user.id}, googleId={provider_id}")
        return {
            "success": True,
            "isNewUser": False,
            "message": "구글 로그인 성공",
            "userId": user.id,
            "googleId": provider_id,
            "email": email,
            "name": name,
            "profileImage": profile_image,
            "accessToken": access_token,
            "tokenType": "Bearer"
        }
        
    except Exception as e:
        logger.error(f"구글 로그인 실패: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"구글 로그인 실패: {str(e)}"
        )


# ========== Kakao OAuth ==========
@router.get("/kakao/login")
async def get_kakao_login_url(services: Dict[str, Any] = Depends(get_services)):
    """카카오 로그인 URL 요청 (State 및 PKCE 포함)"""
    logger.info("카카오 로그인 URL 요청")
    
    kakao_service = services["kakao_service"]
    auth_data = await kakao_service.get_authorization_url()
    
    return {
        "authUrl": auth_data["authUrl"],
        "state": auth_data["state"],
        "message": "카카오 로그인 페이지로 이동하세요"
    }


@router.post("/kakao/callback")
async def kakao_callback(
    request: OAuthCallbackRequest,
    response: Response,
    services: Dict[str, Any] = Depends(get_services)
):
    """카카오 로그인 콜백 처리"""
    logger.info(f"카카오 로그인 콜백 처리 시작: code={request.code}, state={request.state}")
    
    try:
        if not request.state:
            raise HTTPException(status_code=400, detail="State 파라미터가 누락되었습니다.")
        
        kakao_service = services["kakao_service"]
        user_service = services["user_service"]
        jwt_service = services["jwt_service"]
        refresh_token_service = services["refresh_token_service"]
        signup_token_service = services["signup_token_service"]
        
        # OAuth 플로우 실행
        user_info = await kakao_service.process_oauth(request.code, request.state)
        
        # 사용자 정보 추출
        provider_id = str(user_info.get("id"))
        kakao_account = user_info.get("kakao_account", {})
        email = kakao_account.get("email")
        profile = kakao_account.get("profile", {})
        nickname = profile.get("nickname")
        profile_image = profile.get("profile_image_url")
        
        # 사용자 조회 (생성하지 않음)
        existing_user = await user_service.find_user("kakao", provider_id)
        
        if not existing_user:
            # 신규 사용자 - 회원가입 필요
            signup_token = signup_token_service.generate_signup_token(
                "kakao", provider_id, email, None, nickname, profile_image
            )
            
            logger.info(f"신규 사용자 감지 (회원가입 토큰 발급): provider=kakao, providerId={provider_id}")
            return {
                "success": False,
                "isNewUser": True,
                "message": "회원가입이 필요합니다.",
                "signupToken": signup_token
            }
        
        # 기존 사용자 - 로그인 처리
        user = existing_user
        user.email = email
        user.nickname = nickname
        user.profile_image = profile_image
        user = await user_service.save(user)
        
        # JWT 토큰 생성
        access_token = jwt_service.generate_token(user.id, "kakao", email, user.name)
        refresh_token = jwt_service.generate_refresh_token(user.id, "kakao", email, user.name)
        
        # 리프레시 토큰 저장
        await refresh_token_service.save_refresh_token(user.id, refresh_token)
        
        # 쿠키 설정
        response.set_cookie(
            key="refreshToken",
            value=refresh_token,
            httponly=True,
            secure=True,
            samesite="none",
            path="/",
            max_age=settings.jwt_refresh_expiration // 1000
        )
        
        logger.info(f"카카오 로그인 성공: userId={user.id}, kakaoId={provider_id}")
        return {
            "success": True,
            "isNewUser": False,
            "message": "카카오 로그인 성공",
            "userId": user.id,
            "kakaoId": provider_id,
            "email": email,
            "nickname": nickname,
            "profileImage": profile_image,
            "accessToken": access_token,
            "tokenType": "Bearer"
        }
        
    except Exception as e:
        logger.error(f"카카오 로그인 실패: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"카카오 로그인 실패: {str(e)}"
        )


# ========== Naver OAuth ==========
@router.get("/naver/login")
async def get_naver_login_url(services: Dict[str, Any] = Depends(get_services)):
    """네이버 로그인 URL 요청 (State 검증 지원)"""
    logger.info("네이버 로그인 URL 요청")
    
    naver_service = services["naver_service"]
    auth_data = await naver_service.get_authorization_url()
    
    return {
        "authUrl": auth_data["authUrl"],
        "state": auth_data["state"],
        "message": "네이버 로그인 페이지로 이동하세요"
    }


@router.post("/naver/callback")
async def naver_callback(
    request: OAuthCallbackRequest,
    response: Response,
    services: Dict[str, Any] = Depends(get_services)
):
    """네이버 로그인 콜백 처리"""
    logger.info(f"네이버 로그인 콜백 처리 시작: code={request.code}, state={request.state}")
    
    try:
        if not request.state:
            raise HTTPException(status_code=400, detail="State 파라미터가 누락되었습니다.")
        
        naver_service = services["naver_service"]
        user_service = services["user_service"]
        jwt_service = services["jwt_service"]
        refresh_token_service = services["refresh_token_service"]
        signup_token_service = services["signup_token_service"]
        
        # OAuth 플로우 실행
        user_info = await naver_service.process_oauth(request.code, request.state)
        
        # 사용자 정보 추출
        response_data = user_info.get("response", {})
        provider_id = response_data.get("id")
        email = response_data.get("email")
        name = response_data.get("name")
        nickname = response_data.get("nickname")
        profile_image = response_data.get("profile_image")
        
        # 사용자 조회 (생성하지 않음)
        existing_user = await user_service.find_user("naver", provider_id)
        
        if not existing_user:
            # 신규 사용자 - 회원가입 필요
            signup_token = signup_token_service.generate_signup_token(
                "naver", provider_id, email, name, nickname, profile_image
            )
            
            logger.info(f"신규 사용자 감지 (회원가입 토큰 발급): provider=naver, providerId={provider_id}")
            return {
                "success": False,
                "isNewUser": True,
                "message": "회원가입이 필요합니다.",
                "signupToken": signup_token
            }
        
        # 기존 사용자 - 로그인 처리
        user = existing_user
        user.email = email
        user.name = name
        user.nickname = nickname
        user.profile_image = profile_image
        user = await user_service.save(user)
        
        # JWT 토큰 생성
        access_token = jwt_service.generate_token(user.id, "naver", email, name)
        refresh_token = jwt_service.generate_refresh_token(user.id, "naver", email, name)
        
        # 리프레시 토큰 저장
        await refresh_token_service.save_refresh_token(user.id, refresh_token)
        
        # 쿠키 설정
        response.set_cookie(
            key="refreshToken",
            value=refresh_token,
            httponly=True,
            secure=True,
            samesite="none",
            path="/",
            max_age=settings.jwt_refresh_expiration // 1000
        )
        
        logger.info(f"네이버 로그인 성공: userId={user.id}, naverId={provider_id}")
        return {
            "success": True,
            "isNewUser": False,
            "message": "네이버 로그인 성공",
            "userId": user.id,
            "naverId": provider_id,
            "email": email,
            "nickname": nickname,
            "name": name,
            "profileImage": profile_image,
            "accessToken": access_token,
            "tokenType": "Bearer"
        }
        
    except Exception as e:
        logger.error(f"네이버 로그인 실패: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"네이버 로그인 실패: {str(e)}"
        )


# ========== Signup ==========
@router.post("/signup")
async def oauth_signup(
    request: SignupRequest,
    response: Response,
    services: Dict[str, Any] = Depends(get_services)
):
    """OAuth 회원가입 처리 (토큰 기반)"""
    logger.info(f"OAuth 회원가입 처리 시작: signupToken={'있음' if request.signupToken else '없음'}")
    
    try:
        if not request.signupToken:
            raise HTTPException(status_code=400, detail="회원가입 토큰이 누락되었습니다.")
        
        signup_token_service = services["signup_token_service"]
        user_service = services["user_service"]
        jwt_service = services["jwt_service"]
        refresh_token_service = services["refresh_token_service"]
        
        # 회원가입 토큰 검증
        claims = signup_token_service.validate_signup_token(request.signupToken)
        if not claims:
            raise HTTPException(status_code=401, detail="유효하지 않거나 만료된 회원가입 토큰입니다.")
        
        # OAuth 정보 추출
        oauth_info = signup_token_service.extract_oauth_info(claims)
        provider = oauth_info["provider"]
        provider_id = oauth_info["providerId"]
        email = oauth_info["email"]
        name = oauth_info["name"]
        nickname = oauth_info["nickname"]
        profile_image = oauth_info["profileImage"]
        
        logger.info(f"OAuth 정보 추출 완료: provider={provider}, providerId={provider_id}")
        
        # 사용자 조회 (이미 존재하는지 확인)
        existing_user = await user_service.find_user(provider, provider_id)
        
        if existing_user:
            # 이미 존재하는 사용자 - 정보 업데이트 후 로그인 처리
            user = existing_user
            user.email = email
            user.name = name
            user.nickname = nickname
            user.profile_image = profile_image
            user = await user_service.save(user)
            logger.info(f"기존 사용자 정보 업데이트 및 로그인: provider={provider}, providerId={provider_id}, userId={user.id}")
        else:
            # 신규 사용자 생성
            user = await user_service.find_or_create_user(
                provider=provider,
                provider_id=provider_id,
                email=email,
                name=name,
                nickname=nickname,
                profile_image=profile_image
            )
            logger.info(f"신규 사용자 생성: provider={provider}, providerId={provider_id}, userId={user.id}")
        
        # JWT 토큰 생성
        access_token = jwt_service.generate_token(user.id, provider, email, name)
        refresh_token = jwt_service.generate_refresh_token(user.id, provider, email, name)
        
        # 리프레시 토큰 저장
        await refresh_token_service.save_refresh_token(user.id, refresh_token)
        
        # 쿠키 설정
        response.set_cookie(
            key="refreshToken",
            value=refresh_token,
            httponly=True,
            secure=True,
            samesite="none",
            path="/",
            max_age=settings.jwt_refresh_expiration // 1000
        )
        
        logger.info(f"OAuth 회원가입 성공: userId={user.id}, provider={provider}, providerId={provider_id}")
        return {
            "success": True,
            "message": "회원가입 성공",
            "userId": user.id,
            "email": email,
            "name": name,
            "nickname": nickname,
            "profileImage": profile_image,
            "accessToken": access_token,
            "tokenType": "Bearer"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"OAuth 회원가입 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"회원가입 실패: {str(e)}")


# ========== Refresh Token ==========
@router.post("/refresh")
async def refresh_token(
    refreshToken: Optional[str] = Cookie(None),
    authorization: Optional[str] = None,
    services: Dict[str, Any] = Depends(get_services)
):
    """리프레시 토큰으로 새 액세스 토큰 발급"""
    if not refreshToken:
        # Authorization 헤더에서도 시도
        if authorization and authorization.startswith("Bearer "):
            refreshToken = authorization[7:]
        else:
            raise HTTPException(status_code=401, detail="리프레시 토큰이 없습니다.")
    
    try:
        jwt_service = services["jwt_service"]
        refresh_token_service = services["refresh_token_service"]
        user_service = services["user_service"]
        
        # JWT 토큰 검증
        payload = jwt_service.decode_token(refreshToken)
        if not payload:
            raise HTTPException(status_code=401, detail="유효하지 않은 리프레시 토큰입니다.")
        
        # 토큰 타입 확인
        token_type = payload.get("type")
        if token_type != "refresh":
            raise HTTPException(status_code=401, detail="유효하지 않은 리프레시 토큰입니다.")
        
        # 토큰 만료 확인
        if jwt_service.is_token_expired(refreshToken):
            await refresh_token_service.delete_refresh_token(refreshToken)
            raise HTTPException(status_code=401, detail="리프레시 토큰이 만료되었습니다.")
        
        user_id = payload.get("userId")
        email = payload.get("email")
        provider = payload.get("provider")
        
        # Redis에서 토큰 검증
        redis_user_id = await refresh_token_service.validate_refresh_token(refreshToken)
        if not redis_user_id:
            raise HTTPException(status_code=401, detail="리프레시 토큰이 무효화되었습니다.")
        
        # 사용자 ID 일치 확인
        if redis_user_id != user_id:
            raise HTTPException(status_code=401, detail="리프레시 토큰이 유효하지 않습니다.")
        
        # 사용자 정보 조회 (name 추출)
        user = await user_service.find_by_id(user_id)
        name = user.name if user else None
        
        # 새 토큰 생성 및 로테이션
        new_access_token = jwt_service.generate_token(user_id, provider, email, name)
        new_refresh_token = jwt_service.generate_refresh_token(user_id, provider, email, name)
        await refresh_token_service.rotate_refresh_token(user_id, refreshToken, new_refresh_token)
        
        logger.info(f"토큰 갱신 성공: userId={user_id}")
        
        response = JSONResponse({
            "success": True,
            "accessToken": new_access_token,
            "tokenType": "Bearer"
        })
        
        # 새 리프레시 토큰 쿠키 설정
        response.set_cookie(
            key="refreshToken",
            value=new_refresh_token,
            httponly=True,
            secure=True,
            samesite="none",
            path="/",
            max_age=settings.jwt_refresh_expiration // 1000
        )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"리프레시 토큰 처리 중 오류 발생: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="토큰 갱신 중 오류가 발생했습니다.")


# ========== Auth (Logout) ==========
@router.post("/logout")
async def logout(
    refreshToken: Optional[str] = Cookie(None),
    authorization: Optional[str] = None,
    services: Dict[str, Any] = Depends(get_services)
):
    """로그아웃"""
    try:
        jwt_service = services["jwt_service"]
        refresh_token_service = services["refresh_token_service"]
        
        user_id = None
        
        # 리프레시 토큰에서 사용자 ID 추출
        if refreshToken:
            user_id = await refresh_token_service.validate_refresh_token(refreshToken)
            if user_id:
                await refresh_token_service.delete_refresh_token(refreshToken)
                logger.info(f"리프레시 토큰 무효화 완료: userId={user_id}")
        
        # 액세스 토큰에서 사용자 ID 추출 (백업)
        if not user_id and authorization and authorization.startswith("Bearer "):
            access_token = authorization[7:]
            user_id = jwt_service.extract_user_id(access_token)
            logger.info(f"액세스 토큰에서 사용자 ID 추출: userId={user_id}")
        
        # 사용자 ID가 확인되면 모든 토큰 무효화
        if user_id:
            await refresh_token_service.invalidate_all_user_tokens(user_id)
            logger.info(f"사용자의 모든 리프레시 토큰 무효화 완료: userId={user_id}")
        
        response = JSONResponse({
            "success": True,
            "message": "로그아웃 성공"
        })
        
        # 쿠키 삭제
        response.set_cookie(
            key="refreshToken",
            value="",
            httponly=True,
            secure=True,
            samesite="none",
            path="/",
            max_age=0
        )
        
        return response
        
    except Exception as e:
        logger.error(f"로그아웃 처리 중 오류 발생: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="로그아웃 처리 중 오류가 발생했습니다.")


@router.post("/force-logout/{user_id}")
async def force_logout(
    user_id: int = Path(..., description="무효화할 사용자 ID"),
    services: Dict[str, Any] = Depends(get_services)
):
    """강제 로그아웃 (관리자 또는 해킹 위험 감지 시)"""
    try:
        refresh_token_service = services["refresh_token_service"]
        
        # 사용자의 모든 토큰 무효화
        await refresh_token_service.invalidate_all_user_tokens(user_id)
        logger.warn(f"강제 로그아웃 실행: userId={user_id}")
        
        return {
            "success": True,
            "message": "사용자의 모든 토큰이 무효화되었습니다.",
            "userId": user_id
        }
        
    except Exception as e:
        logger.error(f"강제 로그아웃 처리 중 오류 발생: userId={user_id}, error={e}", exc_info=True)
        raise HTTPException(status_code=500, detail="강제 로그아웃 처리 중 오류가 발생했습니다.")

