# Pulse 결정론적 파이프라인(raw→Silver→Gold) 무DB 검증 테스트

from __future__ import annotations

import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from domain.market_insight.hub.services.pulse_pipeline import (  # noqa: E402
    AxisSignal,
    DEFAULT_AXIS_WEIGHTS,
    SignalInput,
    compute_silver,
    fuse_signals,
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
    # 가산 평활(k=10): (20-10)/(10+10)*100 = 50.0 (평활 전 100.0).
    check("zscore 급등 momentum=50.0(평활)", last.momentum_pct == 50.0)
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
# 희소-0 게이트 — 0으로 도배된 희소 시계열의 거짓 급등 차단(비영 관측 기준)
# ---------------------------------------------------------------------------
def test_sparse_zero_gate() -> None:
    # mobility 실데이터 형태: 19일 0 + 비영 2점. min-max 정규화가 흔한 최소값을 0으로
    # 보내 윈도우가 0으로 도배 → 구 게이트(관측 개수)는 momentum 폭증. 신 게이트(비영 개수)는 중립.
    vals = [0.0] * 19 + [40.0, 66.667]
    last = compute_silver(_series("mobility", vals), baseline_method="zscore", min_history=5)[-1]
    check("희소0 윈도우 최신 score=50", last.normalized_score == 50)
    check("희소0 윈도우 최신 momentum=0", last.momentum_pct == 0.0)
    check("희소0 윈도우 최신 badge=보합", last.status_badge == "보합")
    # 대조: 충분한 비영 이력이면 정상 모멘텀 산출(중립 아님).
    dense = compute_silver(
        _series("ai-data", [10, 11, 9, 10, 12, 11, 20]), baseline_method="zscore", min_history=5
    )[-1]
    check("조밀 비영 이력 = 모멘텀 산출(중립 아님)", dense.normalized_score != 50)


# ---------------------------------------------------------------------------
# 가산 평활 — 작은 비영 기준선의 모멘텀 폭증을 신뢰 범위로 수렴(시장축 형태)
# ---------------------------------------------------------------------------
def test_momentum_smoothing() -> None:
    # 작은 비영값(1.0)으로 도배 + 스파이크(60). 게이트는 통과(비영 6개)하나 base가 작아
    # 평활 전이면 수천%(CAP). 가산 평활로 신뢰 범위(<1000%)로 수렴, 실 급등 방향은 유지.
    vals = [1.0] * 6 + [60.0]
    last = compute_silver(_series("food-agri", vals), baseline_method="zscore", min_history=5)[-1]
    check("가산 평활: 모멘텀 < 1000%(폭증 차단)", last.momentum_pct < 1000.0)
    check("가산 평활: 실 급등 방향 유지(양의 모멘텀)", last.momentum_pct > 50.0)


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
    check("Gold momentum 보존(평활 50.0)", gold[-1].momentum_pct == 50.0)


# ---------------------------------------------------------------------------
# 가중 융합 — 동일 (섹터,일자) 축 합산 + 가중치 + 결정론
# ---------------------------------------------------------------------------
def test_fuse() -> None:
    d = date(2026, 6, 24)
    axis = [
        AxisSignal("ai-data", d, "innovation", 3.0),
        AxisSignal("ai-data", d, "economic", 2.0),
        AxisSignal("ai-data", d, "people", 10.0),  # weight 0.7 → 7.0
        AxisSignal("fintech", date(2026, 6, 1), "economic", 4.0),
    ]
    fused = fuse_signals(axis)  # 기본 가중치 innovation/economic=1.0, people=0.7
    by = {(f.sector_slug, f.reference_date): f.raw_signal_value for f in fused}
    check("융합 ai-data = 3+2+0.7*10 = 12.0", by[("ai-data", d)] == 12.0)
    check("융합 fintech 별도일자 = 4.0", by[("fintech", date(2026, 6, 1))] == 4.0)
    check("융합 행수 2(섹터×일자 그룹)", len(fused) == 2)
    check("융합 가중치 오버라이드", fuse_signals(axis, {"people": 0.0, "innovation": 1.0, "economic": 1.0})[0].raw_signal_value == 5.0)
    check("융합 결정론(정렬 안정)", fuse_signals(axis) == fuse_signals(axis))
    check("융합 빈 입력 = []", fuse_signals([]) == [])


def test_tech_demand_axis_weight() -> None:
    # KIAT 수요기술 tech_demand 축이 가중치 0.5로 융합되는지(미등록 시 기본 1.0).
    check("tech_demand 가중치 0.5 등록", DEFAULT_AXIS_WEIGHTS.get("tech_demand") == 0.5)
    fused = fuse_signals([AxisSignal("ai-data", date(2026, 6, 1), "tech_demand", 10.0)])
    check(
        "tech_demand 융합값=10×0.5=5.0",
        bool(fused) and abs(fused[0].raw_signal_value - 5.0) < 1e-9,
    )


# ---------------------------------------------------------------------------
# 감성·방향 가산 이동(modifier) — 활동 점수 위에 직전 윈도우 평균(-1~1) × K 를 얹는다
# ---------------------------------------------------------------------------
def test_modifier_tilt() -> None:
    flat = _series("ai-data", [5, 5, 5, 5])  # 평탄 → 전부 score 50
    d_last = date(2026, 6, 4)
    up = compute_silver(flat, baseline_method="zscore", modifiers={("ai-data", d_last): 0.4})
    check("modifier +0.4 → score 50+6=56", up[-1].normalized_score == 56)
    dn = compute_silver(flat, baseline_method="zscore", modifiers={("ai-data", d_last): -0.4})
    check("modifier -0.4 → score 50-6=44", dn[-1].normalized_score == 44)
    miss = compute_silver(flat, baseline_method="zscore", modifiers={("fintech", d_last): 0.9})
    check("modifier 키 부재 → 불변(50)", all(r.normalized_score == 50 for r in miss))
    check("modifiers None → 불변(50)", all(r.normalized_score == 50 for r in compute_silver(flat)))
    # 상한 클램프 — zscore 급등(95)에 +1.0 → 95+15=110 → 100.
    jump = _series("ai-data", [10, 10, 10, 10, 12])
    hi = compute_silver(jump, baseline_method="zscore", modifiers={("ai-data", date(2026, 6, 5)): 1.0})
    check("modifier 상한 클램프 100", hi[-1].normalized_score == 100)
    # 하한 클램프 — pct_change 급락(5)에 -1.0 → 5-15=-10 → 0.
    drop = _series("fintech", [100, 50])
    lo = compute_silver(drop, baseline_method="pct_change", modifiers={("fintech", date(2026, 6, 2)): -1.0})
    check("modifier 하한 클램프 0", lo[-1].normalized_score == 0)
    # 배지 재계산 — tilt 가 점수를 85 이상으로 올리면 태풍급(momentum 은 활동 기반 그대로).
    ma = _series("ai-data", [30, 30, 30, 46])  # ma_ratio score 77·momentum 40 → 급상승
    plain = compute_silver(ma, baseline_method="ma_ratio")[-1]
    check("tilt 전 score 77·급상승", plain.normalized_score == 77 and plain.status_badge == "급상승")
    tilted = compute_silver(ma, baseline_method="ma_ratio", modifiers={("ai-data", date(2026, 6, 4)): 0.7})[-1]
    check("tilt 후 score>=85 → 태풍급", tilted.normalized_score >= 85 and tilted.status_badge == "태풍급")
    check("tilt 후에도 momentum 활동 기반 유지", tilted.momentum_pct == plain.momentum_pct)


# ---------------------------------------------------------------------------
# modifier 트레일링 윈도우 — carry-forward·평균·윈도우 이탈
# ---------------------------------------------------------------------------
def test_modifier_trailing_window() -> None:
    flat5 = _series("ai-data", [5, 5, 5, 5, 5])  # 6/1~6/5, 전부 score 50
    # carry-forward — 6/3 modifier 가 같은 날 신호 없는 6/5 에도 직전 윈도우로 반영.
    cf = compute_silver(flat5, baseline_method="zscore", modifiers={("ai-data", date(2026, 6, 3)): 0.4})
    by_date = {r.reference_date: r.normalized_score for r in cf}
    check("carry-forward: 6/5 = 50+6=56", by_date[date(2026, 6, 5)] == 56)
    check("carry-forward: modifier 이전일 6/2 = 불변 50", by_date[date(2026, 6, 2)] == 50)
    # 트레일링 평균 — 같은 윈도우의 +1.0·-1.0 이 상쇄되어 tilt 0.
    avg = compute_silver(
        flat5, baseline_method="zscore",
        modifiers={("ai-data", date(2026, 6, 4)): 1.0, ("ai-data", date(2026, 6, 5)): -1.0},
    )
    check("트레일링 평균: 6/5 = (+1-1)/2=0 → 50", avg[-1].normalized_score == 50)
    # 윈도우 이탈 — 7일 밖 modifier 는 미반영.
    flat10 = _series("ai-data", [5] * 10)  # 6/1~6/10
    fall = compute_silver(
        flat10, baseline_method="zscore",
        modifiers={("ai-data", date(2026, 6, 1)): 0.6}, modifier_window_days=7,
    )
    fd = {r.reference_date: r.normalized_score for r in fall}
    check("윈도우 내(6/7) = 50+9=59", fd[date(2026, 6, 7)] == 59)
    check("윈도우 밖(6/8) = 불변 50", fd[date(2026, 6, 8)] == 50)


def main() -> int:
    test_zscore_jump()
    test_other_methods()
    test_flat()
    test_sparse_zero_gate()
    test_momentum_smoothing()
    test_idempotent()
    test_multi_sector()
    test_badge_tiers()
    test_project_gold()
    test_fuse()
    test_tech_demand_axis_weight()
    test_modifier_tilt()
    test_modifier_trailing_window()
    print(f"\n결과: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
