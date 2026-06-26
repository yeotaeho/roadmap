# 운영/보안용 공용 FastAPI 의존성 — 내부 토큰 가드·인증 사용자 추출

from __future__ import annotations

import hmac
from typing import Optional

from fastapi import Header, HTTPException

from core.config.settings import get_settings


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
