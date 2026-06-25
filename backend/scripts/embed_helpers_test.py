# 임베딩 헬퍼(vec_literal·_user_text) 무네트워크 결정론적 테스트

from __future__ import annotations

import os
import sys

for _k, _v in dict(
    NEON_DATABASE_URL="postgresql+asyncpg://u:p@localhost/db",
    JWT_SECRET="x",
    NAVER_CLIENT_ID="x",
    NAVER_CLIENT_SECRET="x",
    NAVER_REDIRECT_URI="x",
).items():
    os.environ.setdefault(_k, _v)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from domain.market_insight.hub.repositories.embed_repository import vec_literal  # noqa: E402
from domain.market_insight.hub.services.embed_service import UserEmbedService  # noqa: E402

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


def test_vec_literal() -> None:
    check("벡터 직렬화 형식", vec_literal([1.0, 2.5, -3.0]) == "[1.0,2.5,-3.0]")
    check("정수→실수 직렬화", vec_literal([0, 1]) == "[0.0,1.0]")
    check("빈 벡터", vec_literal([]) == "[]")


def test_user_text() -> None:
    check(
        "직무+관심 결합",
        UserEmbedService._user_text("데이터 분석가", ["AI", "핀테크"]) == "데이터 분석가 AI 핀테크",
    )
    check("관심만(직무 None)", UserEmbedService._user_text(None, ["AI"]) == "AI")
    check("빈 입력 → 플레이스홀더", UserEmbedService._user_text(None, []) == "_")
    check("비-리스트 관심 무시", UserEmbedService._user_text("기획자", None) == "기획자")


def main() -> int:
    for fn in (test_vec_literal, test_user_text):
        fn()
    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
