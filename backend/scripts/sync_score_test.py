# Sync 적합도 산출 순수함수(minmax_normalize·combine_score·badge) 무네트워크 테스트

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

from domain.market_insight.hub.services.sync_refine_service import (  # noqa: E402
    badge,
    combine_score,
    minmax_normalize,
)

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


def test_minmax() -> None:
    out = minmax_normalize([0.1, 0.2, 0.3])
    check("min→0", out[0] == 0.0)
    check("max→100", out[2] == 100.0)
    check("중간값 비례(50)", abs(out[1] - 50.0) < 1e-9)
    check("동일값 → 50 중립", minmax_normalize([0.2, 0.2]) == [50.0, 50.0])
    check("빈 입력 → []", minmax_normalize([]) == [])


def test_combine() -> None:
    # 0.6*aff + 0.4*trend
    check("적합100·트렌드100 → 100", combine_score(100, 100) == 100)
    check("적합100·트렌드0 → 60", combine_score(100, 0) == 60)
    check("적합0·트렌드100 → 40", combine_score(0, 100) == 40)
    check("적합50·트렌드50 → 50", combine_score(50, 50) == 50)
    check("상한 클램프", combine_score(200, 200) == 100)


def test_badge() -> None:
    check("70+ 강한 적합", badge(80) == "강한 적합")
    check("45~69 적합", badge(50) == "적합")
    check("45 미만 약한 적합", badge(30) == "약한 적합")


def main() -> int:
    for fn in (test_minmax, test_combine, test_badge):
        fn()
    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
