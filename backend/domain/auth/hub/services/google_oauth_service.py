import logging
from typing import Any, Dict, Optional

import httpx

from core.config.settings import settings
from domain.auth.spokes.infra.oauth.authlib_helpers import (
    exchange_authorization_code,
    oauth2_client_for_authorization,
)
from domain.auth.spokes.infra.oauth.pkce import PKCEService
from domain.auth.spokes.infra.oauth.state import OAuthStateService

logger = logging.getLogger(__name__)


class GoogleOAuthService:
    """구글 OAuth 서비스 (인가 URL·토큰 교환: Authlib / 사용자 정보: httpx)"""

    GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
    GOOGLE_USER_INFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"

    def __init__(
        self,
        state_service: OAuthStateService,
        pkce_service: PKCEService,
        http_client: httpx.AsyncClient,
    ):
        self.state_service = state_service
        self.pkce_service = pkce_service
        self.http_client = http_client
        self.client_id = settings.google_client_id
        self.client_secret = settings.google_client_secret
        self.redirect_uri = settings.google_redirect_uri

    async def get_authorization_url(
        self,
        mode: Optional[str] = None,
        client: Optional[str] = None,
        redirect_uri: Optional[str] = None,
    ) -> Dict[str, str]:
        """구글 로그인 URL 생성 (State 및 PKCE 지원)"""
        effective_redirect_uri = redirect_uri or self.redirect_uri
        state = await self.state_service.generate_and_store_state(
            mode=mode,
            client=client,
            redirect_uri=effective_redirect_uri,
        )

        code_verifier = self.pkce_service.generate_code_verifier()
        await self.pkce_service.store_code_verifier(state, code_verifier)

        oauth = oauth2_client_for_authorization(
            client_id=self.client_id,
            client_secret=self.client_secret,
            redirect_uri=effective_redirect_uri,
            scope="email profile",
            code_challenge_method="S256",
        )
        auth_url, _ = oauth.create_authorization_url(
            self.GOOGLE_AUTH_URL,
            state=state,
            code_verifier=code_verifier,
            access_type="offline",
            prompt="consent",
        )

        logger.info(f"구글 인증 URL 생성 완료: state={state}")

        return {
            "authUrl": auth_url,
            "state": state,
        }

    async def get_access_token(
        self,
        code: str,
        state: str,
        redirect_uri: Optional[str] = None,
    ) -> Dict[str, Any]:
        """인가 코드로 액세스 토큰 발급 (PKCE 지원)"""
        logger.info(f"구글 액세스 토큰 요청: code={code}, state={state}")

        code_verifier: Optional[str] = None
        if state:
            code_verifier = await self.pkce_service.get_and_remove_code_verifier(state)
            if code_verifier:
                logger.info("PKCE Code Verifier 추가됨")
            else:
                logger.warn(f"Code Verifier를 찾을 수 없음: state={state}")

        return await exchange_authorization_code(
            token_url=self.GOOGLE_TOKEN_URL,
            client_id=self.client_id,
            client_secret=self.client_secret,
            redirect_uri=redirect_uri or self.redirect_uri,
            code=code,
            code_verifier=code_verifier,
        )

    async def get_user_info(self, access_token: str) -> Dict[str, Any]:
        """액세스 토큰으로 사용자 정보 조회"""
        logger.info("구글 사용자 정보 조회")

        try:
            response = await self.http_client.get(
                self.GOOGLE_USER_INFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            response.raise_for_status()

            user_info = response.json()
            logger.info(f"구글 사용자 정보 조회 성공: id={user_info.get('id')}")
            return user_info

        except httpx.HTTPError as e:
            logger.error(f"구글 사용자 정보 조회 실패: {e}")
            raise RuntimeError(f"구글 사용자 정보 조회 실패: {e}") from e

    async def process_oauth(self, code: str, state: str) -> Dict[str, Any]:
        """전체 OAuth 플로우 실행 (State 검증 및 PKCE 지원)"""
        state_data = await self.state_service.validate_and_remove_state(state)
        if not state_data:
            raise RuntimeError("State 검증 실패: CSRF 공격 가능성")

        mode = state_data.get("mode")
        client = state_data.get("client")
        redirect_uri = state_data.get("redirect_uri")

        token_response = await self.get_access_token(code, state, redirect_uri=redirect_uri)

        user_info = await self.get_user_info(token_response["access_token"])

        if mode:
            user_info["_mode"] = mode
        if client:
            user_info["_client"] = client

        return user_info
