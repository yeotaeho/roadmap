"""Pulse 산출 결정론적 파이프라인 — raw 신호 → Silver 정규화 → Gold 사영."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from statistics import mean, pstdev
from typing import Literal

BaselineMethod = Literal["zscore", "pct_change", "ma_ratio"]

# status_badge 닫힌 집합 (프론트 표시 분기와 동기화 대상).
BADGE_TYPHOON = "태풍급"
BADGE_SURGE = "급상승"
BADGE_UP = "상승"
BADGE_FLAT = "보합"
BADGE_DOWN = "하락"


@dataclass(frozen=True)
class SignalInput:
    """섹터×일자 단위로 집계된 raw 합성 신호값. raw_* 출처 매핑은 호출측 책임이다."""

    sector_slug: str
    reference_date: date
    raw_signal_value: float


@dataclass(frozen=True)
class AxisSignal:
    """축(innovation/economic/people)별 섹터×일자 신호. 가중 융합의 입력."""

    sector_slug: str
    reference_date: date
    axis: str
    value: float


# 축별 융합 가중치. 합성 신호값 = Σ weight[axis] × value.
DEFAULT_AXIS_WEIGHTS: dict[str, float] = {
    "innovation": 1.0,
    "economic": 1.0,
    "people": 0.7,
}


@dataclass(frozen=True)
class PulseSilverRow:
    """refined_pulse_metric_silver 1행에 대응하는 결정론적 산출 결과."""

    sector_slug: str
    reference_date: date
    raw_signal_value: float
    normalized_score: int
    momentum_pct: float
    status_badge: str
    window_days: int
    baseline_method: str


@dataclass(frozen=True)
class PulseGoldRow:
    """pulse_metrics_log 1행 — Silver의 단순 사영."""

    sector_slug: str
    recorded_date: date
    score: int
    status_badge: str
    momentum_pct: float


def _clamp(value: float, lo: int = 0, hi: int = 100) -> int:
    return int(max(lo, min(hi, round(value))))


def _badge(momentum_pct: float, score: int) -> str:
    if score >= 85 or momentum_pct >= 50:
        return BADGE_TYPHOON
    if momentum_pct >= 20:
        return BADGE_SURGE
    if momentum_pct >= 5:
        return BADGE_UP
    if momentum_pct > -5:
        return BADGE_FLAT
    return BADGE_DOWN


def _normalize(value: float, window: list[float], method: str) -> tuple[int, float]:
    """창(window) 기준선 대비 정규화. (normalized_score, momentum_pct)를 반환한다."""
    base = mean(window) if window else value
    momentum_pct = ((value - base) / base * 100.0) if base else 0.0

    if method == "zscore":
        sd = pstdev(window) if len(window) >= 2 else 0.0
        if sd:
            z = (value - base) / sd
        else:
            # 변동성 0인데 값이 변하면 강신호로 처리 (방향만 반영, 결정론적).
            z = 0.0 if value == base else (3.0 if value > base else -3.0)
        score = _clamp(50 + 15 * z)
    elif method == "ma_ratio":
        ratio = (value / base) if base else 1.0
        score = _clamp(50 * ratio)
    else:  # pct_change
        score = _clamp(50 + momentum_pct)

    return score, round(momentum_pct, 2)


def compute_silver(
    signals: list[SignalInput],
    window_days: int = 20,
    baseline_method: BaselineMethod = "zscore",
) -> list[PulseSilverRow]:
    """섹터별 시계열을 정규화해 Silver 행 목록을 산출한다. 결정론적·멱등이다."""
    by_sector: dict[str, list[SignalInput]] = {}
    for sig in signals:
        by_sector.setdefault(sig.sector_slug, []).append(sig)

    rows: list[PulseSilverRow] = []
    for sector, items in by_sector.items():
        ordered = sorted(items, key=lambda x: x.reference_date)
        for i, cur in enumerate(ordered):
            window = [p.raw_signal_value for p in ordered[max(0, i - window_days):i]]
            score, momentum_pct = _normalize(cur.raw_signal_value, window, baseline_method)
            rows.append(
                PulseSilverRow(
                    sector_slug=sector,
                    reference_date=cur.reference_date,
                    raw_signal_value=cur.raw_signal_value,
                    normalized_score=score,
                    momentum_pct=momentum_pct,
                    status_badge=_badge(momentum_pct, score),
                    window_days=window_days,
                    baseline_method=baseline_method,
                )
            )
    return rows


def project_to_gold(silver_rows: list[PulseSilverRow]) -> list[PulseGoldRow]:
    """Silver → Gold(pulse_metrics_log) 단순 사영. Gold는 계산을 추가하지 않는다."""
    return [
        PulseGoldRow(
            sector_slug=r.sector_slug,
            recorded_date=r.reference_date,
            score=r.normalized_score,
            status_badge=r.status_badge,
            momentum_pct=r.momentum_pct,
        )
        for r in silver_rows
    ]


def fuse_signals(
    axis_signals: list[AxisSignal],
    weights: dict[str, float] | None = None,
) -> list[SignalInput]:
    """여러 축 신호를 (섹터, 일자)로 가중 합산해 단일 합성 신호로 융합한다. 결정론적."""
    w = weights or DEFAULT_AXIS_WEIGHTS
    agg: dict[tuple[str, date], float] = {}
    for a in axis_signals:
        key = (a.sector_slug, a.reference_date)
        agg[key] = agg.get(key, 0.0) + w.get(a.axis, 1.0) * a.value
    return [
        SignalInput(sector_slug=k[0], reference_date=k[1], raw_signal_value=round(v, 6))
        for k, v in sorted(agg.items())
    ]
