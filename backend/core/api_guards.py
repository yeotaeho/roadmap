# 운영/보안용 공용 FastAPI 의존성 — 내부 토큰 가드·인증 사용자 추출

from __future__ import annotations

import hmac
from typing import Optional

from fastapi import Header, HTTPException

from core.config.settings import get_settings
from domain.auth.hub.security.services.jwt import JWTService


def _verify_internal_token(provided: Optional[str], expected: Optional[str]) -> None:
    """내부 토큰 검증(순수 로직). 불일치 403, 키 미설정 503(fail-closed)."""
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="내부 엔드포인트가 비활성화되어 있습니다 (INTERNAL_API_KEY 미설정).",
        )
    if not provided or not hmac.compare_digest(provided, expected):
        raise HTTPException(status_code=403, detail="유효하지 않은 내부 토큰입니다.")


async def require_internal_token(
    x_internal_token: Optional[str] = Header(default=None, alias="X-Internal-Token"),
) -> None:
    """refine/match 배치 트리거 가드 — X-Internal-Token 헤더를 검증한다."""
    _verify_internal_token(x_internal_token, get_settings().internal_api_key)


async def get_authenticated_user_id(
    authorization: Optional[str] = Header(default=None),
) -> str:
    """Bearer JWT 에서 user_id 를 추출하는 공용 인증 의존성.

    Sync·Chance 등 사용자별 Gold 서빙에서 user_id 를 쿼리로 신뢰하지 않고
    토큰에서 도출해 IDOR 을 차단한다.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="인증 토큰이 없습니다.")
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="잘못된 인증 토큰 형식입니다.")

    token = authorization[7:]
    jwt_service = JWTService()
    user_id = jwt_service.extract_user_id(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="유효하지 않은 토큰입니다.")
    if jwt_service.is_token_expired(token):
        raise HTTPException(status_code=401, detail="토큰이 만료되었습니다.")
    return user_id
