from fastapi import APIRouter, HTTPException, Depends, Request, Response, Cookie, Path, Header
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any
import httpx
import redis.asyncio as redis
import logging
import json
import uuid
from sqlalchemy.ext.asyncio import AsyncSession

# Domain imports
from core.config.settings import settings
from core.database import get_db
from domain.auth.hub.services.google_oauth_service import GoogleOAuthService
from domain.auth.hub.services.kakao_oauth_service import KakaoOAuthService
from domain.auth.hub.services.naver_oauth_service import NaverOAuthService
from domain.auth.hub.services.user_service import UserService
from domain.auth.hub.services.refresh_token_service import RefreshTokenService
from domain.auth.hub.services.auth_profile_service import AuthProfileService
from domain.auth.hub.security.services.jwt import JWTService
from domain.auth.hub.security.services.signup_token import SignupTokenService
from domain.auth.spokes.infra.oauth.state import OAuthStateService
from domain.auth.spokes.infra.oauth.pkce import PKCEService
from domain.auth.models.bases.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/oauth", tags=["oauth"])
MOBILE_BRIDGE_PREFIX = "oauth:mobile:bridge:"
MOBILE_BRIDGE_TTL_SECONDS = 120

# Request Models
class OAuthCallbackRequest(BaseModel):
    code: str
    state: Optional[str] = None


class RefreshTokenRequest(BaseModel):
    refreshToken: Optional[str] = None


class MobileBridgeExchangeRequest(BaseModel):
    bridgeToken: str


class GoogleNativeLoginRequest(BaseModel):
    idToken: str
    deviceId: Optional[str] = None
    deviceName: Optional[str] = None


class KakaoNativeLoginRequest(BaseModel):
    accessToken: str
    deviceId: Optional[str] = None
    deviceName: Optional[str] = None


class NaverNativeLoginRequest(BaseModel):
    accessToken: str
    deviceId: Optional[str] = None
    deviceName: Optional[str] = None


class SignupRequest(BaseModel):
    signupToken: str
    age: Optional[int] = None


class UpdateProfileRequest(BaseModel):
    name: Optional[str] = None
    profileImage: Optional[str] = None


class UpdateSignupInfoRequest(BaseModel):
    userId: str
    age: Optional[int] = None
    interests: Optional[list] = None
    targetJob: Optional[str] = None
    interestKeywords: Optional[list[str]] = None


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
    auth_profile_service = AuthProfileService(db)
    
    google_service = GoogleOAuthService(state_service, pkce_service, http_client)
    kakao_service = KakaoOAuthService(state_service, pkce_service, http_client)
    naver_service = NaverOAuthService(state_service, http_client)
    
    return {
        "google_service": google_service,
        "kakao_service": kakao_service,
        "naver_service": naver_service,
        "user_service": user_service,
        "auth_profile_service": auth_profile_service,
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


async def generate_tokens_and_set_cookie(
    user: User,
    provider: str,
    email: str,
    name: Optional[str],
    jwt_service: JWTService,
    refresh_token_service: RefreshTokenService,
    response: Response,
    set_cookie: bool = True,
) -> Dict[str, str]:
    """JWT 토큰 생성 및 쿠키 설정 헬퍼 함수"""
    # JWT 토큰 생성
    access_token = jwt_service.generate_token(str(user.id), provider, email, name)
    refresh_token = jwt_service.generate_refresh_token(str(user.id), provider, email, name)
    
    # 리프레시 토큰 저장
    await refresh_token_service.save_refresh_token(str(user.id), refresh_token)
    
    # 쿠키 설정
    if set_cookie:
        response.set_cookie(
            key="refreshToken",
            value=refresh_token,
            httponly=True,
            secure=True,
            samesite="none",
            path="/",
            max_age=settings.jwt_refresh_expiration // 1000
        )
    
    return {
        "accessToken": access_token,
        "refreshToken": refresh_token
    }


async def _create_mobile_bridge_token(
    refresh_token_service: RefreshTokenService,
    payload: Dict[str, Any],
) -> str:
    bridge_token = str(uuid.uuid4())
    key = f"{MOBILE_BRIDGE_PREFIX}{bridge_token}"
    await refresh_token_service.redis.setex(
        key,
        MOBILE_BRIDGE_TTL_SECONDS,
        json.dumps(payload, ensure_ascii=False),
    )
    return bridge_token


def _build_mobile_app_redirect(bridge_token: str) -> str:
    return f"roadmapapp://auth-callback?bridgeToken={bridge_token}"


# Dependency: Current User (JWT 토큰에서 사용자 ID 추출)
async def get_current_user_id(
    authorization: Optional[str] = Header(None),
    services: Dict[str, Any] = Depends(get_services)
) -> str:
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


# ========== Google OAuth ==========
@router.get("/google/login")
async def get_google_login_url(
    mode: Optional[str] = None,
    client: Optional[str] = None,
    redirectUri: Optional[str] = None,
    services: Dict[str, Any] = Depends(get_services)
):
    """구글 로그인 URL 요청 (State 및 PKCE 포함)"""
    google_service = services["google_service"]
    auth_data = await google_service.get_authorization_url(
        mode=mode,
        client=client,
        redirect_uri=redirectUri,
    )
    
    return {
        "authUrl": auth_data["authUrl"],
        "state": auth_data["state"],
        "message": "구글 로그인 페이지로 이동하세요"
    }


@router.post("/google/callback")
async def google_callback(
    request: OAuthCallbackRequest,
    response: Response,
    client: Optional[str] = None,
    services: Dict[str, Any] = Depends(get_services)
):
    """구글 로그인 콜백 처리"""
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
        
        # mode 정보 추출 (회원가입 모드인지 확인)
        mode = user_info.get("_mode")
        client_type = (client or user_info.get("_client") or "").lower()
        is_mobile = client_type == "mobile"
        
        # 사용자 정보 추출
        provider_id = user_info.get("id")
        email = user_info.get("email")
        name = user_info.get("name")
        profile_image = user_info.get("picture")
        
        # 필수 값 검증
        if not provider_id:
            raise HTTPException(
                status_code=400,
                detail="구글 사용자 ID를 가져올 수 없습니다."
            )
        
        provider_id = str(provider_id)
        
        # 사용자 조회
        existing_user = await user_service.find_user("google", provider_id)
        
        if not existing_user:
            # 신규 사용자
            if mode == "signup":
                # 회원가입 모드면 DB에 저장만 하고 로그인은 하지 않음
                # (이미 find_user로 존재 여부 확인했으므로 find_or_create_user는 항상 신규 생성만 함)
                user = await user_service.find_or_create_user(
                    provider="google",
                    provider_id=provider_id,
                    email=email,
                    name=name,
                    nickname=None,
                    profile_image=profile_image
                )
                
                logger.info(f"구글 회원가입 완료: userId={user.id}")
                return {
                    "success": True,
                    "isNewUser": False,
                    "isSignupComplete": True,
                    "message": "회원가입이 완료되었습니다. 로그인해주세요.",
                    "userId": user.id,
                    "googleId": provider_id,
                    "email": email,
                    "name": name,
                    "profileImage": profile_image
                }
            else:
                # 로그인 모드면 회원가입 토큰만 반환
                signup_token = signup_token_service.generate_signup_token(
                    "google", provider_id, email, name, None, profile_image
                )
                
                return {
                    "success": False,
                    "isNewUser": True,
                    "message": "회원가입이 필요합니다.",
                    "signupToken": signup_token
                }
        
        # 기존 사용자인데 회원가입 모드인 경우
        if mode == "signup":
            raise HTTPException(
                status_code=400,
                detail="이미 가입된 사용자입니다. 로그인을 진행해주세요."
            )
        
        # 기존 사용자 - 로그인 처리
        user = existing_user
        user.email = email
        user.name = name
        user.profile_image = profile_image
        user = await user_service.save(user)
        
        # JWT 토큰 생성 및 쿠키 설정
        tokens = await generate_tokens_and_set_cookie(
            user,
            "google",
            email,
            name,
            jwt_service,
            refresh_token_service,
            response,
            set_cookie=not is_mobile,
        )
        access_token = tokens["accessToken"]
        refresh_token = tokens["refreshToken"]
        
        logger.info(f"구글 로그인 성공: userId={user.id}")
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
            "refreshToken": refresh_token if is_mobile else None,
            "tokenType": "Bearer"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"구글 로그인 실패: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="구글 로그인 처리 중 오류가 발생했습니다."
        )


@router.get("/{provider}/mobile/callback")
async def mobile_oauth_callback(
    provider: str = Path(..., description="google | kakao | naver"),
    code: str = "",
    state: str = "",
    services: Dict[str, Any] = Depends(get_services),
):
    """모바일 전용 OAuth 콜백: 백엔드에서 코드 교환 후 앱 딥링크로 브릿지 토큰 전달."""
    try:
        provider_key = provider.lower().strip()
        if provider_key not in {"google", "kakao", "naver"}:
            raise HTTPException(status_code=400, detail="지원하지 않는 provider입니다.")
        if not code:
            raise HTTPException(status_code=400, detail="OAuth code가 누락되었습니다.")
        if not state:
            raise HTTPException(status_code=400, detail="OAuth state가 누락되었습니다.")

        provider_service = services[f"{provider_key}_service"]
        user_service = services["user_service"]
        jwt_service = services["jwt_service"]
        signup_token_service = services["signup_token_service"]
        refresh_token_service = services["refresh_token_service"]

        user_info = await provider_service.process_oauth(code, state)
        mode = user_info.get("_mode")

        if provider_key == "google":
            provider_id = str(user_info.get("id") or "")
            email = user_info.get("email")
            name = user_info.get("name")
            nickname = None
            profile_image = user_info.get("picture")
        elif provider_key == "kakao":
            provider_id = str(user_info.get("id") or "")
            kakao_account = user_info.get("kakao_account", {})
            email = kakao_account.get("email")
            profile = kakao_account.get("profile", {})
            nickname = profile.get("nickname")
            name = None
            profile_image = profile.get("profile_image_url")
        else:
            response_data = user_info.get("response", {})
            provider_id = str(response_data.get("id") or "")
            email = response_data.get("email")
            name = response_data.get("name")
            nickname = response_data.get("nickname")
            profile_image = response_data.get("profile_image")

        if not provider_id:
            raise HTTPException(status_code=400, detail="OAuth 사용자 ID를 가져오지 못했습니다.")

        existing_user = await user_service.find_user(provider_key, provider_id)

        payload: Dict[str, Any]
        if not existing_user:
            if mode == "signup":
                user = await user_service.find_or_create_user(
                    provider=provider_key,
                    provider_id=provider_id,
                    email=email,
                    name=name,
                    nickname=nickname,
                    profile_image=profile_image,
                )
                payload = {
                    "success": True,
                    "isNewUser": False,
                    "isSignupComplete": True,
                    "message": "회원가입이 완료되었습니다. 로그인해주세요.",
                    "userId": str(user.id),
                }
            else:
                signup_token = signup_token_service.generate_signup_token(
                    provider_key,
                    provider_id,
                    email,
                    name,
                    nickname,
                    profile_image,
                )
                payload = {
                    "success": False,
                    "isNewUser": True,
                    "message": "회원가입이 필요합니다.",
                    "signupToken": signup_token,
                }
        else:
            if mode == "signup":
                raise HTTPException(
                    status_code=400,
                    detail="이미 가입된 사용자입니다. 로그인을 진행해주세요.",
                )

            user = existing_user
            user.email = email
            if name is not None:
                user.name = name
            if nickname is not None:
                user.nickname = nickname
            if profile_image is not None:
                user.profile_image_url = profile_image
            user = await user_service.save(user)

            tokens = await generate_tokens_and_set_cookie(
                user,
                provider_key,
                email,
                name,
                jwt_service,
                refresh_token_service,
                Response(),
                set_cookie=False,
            )
            payload = {
                "success": True,
                "isNewUser": False,
                "message": f"{provider_key} 로그인 성공",
                "userId": str(user.id),
                "accessToken": tokens["accessToken"],
                "refreshToken": tokens["refreshToken"],
                "tokenType": "Bearer",
            }

        bridge_token = await _create_mobile_bridge_token(refresh_token_service, payload)
        return RedirectResponse(
            url=_build_mobile_app_redirect(bridge_token),
            status_code=307,
        )
    except HTTPException as exc:
        bridge_token = await _create_mobile_bridge_token(
            services["refresh_token_service"],
            {
                "success": False,
                "isNewUser": False,
                "message": exc.detail,
            },
        )
        return RedirectResponse(
            url=_build_mobile_app_redirect(bridge_token),
            status_code=307,
        )
    except Exception as e:
        logger.error("모바일 OAuth 콜백 처리 실패: %s", e, exc_info=True)
        bridge_token = await _create_mobile_bridge_token(
            services["refresh_token_service"],
            {
                "success": False,
                "isNewUser": False,
                "message": "모바일 OAuth 처리 중 오류가 발생했습니다.",
            },
        )
        return RedirectResponse(
            url=_build_mobile_app_redirect(bridge_token),
            status_code=307,
        )


# ========== Kakao OAuth ==========
@router.get("/kakao/login")
async def get_kakao_login_url(
    mode: Optional[str] = None,
    client: Optional[str] = None,
    redirectUri: Optional[str] = None,
    services: Dict[str, Any] = Depends(get_services)
):
    """카카오 로그인 URL 요청 (State 및 PKCE 포함)"""
    kakao_service = services["kakao_service"]
    auth_data = await kakao_service.get_authorization_url(
        mode=mode,
        client=client,
        redirect_uri=redirectUri,
    )
    
    return {
        "authUrl": auth_data["authUrl"],
        "state": auth_data["state"],
        "message": "카카오 로그인 페이지로 이동하세요"
    }


@router.post("/kakao/callback")
async def kakao_callback(
    request: OAuthCallbackRequest,
    response: Response,
    client: Optional[str] = None,
    services: Dict[str, Any] = Depends(get_services)
):
    """카카오 로그인 콜백 처리"""
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
        
        # mode 정보 추출 (회원가입 모드인지 확인)
        mode = user_info.get("_mode")
        client_type = (client or user_info.get("_client") or "").lower()
        is_mobile = client_type == "mobile"
        
        # 사용자 정보 추출
        provider_id = user_info.get("id")
        kakao_account = user_info.get("kakao_account", {})
        email = kakao_account.get("email")
        profile = kakao_account.get("profile", {})
        nickname = profile.get("nickname")
        profile_image = profile.get("profile_image_url")
        
        # 필수 값 검증
        if not provider_id:
            raise HTTPException(
                status_code=400,
                detail="카카오 사용자 ID를 가져올 수 없습니다."
            )
        
        provider_id = str(provider_id)
        
        # 사용자 조회
        existing_user = await user_service.find_user("kakao", provider_id)
        
        if not existing_user:
            # 신규 사용자
            if mode == "signup":
                # 회원가입 모드면 DB에 저장만 하고 로그인은 하지 않음
                # (이미 find_user로 존재 여부 확인했으므로 find_or_create_user는 항상 신규 생성만 함)
                user = await user_service.find_or_create_user(
                    provider="kakao",
                    provider_id=provider_id,
                    email=email,
                    name=None,
                    nickname=nickname,
                    profile_image=profile_image
                )
                
                logger.info(f"카카오 회원가입 완료: userId={user.id}")
                return {
                    "success": True,
                    "isNewUser": False,
                    "isSignupComplete": True,
                    "message": "회원가입이 완료되었습니다. 로그인해주세요.",
                    "userId": user.id,
                    "kakaoId": provider_id,
                    "email": email,
                    "nickname": nickname,
                    "profileImage": profile_image
                }
            else:
                # 로그인 모드면 회원가입 토큰만 반환
                signup_token = signup_token_service.generate_signup_token(
                    "kakao", provider_id, email, None, nickname, profile_image
                )
                
                return {
                    "success": False,
                    "isNewUser": True,
                    "message": "회원가입이 필요합니다.",
                    "signupToken": signup_token
                }
        
        # 기존 사용자인데 회원가입 모드인 경우
        if mode == "signup":
            raise HTTPException(
                status_code=400,
                detail="이미 가입된 사용자입니다. 로그인을 진행해주세요."
            )
        
        # 기존 사용자 - 로그인 처리
        user = existing_user
        user.email = email
        user.nickname = nickname
        user.profile_image = profile_image
        user = await user_service.save(user)
        
        # JWT 토큰 생성 및 쿠키 설정
        tokens = await generate_tokens_and_set_cookie(
            user,
            "kakao",
            email,
            user.name,
            jwt_service,
            refresh_token_service,
            response,
            set_cookie=not is_mobile,
        )
        access_token = tokens["accessToken"]
        refresh_token = tokens["refreshToken"]
        
        logger.info(f"카카오 로그인 성공: userId={user.id}")
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
            "refreshToken": refresh_token if is_mobile else None,
            "tokenType": "Bearer"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"카카오 로그인 실패: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="카카오 로그인 처리 중 오류가 발생했습니다."
        )


# ========== Naver OAuth ==========
@router.get("/naver/login")
async def get_naver_login_url(
    mode: Optional[str] = None,
    client: Optional[str] = None,
    redirectUri: Optional[str] = None,
    services: Dict[str, Any] = Depends(get_services)
):
    """네이버 로그인 URL 요청 (State 검증 지원)"""
    naver_service = services["naver_service"]
    auth_data = await naver_service.get_authorization_url(
        mode=mode,
        client=client,
        redirect_uri=redirectUri,
    )
    
    return {
        "authUrl": auth_data["authUrl"],
        "state": auth_data["state"],
        "message": "네이버 로그인 페이지로 이동하세요"
    }


@router.post("/naver/callback")
async def naver_callback(
    request: OAuthCallbackRequest,
    response: Response,
    client: Optional[str] = None,
    services: Dict[str, Any] = Depends(get_services)
):
    """네이버 로그인 콜백 처리"""
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
        
        # mode 정보 추출 (회원가입 모드인지 확인)
        mode = user_info.get("_mode")
        client_type = (client or user_info.get("_client") or "").lower()
        is_mobile = client_type == "mobile"
        
        # 사용자 정보 추출
        response_data = user_info.get("response", {})
        provider_id = response_data.get("id")
        email = response_data.get("email")
        name = response_data.get("name")
        nickname = response_data.get("nickname")
        profile_image = response_data.get("profile_image")
        
        # 필수 값 검증
        if not provider_id:
            raise HTTPException(
                status_code=400,
                detail="네이버 사용자 ID를 가져올 수 없습니다."
            )
        
        provider_id = str(provider_id)
        
        # 사용자 조회
        existing_user = await user_service.find_user("naver", provider_id)
        
        if not existing_user:
            # 신규 사용자
            if mode == "signup":
                # 회원가입 모드면 DB에 저장만 하고 로그인은 하지 않음
                # (이미 find_user로 존재 여부 확인했으므로 find_or_create_user는 항상 신규 생성만 함)
                user = await user_service.find_or_create_user(
                    provider="naver",
                    provider_id=provider_id,
                    email=email,
                    name=name,
                    nickname=nickname,
                    profile_image=profile_image
                )
                
                logger.info(f"네이버 회원가입 완료: userId={user.id}")
                return {
                    "success": True,
                    "isNewUser": False,
                    "isSignupComplete": True,
                    "message": "회원가입이 완료되었습니다. 로그인해주세요.",
                    "userId": user.id,
                    "naverId": provider_id,
                    "email": email,
                    "name": name,
                    "nickname": nickname,
                    "profileImage": profile_image
                }
            else:
                # 로그인 모드면 회원가입 토큰만 반환
                signup_token = signup_token_service.generate_signup_token(
                    "naver", provider_id, email, name, nickname, profile_image
                )
                
                return {
                    "success": False,
                    "isNewUser": True,
                    "message": "회원가입이 필요합니다.",
                    "signupToken": signup_token
                }
        
        # 기존 사용자인데 회원가입 모드인 경우
        if mode == "signup":
            raise HTTPException(
                status_code=400,
                detail="이미 가입된 사용자입니다. 로그인을 진행해주세요."
            )
        
        # 기존 사용자 - 로그인 처리
        user = existing_user
        user.email = email
        user.name = name
        user.nickname = nickname
        user.profile_image = profile_image
        user = await user_service.save(user)
        
        # JWT 토큰 생성 및 쿠키 설정
        tokens = await generate_tokens_and_set_cookie(
            user,
            "naver",
            email,
            name,
            jwt_service,
            refresh_token_service,
            response,
            set_cookie=not is_mobile,
        )
        access_token = tokens["accessToken"]
        refresh_token = tokens["refreshToken"]
        
        logger.info(f"네이버 로그인 성공: userId={user.id}")
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
            "refreshToken": refresh_token if is_mobile else None,
            "tokenType": "Bearer"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"네이버 로그인 실패: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="네이버 로그인 처리 중 오류가 발생했습니다."
        )


# ========== Signup ==========
@router.post("/signup")
async def oauth_signup(
    request: SignupRequest,
    response: Response,
    client: Optional[str] = None,
    services: Dict[str, Any] = Depends(get_services)
):
    """OAuth 회원가입 처리 (토큰 기반)"""
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
        
        # 사용자 조회 (이미 존재하는지 확인)
        existing_user = await user_service.find_user(provider, provider_id)
        
        if existing_user:
            # 이미 존재하는 사용자 - 회원가입 불가
            raise HTTPException(
                status_code=400,
                detail="이미 가입된 사용자입니다. 로그인을 진행해주세요."
            )
        
        # 신규 사용자 생성 (이미 존재 여부 확인했으므로 find_or_create_user는 항상 신규 생성만 함)
        user = await user_service.find_or_create_user(
            provider=provider,
            provider_id=provider_id,
            email=email,
            name=name,
            nickname=nickname,
            profile_image=profile_image
        )
        
        client_type = (client or "").lower()
        is_mobile = client_type == "mobile"

        # JWT 토큰 생성 및 쿠키 설정
        tokens = await generate_tokens_and_set_cookie(
            user,
            provider,
            email,
            name,
            jwt_service,
            refresh_token_service,
            response,
            set_cookie=not is_mobile,
        )
        access_token = tokens["accessToken"]
        refresh_token = tokens["refreshToken"]
        
        logger.info(f"OAuth 회원가입 성공: userId={user.id}, provider={provider}")
        return {
            "success": True,
            "message": "회원가입 성공",
            "userId": user.id,
            "email": email,
            "name": name,
            "nickname": nickname,
            "profileImage": profile_image,
            "accessToken": access_token,
            "refreshToken": refresh_token if is_mobile else None,
            "tokenType": "Bearer"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"OAuth 회원가입 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="회원가입 처리 중 오류가 발생했습니다.")


# ========== User Profile ==========
@router.get("/me")
async def get_current_user(
    user_id: str = Depends(get_current_user_id),
    services: Dict[str, Any] = Depends(get_services)
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
            "id": str(user.id),
            "name": user.name,
            "email": user.email,
            "nickname": user.nickname,
            "profileImage": user.profile_image_url,
            "provider": user.auth_provider
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"사용자 정보 조회 실패: userId={user_id}, error={e}", exc_info=True)
        raise HTTPException(status_code=500, detail="사용자 정보 조회 중 오류가 발생했습니다.")


@router.put("/me")
async def update_current_user(
    request: UpdateProfileRequest,
    user_id: str = Depends(get_current_user_id),
    services: Dict[str, Any] = Depends(get_services)
):
    """현재 로그인한 사용자 프로필 정보 업데이트"""
    try:
        logger.info(f"[백엔드 API] PUT /api/oauth/me 요청 수신 - userId={user_id}")
        logger.info(f"[백엔드 API] 요청 파라미터 - name={request.name}, profileImage={'있음' if request.profileImage else '없음'}")
        
        user_service = services["user_service"]
        
        # 사용자 정보 조회
        logger.info(f"[백엔드 API] DB에서 사용자 정보 조회 시작 - userId={user_id}")
        user = await user_service.find_by_id(user_id)
        
        if not user:
            logger.error(f"[백엔드 API] 사용자를 찾을 수 없음 - userId={user_id}")
            raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
        
        logger.info(f"[백엔드 API] 사용자 정보 조회 완료 - userId={user_id}, 현재 name={user.name}, 현재 nickname={user.nickname}")
        
        # 정보 업데이트
        # name 파라미터는 nickname 컬럼에 저장 (name은 OAuth 초기 정보로 유지)
        name = request.name
        profileImage = request.profileImage
        
        if name is not None:
            logger.info(f"[백엔드 API] nickname 컬럼 업데이트 - 기존: {user.nickname} → 새로운: {name}")
            user.nickname = name
        if profileImage is not None:
            logger.info(f"[백엔드 API] profile_image_url 컬럼 업데이트 - 기존: {user.profile_image_url} → 새로운: {profileImage}")
            user.profile_image_url = profileImage
        
        # 저장
        logger.info(f"[백엔드 API] DB 저장 시작 - userId={user_id}")
        updated_user = await user_service.save(user)
        logger.info(f"[백엔드 API] DB 저장 완료 - userId={user_id}, 저장된 nickname={updated_user.nickname}, 저장된 name={updated_user.name}")
        
        logger.info(f"[백엔드 API] 사용자 정보 업데이트 성공: userId={user_id}")
        
        return {
            "id": str(updated_user.id),
            "name": updated_user.name,
            "email": updated_user.email,
            "nickname": updated_user.nickname,
            "profileImage": updated_user.profile_image_url,
            "provider": updated_user.auth_provider
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[백엔드 API] 사용자 정보 업데이트 실패: userId={user_id}, error={e}", exc_info=True)
        raise HTTPException(status_code=500, detail="사용자 정보 업데이트 중 오류가 발생했습니다.")


# ========== Refresh Token ==========
@router.post("/mobile/exchange")
async def exchange_mobile_bridge_token(
    request: MobileBridgeExchangeRequest,
    services: Dict[str, Any] = Depends(get_services),
):
    """모바일 딥링크 bridge token을 실제 인증 응답으로 교환(1회성)."""
    key = f"{MOBILE_BRIDGE_PREFIX}{request.bridgeToken}"
    refresh_token_service = services["refresh_token_service"]
    raw = await refresh_token_service.redis.get(key)
    if not raw:
        raise HTTPException(status_code=401, detail="bridge token이 유효하지 않거나 만료되었습니다.")
    await refresh_token_service.redis.delete(key)
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail="bridge payload 파싱 실패") from e
    return payload


@router.post("/google/native-login")
async def google_native_login(
    request: GoogleNativeLoginRequest,
    response: Response,
    services: Dict[str, Any] = Depends(get_services),
):
    """Flutter google_sign_in idToken을 검증하고 자체 JWT를 발급한다."""
    try:
        if not request.idToken:
            raise HTTPException(status_code=400, detail="idToken이 필요합니다.")

        http_client: httpx.AsyncClient = services["google_service"].http_client
        user_service: UserService = services["user_service"]
        jwt_service: JWTService = services["jwt_service"]
        refresh_token_service: RefreshTokenService = services["refresh_token_service"]

        token_info_res = await http_client.get(
            "https://oauth2.googleapis.com/tokeninfo",
            params={"id_token": request.idToken},
        )
        if token_info_res.status_code != 200:
            raise HTTPException(status_code=401, detail="유효하지 않은 Google idToken입니다.")
        token_info = token_info_res.json()

        aud = token_info.get("aud")
        allowed_aud = {settings.google_client_id}
        if settings.google_android_client_id:
            allowed_aud.add(settings.google_android_client_id)
        if aud not in allowed_aud:
            raise HTTPException(status_code=401, detail="Google 토큰 aud 검증 실패")

        issuer = token_info.get("iss")
        if issuer not in {"https://accounts.google.com", "accounts.google.com"}:
            raise HTTPException(status_code=401, detail="Google 토큰 iss 검증 실패")

        provider_id = token_info.get("sub")
        email = token_info.get("email")
        name = token_info.get("name")
        profile_image = token_info.get("picture")
        if not provider_id or not email:
            raise HTTPException(status_code=400, detail="Google 사용자 정보가 불완전합니다.")

        user = await user_service.find_or_create_user(
            provider="google",
            provider_id=str(provider_id),
            email=email,
            name=name,
            nickname=name,
            profile_image=profile_image,
        )

        tokens = await generate_tokens_and_set_cookie(
            user=user,
            provider="google",
            email=email,
            name=name,
            jwt_service=jwt_service,
            refresh_token_service=refresh_token_service,
            response=response,
            set_cookie=False,
        )
        return {
            "success": True,
            "message": "구글 네이티브 로그인 성공",
            "userId": str(user.id),
            "accessToken": tokens["accessToken"],
            "refreshToken": tokens["refreshToken"],
            "tokenType": "Bearer",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("구글 네이티브 로그인 실패: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="구글 네이티브 로그인 처리 중 오류가 발생했습니다.")


def _kakao_profile_from_user_me(user_info: Dict[str, Any]) -> tuple[str, str, Optional[str], Optional[str]]:
    """/v2/user/me 응답 → (provider_id, email, display_name, profile_image)"""
    provider_id = str(user_info.get("id") or "")
    kakao_account = user_info.get("kakao_account") or {}
    email = kakao_account.get("email")
    profile = kakao_account.get("profile") or {}
    nickname = profile.get("nickname")
    profile_image = profile.get("profile_image_url")
    if not email:
        if not provider_id:
            raise HTTPException(
                status_code=400, detail="카카오 사용자 식별 정보를 가져오지 못했습니다."
            )
        email = f"kakao_{provider_id}@users.local"
    display = nickname or (email.split("@")[0] if email else None)
    return provider_id, email, display, profile_image


def _naver_profile_from_user_me(user_info: Dict[str, Any]) -> tuple[str, str, Optional[str], Optional[str]]:
    """/v1/nid/me 응답 → (provider_id, email, display_name, profile_image)"""
    response = user_info.get("response") or {}
    provider_id = str(response.get("id") or "")
    email = response.get("email")
    profile_image = response.get("profile_image")
    name = response.get("name")
    nickname = response.get("nickname")
    if not email:
        if not provider_id:
            raise HTTPException(
                status_code=400, detail="네이버 사용자 식별 정보를 가져오지 못했습니다."
            )
        email = f"naver_{provider_id}@users.local"
    display = name or nickname or (email.split("@")[0] if email else None)
    return provider_id, email, display, profile_image


@router.post("/kakao/native-login")
async def kakao_native_login(
    request: KakaoNativeLoginRequest,
    response: Response,
    services: Dict[str, Any] = Depends(get_services),
):
    """Flutter kakao_flutter_sdk accessToken으로 사용자 확인 후 자체 JWT 발급."""
    if not request.accessToken or not request.accessToken.strip():
        raise HTTPException(status_code=400, detail="accessToken이 필요합니다.")
    kakao_service: KakaoOAuthService = services["kakao_service"]
    user_service: UserService = services["user_service"]
    jwt_service: JWTService = services["jwt_service"]
    refresh_token_service: RefreshTokenService = services["refresh_token_service"]
    try:
        user_info = await kakao_service.get_user_info(request.accessToken.strip())
    except Exception as e:
        logger.error("카카오 accessToken 검증 실패: %s", e, exc_info=True)
        raise HTTPException(
            status_code=401, detail="유효하지 않은 카카오 accessToken입니다."
        ) from e
    try:
        provider_id, email, display_name, profile_image = _kakao_profile_from_user_me(
            user_info
        )
        if not provider_id:
            raise HTTPException(status_code=400, detail="카카오 사용자 ID가 없습니다.")
        user = await user_service.find_or_create_user(
            provider="kakao",
            provider_id=provider_id,
            email=email,
            name=display_name,
            nickname=display_name,
            profile_image=profile_image,
        )
        tokens = await generate_tokens_and_set_cookie(
            user=user,
            provider="kakao",
            email=email,
            name=display_name,
            jwt_service=jwt_service,
            refresh_token_service=refresh_token_service,
            response=response,
            set_cookie=False,
        )
        return {
            "success": True,
            "message": "카카오 네이티브 로그인 성공",
            "userId": str(user.id),
            "accessToken": tokens["accessToken"],
            "refreshToken": tokens["refreshToken"],
            "tokenType": "Bearer",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("카카오 네이티브 로그인 실패: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500, detail="카카오 네이티브 로그인 처리 중 오류가 발생했습니다."
        ) from e


@router.post("/naver/native-login")
async def naver_native_login(
    request: NaverNativeLoginRequest,
    response: Response,
    services: Dict[str, Any] = Depends(get_services),
):
    """Flutter 네이버 SDK accessToken으로 사용자 확인 후 자체 JWT 발급."""
    if not request.accessToken or not request.accessToken.strip():
        raise HTTPException(status_code=400, detail="accessToken이 필요합니다.")
    naver_service: NaverOAuthService = services["naver_service"]
    user_service: UserService = services["user_service"]
    jwt_service: JWTService = services["jwt_service"]
    refresh_token_service: RefreshTokenService = services["refresh_token_service"]
    try:
        user_info = await naver_service.get_user_info(request.accessToken.strip())
    except Exception as e:
        logger.error("네이버 accessToken 검증 실패: %s", e, exc_info=True)
        raise HTTPException(
            status_code=401, detail="유효하지 않은 네이버 accessToken입니다."
        ) from e
    try:
        provider_id, email, display_name, profile_image = _naver_profile_from_user_me(
            user_info
        )
        if not provider_id:
            raise HTTPException(status_code=400, detail="네이버 사용자 ID가 없습니다.")
        user = await user_service.find_or_create_user(
            provider="naver",
            provider_id=provider_id,
            email=email,
            name=display_name,
            nickname=display_name,
            profile_image=profile_image,
        )
        tokens = await generate_tokens_and_set_cookie(
            user=user,
            provider="naver",
            email=email,
            name=display_name,
            jwt_service=jwt_service,
            refresh_token_service=refresh_token_service,
            response=response,
            set_cookie=False,
        )
        return {
            "success": True,
            "message": "네이버 네이티브 로그인 성공",
            "userId": str(user.id),
            "accessToken": tokens["accessToken"],
            "refreshToken": tokens["refreshToken"],
            "tokenType": "Bearer",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("네이버 네이티브 로그인 실패: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500, detail="네이버 네이티브 로그인 처리 중 오류가 발생했습니다."
        ) from e


@router.post("/refresh")
async def refresh_token(
    request_body: Optional[RefreshTokenRequest] = None,
    refreshToken: Optional[str] = Cookie(None),
    client: Optional[str] = None,
    authorization: Optional[str] = None,
    services: Dict[str, Any] = Depends(get_services)
):
    """리프레시 토큰으로 새 액세스 토큰 발급"""
    if not refreshToken and request_body and request_body.refreshToken:
        refreshToken = request_body.refreshToken

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
        
        is_mobile = (client or "").lower() == "mobile"

        response = JSONResponse({
            "success": True,
            "accessToken": new_access_token,
            "refreshToken": new_refresh_token if is_mobile else None,
            "tokenType": "Bearer"
        })
        
        # 새 리프레시 토큰 쿠키 설정
        if not is_mobile:
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
        
        # 액세스 토큰에서 사용자 ID 추출 (백업)
        if not user_id and authorization and authorization.startswith("Bearer "):
            access_token = authorization[7:]
            user_id = jwt_service.extract_user_id(access_token)
        
        # 사용자 ID가 확인되면 모든 토큰 무효화
        if user_id:
            await refresh_token_service.invalidate_all_user_tokens(user_id)
        
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
    user_id: str = Path(..., description="무효화할 사용자 ID"),
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


@router.post("/update-signup-info")
async def update_signup_info(
    request: UpdateSignupInfoRequest,
    services: Dict[str, Any] = Depends(get_services)
):
    """회원가입 완료 후 추가 프로필 정보 업데이트"""
    try:
        user_service = services["user_service"]
        auth_profile_service = services["auth_profile_service"]
        
        # 사용자 조회
        user = await user_service.find_by_id(request.userId)
        
        if not user:
            raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
        
        # users 스키마에는 age / interests 컬럼이 없어 저장하지 않음
        if request.age is not None:
            logger.info(f"users 스키마상 age 저장 생략: userId={request.userId}, age={request.age}")
        if request.interests:
            logger.info(f"users 스키마상 interests 저장 생략: userId={request.userId}, interests={request.interests}")

        target_job = request.targetJob.strip() if request.targetJob else None
        interest_keywords = request.interestKeywords or []
        if target_job or interest_keywords:
            await auth_profile_service.upsert_sync_profile(
                user_id=request.userId,
                target_job=target_job,
                interest_keywords=interest_keywords,
            )
        
        return {
            "success": True,
            "message": "회원가입 정보가 업데이트되었습니다.",
            "userId": request.userId,
            "targetJob": target_job,
            "interestKeywords": interest_keywords,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"회원가입 정보 업데이트 실패: userId={request.userId}, error={e}", exc_info=True)
        raise HTTPException(status_code=500, detail="정보 업데이트 중 오류가 발생했습니다.")

