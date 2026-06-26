# 내부 토큰 가드(_verify_internal_token) 무네트워크 검증 테스트

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import HTTPException  # noqa: E402

from core.api_guards import _verify_internal_token  # noqa: E402

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


def _status(provided, expected) -> int | None:
    """검증을 실행하고 HTTPException.status_code 를 반환(통과 시 None)."""
    try:
        _verify_internal_token(provided, expected)
        return None
    except HTTPException as e:
        return e.status_code


def test_key_unset_fail_closed() -> None:
    check("키 미설정(None)→503", _status("anything", None) == 503)
    check("키 미설정(빈문자열)→503", _status("anything", "") == 503)


def test_missing_token() -> None:
    check("토큰 누락(None)→403", _status(None, "secret") == 403)
    check("토큰 빈문자열→403", _status("", "secret") == 403)


def test_wrong_token() -> None:
    check("틀린 토큰→403", _status("wrong", "secret") == 403)
    check("대소문자 불일치→403", _status("SECRET", "secret") == 403)


def test_correct_token() -> None:
    check("정확한 토큰→통과(None)", _status("secret", "secret") is None)


def main() -> int:
    test_key_unset_fail_closed()
    test_missing_token()
    test_wrong_token()
    test_correct_token()
    print(f"\n결과: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
