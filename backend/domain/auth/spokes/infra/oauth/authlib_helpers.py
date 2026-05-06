"""
OAuth2 인가 URL 생성 · 토큰 엔드포인트 교환만 Authlib 사용.

Redis(state/PKCE)·JWT·User ORM 은 기존 코드 경로를 유지한다.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from authlib.integrations.base_client import OAuthError
from authlib.integrations.httpx_client import AsyncOAuth2Client
from authlib.oauth2.client import OAuth2Client

logger = logging.getLogger(__name__)


def oauth2_client_for_authorization(
    *,
    client_id: str,
    client_secret: Optional[str],
    redirect_uri: str,
    scope: Optional[str],
    code_challenge_method: Optional[str] = None,
) -> OAuth2Client:
    """인가 화면 URL만 필요할 때 (세션 없이 OAuth2Client)."""
    secret = client_secret or None
    return OAuth2Client(
        None,
        client_id=client_id,
        client_secret=secret,
        redirect_uri=redirect_uri,
        scope=scope,
        code_challenge_method=code_challenge_method,
        token_endpoint_auth_method="client_secret_post" if secret else "none",
    )


async def exchange_authorization_code(
    *,
    token_url: str,
    client_id: str,
    client_secret: Optional[str],
    redirect_uri: str,
    code: str,
    code_verifier: Optional[str] = None,
    state: Optional[str] = None,
    timeout: float = 30.0,
) -> Dict[str, Any]:
    """Authorization code → 액세스 토큰 (PKCE verifier·state 는 프로바이더별 선택)."""
    secret = client_secret or None
    auth_method = "client_secret_post" if secret else "none"

    params: Dict[str, Any] = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
    }
    if code_verifier is not None:
        params["code_verifier"] = code_verifier
    if state is not None:
        params["state"] = state

    try:
        async with AsyncOAuth2Client(
            client_id=client_id,
            client_secret=secret,
            redirect_uri=redirect_uri,
            token_endpoint_auth_method=auth_method,
            timeout=timeout,
        ) as client:
            token = await client.fetch_token(token_url, **params)
    except OAuthError as e:
        logger.error("Authlib token exchange failed: %s", e)
        raise RuntimeError(f"OAuth token exchange failed: {e}") from e

    return dict(token)
