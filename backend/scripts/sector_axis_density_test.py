# 섹터×축 밀도 진단(compute_density_report) 무DB 검증 테스트

from __future__ import annotations

import os
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from domain.market_insight.hub.services.pulse_pipeline import AxisSignal  # noqa: E402
from scripts.sector_axis_density_audit import (  # noqa: E402
    compute_density_report,
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


def _row(report: list[dict], slug: str) -> dict:
    return next(r for r in report if r["sector"] == slug)


D0 = date(2026, 6, 1)


def _daily(slug: str, axis: str, n: int, value: float = 10.0) -> list[AxisSignal]:
    return [AxisSignal(slug, D0 + timedelta(days=i), axis, value) for i in range(n)]


# ---------------------------------------------------------------------------
# 12 섹터 전부 리포트에 포함(신호 없는 섹터도 회색으로 표기)
# ---------------------------------------------------------------------------
def test_covers_all_sectors() -> None:
    report, as_of = compute_density_report(_daily("ai-data", "market", 8))
    slugs = {r["sector"] for r in report}
    check("12 섹터 모두 포함", {"fintech", "mobility", "content-creator",
          "social-service", "logistics", "beauty-fashion"} <= slugs)
    fintech = _row(report, "fintech")
    check("신호 없는 fintech 는 회색", fintech["gray"] is True)
    check("fintech 축 밀도 전부 0", all(v == 0 for v in fintech["axis_window"].values()))


# ---------------------------------------------------------------------------
# 일별 시장 신호(변동 있음) → 게이트 통과(활성), 시장축 밀도 = 일수
# (실데이터는 거래대금이 매일 변동 — 평탄 상수열은 운영에서도 전부 50→insufficient)
# ---------------------------------------------------------------------------
def test_dense_market_active() -> None:
    vals = [10, 12, 9, 15, 11, 14, 8, 16]
    sigs = [AxisSignal("fintech", D0 + timedelta(days=i), "market", float(v))
            for i, v in enumerate(vals)]
    report, as_of = compute_density_report(sigs)
    ft = _row(report, "fintech")
    check("밀집·변동 시장신호 fintech 활성", ft["gray"] is False)
    check("시장축 윈도우 밀도 8", ft["axis_window"]["market"] == 8)
    check("as_of = 최신 날짜", as_of == D0 + timedelta(days=7))


# ---------------------------------------------------------------------------
# 일별이라도 값이 완전 평탄하면 전부 50 → 회색(운영 pulse_overview 와 동일)
# ---------------------------------------------------------------------------
def test_flat_signal_gray() -> None:
    report, _ = compute_density_report(_daily("edutech", "market", 8, value=10.0))
    ed = _row(report, "edutech")
    check("평탄 상수 시장신호 edutech 회색", ed["gray"] is True)


# ---------------------------------------------------------------------------
# 2일치 희소 신호 → 회색(게이트 미달)
# ---------------------------------------------------------------------------
def test_sparse_gray() -> None:
    sigs = [AxisSignal("mobility", D0, "innovation", 5.0),
            AxisSignal("mobility", D0 + timedelta(days=1), "innovation", 5.0)]
    report, _ = compute_density_report(sigs)
    mob = _row(report, "mobility")
    check("희소(2일) mobility 회색", mob["gray"] is True)
    check("혁신축 밀도 2", mob["axis_window"]["innovation"] == 2)


# ---------------------------------------------------------------------------
# 윈도우 경계 — 윈도우 밖 신호는 axis_window 에서 제외, axis_total 엔 포함
# ---------------------------------------------------------------------------
def test_window_filtering() -> None:
    sigs = _daily("logistics", "market", 6)  # D0..D0+5
    old = AxisSignal("logistics", D0 - timedelta(days=40), "economic", 7.0)
    report, as_of = compute_density_report([*sigs, old], window_days=20)
    lg = _row(report, "logistics")
    check("윈도우 밖 economic 은 window 밀도 0", lg["axis_window"]["economic"] == 0)
    check("윈도우 밖 economic 도 total 엔 1", lg["axis_total"]["economic"] == 1)
    check("윈도우 내 market 밀도 6", lg["axis_window"]["market"] == 6)


def main() -> None:
    test_covers_all_sectors()
    test_dense_market_active()
    test_flat_signal_gray()
    test_sparse_gray()
    test_window_filtering()
    print(f"\n{'=' * 40}\nPASS={PASS} FAIL={FAIL}\n{'=' * 40}")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
