import httpx
from typing import Dict, Any, Optional
import logging
from urllib.parse import urlencode
from ..config.settings import settings
from ..util.state import OAuthStateService
from ..util.pkce import PKCEService

logger = logging.getLogger(__name__)


class KakaoOAuthService:
    """카카오 OAuth 서비스"""
    
    KAKAO_AUTH_URL = "https://kauth.kakao.com/oauth/authorize"
    KAKAO_TOKEN_URL = "https://kauth.kakao.com/oauth/token"
    KAKAO_USER_INFO_URL = "https://kapi.kakao.com/v2/user/me"
    
    def __init__(
        self,
        state_service: OAuthStateService,
        pkce_service: PKCEService,
        http_client: httpx.AsyncClient
    ):
        self.state_service = state_service
        self.pkce_service = pkce_service
        self.http_client = http_client
        self.client_id = settings.kakao_client_id
        self.client_secret = settings.kakao_client_secret
        self.redirect_uri = settings.kakao_redirect_uri
    
    async def get_authorization_url(self, mode: Optional[str] = None) -> Dict[str, str]:
        """카카오 로그인 URL 생성 (State 및 PKCE 지원)"""
        # 1. State 생성 및 저장 (mode 정보 포함)
        state = await self.state_service.generate_and_store_state(mode=mode)
        
        # 2. PKCE Code Verifier & Challenge 생성
        code_verifier = self.pkce_service.generate_code_verifier()
        code_challenge = self.pkce_service.generate_code_challenge(code_verifier)
        
        # 3. Code Verifier를 Redis에 저장
        await self.pkce_service.store_code_verifier(state, code_verifier)
        
        # 4. Authorization URL 생성
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256"
        }
        
        auth_url = f"{self.KAKAO_AUTH_URL}?{urlencode(params)}"
        
        logger.info(f"카카오 인증 URL 생성 완료: state={state}")
        
        return {
            "authUrl": auth_url,
            "state": state
        }
    
    async def get_access_token(self, code: str, state: str) -> Dict[str, Any]:
        """인가 코드로 액세스 토큰 발급 (PKCE 지원)"""
        logger.info(f"카카오 액세스 토큰 요청: code={code}, state={state}")
        
        # PKCE Code Verifier 조회
        code_verifier = None
        if state:
            code_verifier = await self.pkce_service.get_and_remove_code_verifier(state)
            if code_verifier:
                logger.info("PKCE Code Verifier 추가됨")
            else:
                logger.warn(f"Code Verifier를 찾을 수 없음: state={state}")
        
        # 토큰 요청 파라미터
        data = {
            "grant_type": "authorization_code",
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "code": code
        }
        
        # client_secret이 있으면 추가
        if self.client_secret:
            data["client_secret"] = self.client_secret
        
        if code_verifier:
            data["code_verifier"] = code_verifier
        
        try:
            response = await self.http_client.post(
                self.KAKAO_TOKEN_URL,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            response.raise_for_status()
            
            token_data = response.json()
            logger.info("카카오 액세스 토큰 발급 성공")
            return token_data
            
        except httpx.HTTPError as e:
            logger.error(f"카카오 액세스 토큰 발급 실패: {e}")
            raise RuntimeError(f"카카오 토큰 발급 실패: {e}")
    
    async def get_user_info(self, access_token: str) -> Dict[str, Any]:
        """액세스 토큰으로 사용자 정보 조회"""
        logger.info("카카오 사용자 정보 조회")
        
        try:
            response = await self.http_client.get(
                self.KAKAO_USER_INFO_URL,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/x-www-form-urlencoded"
                }
            )
            response.raise_for_status()
            
            user_info = response.json()
            logger.info(f"카카오 사용자 정보 조회 성공: id={user_info.get('id')}")
            return user_info
            
        except httpx.HTTPError as e:
            logger.error(f"카카오 사용자 정보 조회 실패: {e}")
            raise RuntimeError(f"카카오 사용자 정보 조회 실패: {e}")
    
    async def process_oauth(self, code: str, state: str) -> Dict[str, Any]:
        """전체 OAuth 플로우 실행 (State 검증 및 PKCE 지원)"""
        # 1. State 검증 및 mode 정보 추출
        state_data = await self.state_service.validate_and_remove_state(state)
        if not state_data:
            raise RuntimeError("State 검증 실패: CSRF 공격 가능성")
        
        mode = state_data.get("mode")
        
        # 2. 토큰 발급 (PKCE code_verifier 포함)
        token_response = await self.get_access_token(code, state)
        
        # 3. 사용자 정보 조회
        user_info = await self.get_user_info(token_response["access_token"])
        
        # mode 정보를 user_info에 추가
        if mode:
            user_info["_mode"] = mode
        
        return user_info

