"""Pulse 산출 결정론적 파이프라인 — raw 신호 → Silver 정규화 → Gold 사영."""

from __future__ import annotations

import bisect
from dataclasses import dataclass
from datetime import date, timedelta
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
# market = 자본 흐름(Yahoo 시장 시계열). 진로 제품의 핵심 '돈의 흐름' 축.
# economic_text = LLM 분류 경제뉴스(코드 미보유분). discourse = LLM 분류 뉴스 담론(노이즈 큰 공급 신호).
DEFAULT_AXIS_WEIGHTS: dict[str, float] = {
    "innovation": 1.0,
    "economic": 1.0,
    "people": 0.7,
    "market": 1.0,
    "economic_text": 1.0,
    "discourse": 0.5,
    "tech_demand": 0.5,  # KIAT 수요기술 — 생산 신호의 보조(추후 튜닝).
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


# 모멘텀(%) 저장 상한. NUMERIC(8,2)(<10^6) 오버플로 방지 + 배지가 50%에서 포화하므로
# 그 이상은 "포화"로 간주해 클램프(희소 베이스라인이 만드는 수백만 % 노이즈 차단).
MOMENTUM_CAP = 9999.99

# 모멘텀 가산 평활(Laplace) 상수. momentum = (value-base)/(base+k)로 분모를 안정화해,
# 작은 기준선(시장축 상대유량 등 0에 가까운 base)이 만드는 거짓 폭증(수천%)을 신뢰 범위로 수렴.
# 정규화 0~100 스케일 기준 "최소 의미 있는 배경 활동" 크기. 클수록 모멘텀이 더 보수적이 된다.
MOMENTUM_SMOOTHING = 10.0


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
    # 가산 평활: 분모에 MOMENTUM_SMOOTHING 을 더해 작은 기준선의 division 폭증을 차단.
    momentum_pct = (value - base) / (base + MOMENTUM_SMOOTHING) * 100.0

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

    momentum_pct = max(-MOMENTUM_CAP, min(MOMENTUM_CAP, momentum_pct))
    return score, round(momentum_pct, 2)


def _trailing_modifier(
    dates: list[date],
    vals: list[float],
    weights: list[float],
    ref_date: date,
    window_days: int,
    shrink_k: float,
) -> float:
    """ref_date 직전 window_days 내 modifier 의 관측수 가중 평균을 shrinkage 보정해 반환(없으면 0.0).

    정확-일자 매칭 대신 트레일링 평균을 써, 최신 활동일이 직전 며칠치 방향을 carry-forward 로
    물려받게 한다(주말·장마감 시차로 같은 날 신호가 없어도 반영). 관측수(weight) 가중으로
    단일 관측일을 덜 반영하고, 총 관측수 W 가 적으면 W/(W+shrink_k) 로 0(중립)을 향해 수축해
    ±1 노이즈(단일 티커·단일 기사)를 억제한다. dates 는 오름차순.
    """
    lo = bisect.bisect_right(dates, ref_date - timedelta(days=window_days))
    hi = bisect.bisect_right(dates, ref_date)
    num = 0.0
    total_w = 0.0
    for i in range(lo, hi):
        num += vals[i] * weights[i]
        total_w += weights[i]
    if total_w <= 0:
        return 0.0
    weighted_avg = num / total_w
    return weighted_avg * (total_w / (total_w + shrink_k))


def compute_silver(
    signals: list[SignalInput],
    window_days: int = 20,
    baseline_method: BaselineMethod = "zscore",
    min_history: int = 0,
    modifiers: dict[tuple[str, date], tuple[float, float]] | None = None,
    sentiment_k: float = 15.0,
    modifier_window_days: int = 7,
    modifier_shrink_k: float = 8.0,
) -> list[PulseSilverRow]:
    """섹터별 시계열을 정규화해 Silver 행 목록을 산출한다. 결정론적·멱등이다.

    min_history: 모멘텀 산출에 필요한 최소 직전 유효(비영) 관측 수. 미만이면 중립(score 50, 보합).
    이력이 희소한 섹터가 거짓 급등(태풍급)을 내는 것을 막는다(운영은 5, 테스트 기본 0).

    modifiers: (섹터, 발생일) → (방향성 value -1~1, 관측수 weight). 활동 점수 위에 sentiment_k 배로
    가산 이동해 감성·시장 방향을 점수에 반영한다(곱셈은 z-score 가 균일 스케일을 상쇄해 정상상태
    심리를 못 반영하므로 가산을 쓴다). 적용은 정확-일자가 아니라 직전 modifier_window_days 일의
    관측수 가중 평균(carry-forward)이며, 총 관측수가 적으면 modifier_shrink_k 로 0 을 향해 수축해
    단일 관측의 ±1 노이즈를 억제한다. 윈도우에 modifier 가 없으면 tilt 0(데이터 없는 섹터 현 동작 유지).
    배지는 tilt 된 점수로 재계산되고, momentum_pct 는 활동 기반 그대로 둔다(차트 '활동 변화율' 유지).
    """
    by_sector: dict[str, list[SignalInput]] = {}
    for sig in signals:
        by_sector.setdefault(sig.sector_slug, []).append(sig)

    # 섹터별 modifier 타임라인(오름차순) — 트레일링 윈도우 가중 평균 조회용.
    mod_timeline: dict[str, tuple[list[date], list[float], list[float]]] = {}
    if modifiers:
        tmp: dict[str, list[tuple[date, float, float]]] = {}
        for (slug, d), (v, w) in modifiers.items():
            tmp.setdefault(slug, []).append((d, v, w))
        for slug, triples in tmp.items():
            triples.sort()
            mod_timeline[slug] = (
                [t[0] for t in triples],
                [t[1] for t in triples],
                [t[2] for t in triples],
            )

    rows: list[PulseSilverRow] = []
    for sector, items in by_sector.items():
        ordered = sorted(items, key=lambda x: x.reference_date)
        timeline = mod_timeline.get(sector)
        for i, cur in enumerate(ordered):
            window = [p.raw_signal_value for p in ordered[max(0, i - window_days):i]]
            # 유효(비영) 관측 기준 게이트 — min-max 정규화가 흔한 최소값을 0으로 보내
            # 0으로 도배된 희소 섹터가 거의-0 기준선으로 거짓 급등(수천%)을 내는 것을 차단.
            nonzero = [w for w in window if w > 0]
            if len(nonzero) < min_history:
                score, momentum_pct = 50, 0.0  # 유효 이력 부족 → 중립
            else:
                score, momentum_pct = _normalize(cur.raw_signal_value, window, baseline_method)
            # 감성·방향 가산 이동 — 직전 윈도우 관측수 가중 modifier(-1~1)×K 를 점수에 얹는다.
            if timeline is not None:
                tilt = _trailing_modifier(
                    timeline[0], timeline[1], timeline[2],
                    cur.reference_date, modifier_window_days, modifier_shrink_k,
                )
                if tilt:
                    score = _clamp(score + sentiment_k * tilt)
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
