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
    AFFINITY_HI,
    AFFINITY_LO,
    badge,
    combine_score,
    has_sufficient_signal,
    scale_affinity,
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


def test_scale_affinity() -> None:
    # 전역 절대 스케일 — 사용자별 스트레치 없음.
    check("LO 이하 → 0", scale_affinity(AFFINITY_LO - 0.1) == 0.0)
    check("HI 이상 → 100", scale_affinity(AFFINITY_HI + 0.1) == 100.0)
    check("중점 → 50", abs(scale_affinity((AFFINITY_LO + AFFINITY_HI) / 2) - 50.0) < 1e-9)
    # 빈약한 밴드(0.18~0.21)가 더 이상 0~100으로 늘어나지 않음 — 핵심 회귀.
    lo_pct = scale_affinity(0.18)
    hi_pct = scale_affinity(0.21)
    check("빈약 밴드는 좁게 유지(스트레치 방지)", (hi_pct - lo_pct) < 15)
    check("빈약 밴드 상단도 강한적합 아님(<70)", hi_pct < 70)


def test_sufficiency() -> None:
    check("스프레드 충분 → True", has_sufficient_signal([0.1, 0.2, 0.35]) is True)
    check("razor-thin 밴드 → False", has_sufficient_signal([0.18, 0.19, 0.20]) is False)
    check("단일 섹터 → False", has_sufficient_signal([0.3]) is False)
    check("빈 입력 → False", has_sufficient_signal([]) is False)


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
    for fn in (test_scale_affinity, test_sufficiency, test_combine, test_badge):
        fn()
    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
