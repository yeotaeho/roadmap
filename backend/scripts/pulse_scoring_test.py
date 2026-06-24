# Pulse 결정론적 파이프라인(raw→Silver→Gold) 무DB 검증 테스트

from __future__ import annotations

import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from domain.market_insight.hub.services.pulse_pipeline import (  # noqa: E402
    SignalInput,
    compute_silver,
    project_to_gold,
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


def _series(slug: str, values: list[float]) -> list[SignalInput]:
    return [
        SignalInput(slug, date(2026, 6, 1 + i), v) for i, v in enumerate(values)
    ]


# ---------------------------------------------------------------------------
# zscore — 평탄 후 급등
# ---------------------------------------------------------------------------
def test_zscore_jump() -> None:
    rows = compute_silver(_series("ai-data", [10, 10, 10, 10, 20]), baseline_method="zscore")
    check("zscore 행 5개", len(rows) == 5)
    check("zscore 첫 행 score=50/보합", rows[0].normalized_score == 50 and rows[0].status_badge == "보합")
    last = rows[-1]
    check("zscore 급등 score=95", last.normalized_score == 95)
    check("zscore 급등 momentum=100.0", last.momentum_pct == 100.0)
    check("zscore 급등 badge=태풍급", last.status_badge == "태풍급")


# ---------------------------------------------------------------------------
# pct_change / ma_ratio — 동일 급등 시리즈
# ---------------------------------------------------------------------------
def test_other_methods() -> None:
    pct = compute_silver(_series("ai-data", [10, 10, 10, 10, 20]), baseline_method="pct_change")
    check("pct_change 급등 score=100", pct[-1].normalized_score == 100)
    check("pct_change 급등 badge=태풍급", pct[-1].status_badge == "태풍급")

    mar = compute_silver(_series("ai-data", [10, 10, 10, 10, 20]), baseline_method="ma_ratio")
    check("ma_ratio 급등 score=100(2배)", mar[-1].normalized_score == 100)


# ---------------------------------------------------------------------------
# 평탄 시계열 — 전부 중립
# ---------------------------------------------------------------------------
def test_flat() -> None:
    rows = compute_silver(_series("fintech", [5, 5, 5, 5]), baseline_method="zscore")
    check("평탄 전부 score=50", all(r.normalized_score == 50 for r in rows))
    check("평탄 전부 badge=보합", all(r.status_badge == "보합" for r in rows))


# ---------------------------------------------------------------------------
# 멱등성 — 동일 입력 동일 출력
# ---------------------------------------------------------------------------
def test_idempotent() -> None:
    sig = _series("ai-data", [10, 12, 9, 30])
    check("멱등: 동일 입력 동일 출력", compute_silver(sig) == compute_silver(sig))


# ---------------------------------------------------------------------------
# 섹터 독립 — 섹터별 창이 분리됨
# ---------------------------------------------------------------------------
def test_multi_sector() -> None:
    signals = [
        SignalInput("ai-data", date(2026, 6, 1), 10),
        SignalInput("fintech", date(2026, 6, 1), 100),
        SignalInput("ai-data", date(2026, 6, 2), 20),
        SignalInput("fintech", date(2026, 6, 2), 50),
    ]
    rows = compute_silver(signals, baseline_method="zscore")
    ai = [r for r in rows if r.sector_slug == "ai-data"][-1]
    fin = [r for r in rows if r.sector_slug == "fintech"][-1]
    check("섹터독립 ai-data 급등 score=95", ai.normalized_score == 95)
    check("섹터독립 fintech 급락 score=5/하락", fin.normalized_score == 5 and fin.status_badge == "하락")


# ---------------------------------------------------------------------------
# badge 티어 — 급상승/상승 경계
# ---------------------------------------------------------------------------
def test_badge_tiers() -> None:
    surge = compute_silver(_series("edutech", [100, 125]), baseline_method="pct_change")
    check("badge 급상승(+25%)", surge[-1].status_badge == "급상승")
    up = compute_silver(_series("edutech", [100, 110]), baseline_method="pct_change")
    check("badge 상승(+10%)", up[-1].status_badge == "상승")


# ---------------------------------------------------------------------------
# Gold 사영 — Silver와 1:1, 값 보존
# ---------------------------------------------------------------------------
def test_project_gold() -> None:
    silver = compute_silver(_series("ai-data", [10, 10, 10, 10, 20]), baseline_method="zscore")
    gold = project_to_gold(silver)
    check("Gold 길이 = Silver 길이", len(gold) == len(silver))
    check("Gold recorded_date=Silver reference_date", gold[-1].recorded_date == date(2026, 6, 5))
    check("Gold score=Silver normalized_score", gold[-1].score == silver[-1].normalized_score)
    check("Gold momentum 보존", gold[-1].momentum_pct == 100.0)


def main() -> int:
    test_zscore_jump()
    test_other_methods()
    test_flat()
    test_idempotent()
    test_multi_sector()
    test_badge_tiers()
    test_project_gold()
    print(f"\n결과: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
