# 공용 인증 의존성(get_authenticated_user_id) 무네트워크 검증 테스트

from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import jwt as pyjwt  # noqa: E402
from fastapi import HTTPException  # noqa: E402

from core.api_guards import get_authenticated_user_id  # noqa: E402
from domain.auth.hub.security.services.jwt import JWTService  # noqa: E402

PASS = 0
FAIL = 0


def check(name: str, cond: bool) -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"[PASS] {name}")
    else:
        FAIL += 1
        print(f"[FAIL] {name}")


def _call(authorization):
    """의존성을 실행하고 (user_id, status_code) 반환 — 예외 시 user_id=None."""
    try:
        uid = asyncio.run(get_authenticated_user_id(authorization=authorization))
        return uid, None
    except HTTPException as e:
        return None, e.status_code


def test_valid_token() -> None:
    svc = JWTService()
    token = svc.generate_token("user-123", "google", "a@b.com", "테스터")
    uid, status = _call(f"Bearer {token}")
    check("정상 토큰→user_id 추출", uid == "user-123" and status is None)


def test_missing_header() -> None:
    uid, status = _call(None)
    check("헤더 없음→401", status == 401)


def test_bad_format() -> None:
    uid, status = _call("Token abc")
    check("Bearer 아님→401", status == 401)


def test_garbage_token() -> None:
    uid, status = _call("Bearer not-a-jwt")
    check("깨진 토큰→401", status == 401)


def test_expired_token() -> None:
    svc = JWTService()
    past = datetime.utcnow() - timedelta(hours=1)
    payload = {"userId": "user-9", "sub": "user-9", "exp": past, "iat": past}
    token = pyjwt.encode(payload, svc._get_secret_key(), algorithm=JWTService.ALGORITHM)
    uid, status = _call(f"Bearer {token}")
    check("만료 토큰→401", status == 401)


def main() -> int:
    test_valid_token()
    test_missing_header()
    test_bad_format()
    test_garbage_token()
    test_expired_token()
    print(f"\n결과: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
