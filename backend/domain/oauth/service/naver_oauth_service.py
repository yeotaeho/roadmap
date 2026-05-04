import httpx
from typing import Dict, Any, Optional
import logging
from urllib.parse import urlencode
from ..config.settings import settings
from ..util.state import OAuthStateService

logger = logging.getLogger(__name__)


class NaverOAuthService:
    """네이버 OAuth 서비스"""
    
    NAVER_AUTH_URL = "https://nid.naver.com/oauth2.0/authorize"
    NAVER_TOKEN_URL = "https://nid.naver.com/oauth2.0/token"
    NAVER_USER_INFO_URL = "https://openapi.naver.com/v1/nid/me"
    
    def __init__(
        self,
        state_service: OAuthStateService,
        http_client: httpx.AsyncClient
    ):
        self.state_service = state_service
        self.http_client = http_client
        self.client_id = settings.naver_client_id
        self.client_secret = settings.naver_client_secret
        self.redirect_uri = settings.naver_redirect_uri
    
    async def get_authorization_url(self, mode: Optional[str] = None) -> Dict[str, str]:
        """네이버 로그인 URL 생성 (State 검증 지원)"""
        # State 생성 및 Redis에 저장 (mode 정보 포함)
        state = await self.state_service.generate_and_store_state(mode=mode)
        
        logger.info(f"네이버 로그인 URL 생성: state={state}")
        
        # Authorization URL 생성
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "state": state
        }
        
        auth_url = f"{self.NAVER_AUTH_URL}?{urlencode(params)}"
        
        logger.info(f"생성된 네이버 인증 URL: {auth_url}")
        
        return {
            "authUrl": auth_url,
            "state": state
        }
    
    async def get_access_token(self, code: str, state: str) -> Dict[str, Any]:
        """인가 코드로 액세스 토큰 발급"""
        logger.info(f"네이버 액세스 토큰 요청: code={code}, state={state}")
        
        # 토큰 요청 파라미터
        data = {
            "grant_type": "authorization_code",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "state": state
        }
        
        try:
            response = await self.http_client.post(
                self.NAVER_TOKEN_URL,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            response.raise_for_status()
            
            token_data = response.json()
            logger.info("네이버 액세스 토큰 발급 성공")
            return token_data
            
        except httpx.HTTPError as e:
            logger.error(f"네이버 액세스 토큰 발급 실패: {e}")
            raise RuntimeError(f"네이버 토큰 발급 실패: {e}")
    
    async def get_user_info(self, access_token: str) -> Dict[str, Any]:
        """액세스 토큰으로 사용자 정보 조회"""
        logger.info("네이버 사용자 정보 조회")
        
        try:
            response = await self.http_client.get(
                self.NAVER_USER_INFO_URL,
                headers={"Authorization": f"Bearer {access_token}"}
            )
            response.raise_for_status()
            
            user_info = response.json()
            logger.info(f"네이버 사용자 정보 조회 성공: id={user_info.get('response', {}).get('id')}")
            return user_info
            
        except httpx.HTTPError as e:
            logger.error(f"네이버 사용자 정보 조회 실패: {e}")
            raise RuntimeError(f"네이버 사용자 정보 조회 실패: {e}")
    
    async def process_oauth(self, code: str, state: str) -> Dict[str, Any]:
        """전체 OAuth 플로우 실행 (State 검증 강화)"""
        # 1. State 검증 및 mode 정보 추출
        state_data = await self.state_service.validate_and_remove_state(state)
        if not state_data:
            raise RuntimeError("State 검증 실패: CSRF 공격 가능성")
        
        mode = state_data.get("mode")
        
        # 2. 토큰 발급
        token_response = await self.get_access_token(code, state)
        
        # 3. 사용자 정보 조회
        user_info = await self.get_user_info(token_response["access_token"])
        
        # mode 정보를 user_info에 추가
        if mode:
            user_info["_mode"] = mode
        
        return user_info

