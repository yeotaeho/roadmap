from fastapi import APIRouter, HTTPException, Depends, Request, Response, Cookie, Path, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any
import httpx
import redis.asyncio as redis
import logging
from sqlalchemy.ext.asyncio import AsyncSession

# Domain imports
from domain.oauth.config.settings import settings
from domain.oauth.base.database import get_db
from domain.oauth.service.google_oauth_service import GoogleOAuthService
from domain.oauth.service.kakao_oauth_service import KakaoOAuthService
from domain.oauth.service.naver_oauth_service import NaverOAuthService
from domain.oauth.service.user_service import UserService
from domain.oauth.service.refresh_token_service import RefreshTokenService
from domain.oauth.util.jwt import JWTService
from domain.oauth.util.signup_token import SignupTokenService
from domain.oauth.util.state import OAuthStateService
from domain.oauth.util.pkce import PKCEService
from domain.oauth.model.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/oauth", tags=["oauth"])

# Request Models
class OAuthCallbackRequest(BaseModel):
    code: str
    state: Optional[str] = None


class SignupRequest(BaseModel):
    signupToken: str
    age: Optional[int] = None


class UpdateProfileRequest(BaseModel):
    name: Optional[str] = None
    profileImage: Optional[str] = None


class UpdateSignupInfoRequest(BaseModel):
    userId: int
    age: Optional[int] = None
    interests: Optional[list] = None


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


async def generate_tokens_and_set_cookie(
    user: User,
    provider: str,
    email: str,
    name: Optional[str],
    jwt_service: JWTService,
    refresh_token_service: RefreshTokenService,
    response: Response
) -> Dict[str, str]:
    """JWT 토큰 생성 및 쿠키 설정 헬퍼 함수"""
    # JWT 토큰 생성
    access_token = jwt_service.generate_token(user.id, provider, email, name, user.age)
    refresh_token = jwt_service.generate_refresh_token(user.id, provider, email, name, user.age)
    
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
    
    return {
        "accessToken": access_token,
        "refreshToken": refresh_token
    }


# Dependency: Current User (JWT 토큰에서 사용자 ID 추출)
async def get_current_user_id(
    authorization: Optional[str] = Header(None),
    services: Dict[str, Any] = Depends(get_services)
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


# ========== Google OAuth ==========
@router.get("/google/login")
async def get_google_login_url(
    mode: Optional[str] = None,
    services: Dict[str, Any] = Depends(get_services)
):
    """구글 로그인 URL 요청 (State 및 PKCE 포함)"""
    google_service = services["google_service"]
    auth_data = await google_service.get_authorization_url(mode=mode)
    
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
                    profile_image=profile_image,
                    age=None
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
            user, "google", email, name, jwt_service, refresh_token_service, response
        )
        access_token = tokens["accessToken"]
        
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


# ========== Kakao OAuth ==========
@router.get("/kakao/login")
async def get_kakao_login_url(
    mode: Optional[str] = None,
    services: Dict[str, Any] = Depends(get_services)
):
    """카카오 로그인 URL 요청 (State 및 PKCE 포함)"""
    kakao_service = services["kakao_service"]
    auth_data = await kakao_service.get_authorization_url(mode=mode)
    
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
                    profile_image=profile_image,
                    age=None
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
            user, "kakao", email, user.name, jwt_service, refresh_token_service, response
        )
        access_token = tokens["accessToken"]
        
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
    services: Dict[str, Any] = Depends(get_services)
):
    """네이버 로그인 URL 요청 (State 검증 지원)"""
    naver_service = services["naver_service"]
    auth_data = await naver_service.get_authorization_url(mode=mode)
    
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
                    profile_image=profile_image,
                    age=None
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
            user, "naver", email, name, jwt_service, refresh_token_service, response
        )
        access_token = tokens["accessToken"]
        
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
        age = request.age or oauth_info.get("age")
        
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
            profile_image=profile_image,
            age=age
        )
        
        # JWT 토큰 생성 및 쿠키 설정
        tokens = await generate_tokens_and_set_cookie(
            user, provider, email, name, jwt_service, refresh_token_service, response
        )
        access_token = tokens["accessToken"]
        
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
    user_id: int = Depends(get_current_user_id),
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
    request: UpdateProfileRequest,
    user_id: int = Depends(get_current_user_id),
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
            logger.info(f"[백엔드 API] profile_image 컬럼 업데이트 - 기존: {user.profile_image} → 새로운: {profileImage}")
            user.profile_image = profileImage
        
        # 저장
        logger.info(f"[백엔드 API] DB 저장 시작 - userId={user_id}")
        updated_user = await user_service.save(user)
        logger.info(f"[백엔드 API] DB 저장 완료 - userId={user_id}, 저장된 nickname={updated_user.nickname}, 저장된 name={updated_user.name}")
        
        logger.info(f"[백엔드 API] 사용자 정보 업데이트 성공: userId={user_id}")
        
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
        logger.error(f"[백엔드 API] 사용자 정보 업데이트 실패: userId={user_id}, error={e}", exc_info=True)
        raise HTTPException(status_code=500, detail="사용자 정보 업데이트 중 오류가 발생했습니다.")


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
        
        # 사용자 정보 조회 (name, age 추출)
        user = await user_service.find_by_id(user_id)
        name = user.name if user else None
        age = user.age if user else None
        
        # 새 토큰 생성 및 로테이션
        new_access_token = jwt_service.generate_token(user_id, provider, email, name, age)
        new_refresh_token = jwt_service.generate_refresh_token(user_id, provider, email, name, age)
        await refresh_token_service.rotate_refresh_token(user_id, refreshToken, new_refresh_token)
        
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


@router.post("/update-signup-info")
async def update_signup_info(
    request: UpdateSignupInfoRequest,
    services: Dict[str, Any] = Depends(get_services)
):
    """회원가입 완료 후 나이와 관심분야 업데이트"""
    try:
        user_service = services["user_service"]
        
        # 사용자 조회
        user = await user_service.find_by_id(request.userId)
        
        if not user:
            raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
        
        # 나이와 관심분야 업데이트
        if request.age:
            user.age = request.age
            logger.info(f"회원가입 정보 업데이트: userId={request.userId}, age={request.age}")
        
        if request.interests and len(request.interests) > 0:
            # 관심분야를 JSON 형태로 저장
            user.pref_domain_json = {"interests": request.interests}
            logger.info(f"회원가입 정보 업데이트: userId={request.userId}, interests={request.interests}")
        
        await user_service.save(user)
        
        return {
            "success": True,
            "message": "회원가입 정보가 업데이트되었습니다.",
            "userId": request.userId
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"회원가입 정보 업데이트 실패: userId={request.userId}, error={e}", exc_info=True)
        raise HTTPException(status_code=500, detail="정보 업데이트 중 오류가 발생했습니다.")

