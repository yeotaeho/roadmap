# RIASEC·Big Five 축 점수 블렌딩 — confidence 가중 증분 평균 + shrinkage(순수·결정론)

from __future__ import annotations

RIASEC_CODES = ("R", "I", "A", "S", "E", "C")
NEUTRAL = 50.0
SHRINK_K = 4.0   # 누적 가중치가 이 값에 이르면 raw 를 완전 표현(그 전엔 50 방향 shrink)
TOP_MIN = 55     # display 점수가 이 값 초과인 축만 top_codes 후보

BIGFIVE_CODES = ("O", "C", "E", "A", "N")
BIGFIVE_SHRINK_K = 8.0   # 성격은 흥미보다 짧은 대화에서 신뢰도 낮음 → RIASEC(4)보다 강한 shrinkage


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _axis(d: dict | None, key: str, default: float) -> float:
    """dict 에서 축 값 안전 추출(비dict·누락·비수치는 default)."""
    if not isinstance(d, dict):
        return default
    v = d.get(key)
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def blend_axes(
    existing: dict | None, window_scores: dict, window_conf: dict, codes: tuple, shrink_k: float
) -> dict:
    """축 집합에 대한 confidence 가중 증분 평균 + shrinkage. 순수·결정론.

    반환: {"scores": {int, shrink 적용}, "raw": {float}, "weights": {float}}.
    existing 의 raw/weights 가 없거나 옛 형태여도 중립 50·0 으로 취급(하위호환).
    """
    prev_raw = existing.get("raw") if isinstance(existing, dict) else None
    prev_w = existing.get("weights") if isinstance(existing, dict) else None

    raw: dict[str, float] = {}
    weights: dict[str, float] = {}
    scores: dict[str, int] = {}
    for c in codes:
        s_prev = _axis(prev_raw, c, NEUTRAL)
        w_prev = _axis(prev_w, c, 0.0)
        s_win = _clamp(_axis(window_scores, c, NEUTRAL), 0.0, 100.0)
        w_win = _clamp(_axis(window_conf, c, 0.0), 0.0, 1.0)
        w_new = w_prev + w_win
        s_new = (s_prev * w_prev + s_win * w_win) / w_new if w_new > 0 else NEUTRAL
        raw[c] = s_new
        weights[c] = w_new
        shrunk = NEUTRAL + (s_new - NEUTRAL) * min(1.0, w_new / shrink_k)
        scores[c] = int(round(_clamp(shrunk, 0.0, 100.0)))
    return {"scores": scores, "raw": raw, "weights": weights}


def blend_riasec(existing_riasec: dict | None, window_scores: dict, window_conf: dict) -> dict:
    """RIASEC 6축 블렌딩 + top_codes 파생(점수 순위 상위 2, 55 초과). 하위호환 유지."""
    out = blend_axes(existing_riasec, window_scores, window_conf, RIASEC_CODES, SHRINK_K)
    ranked = sorted(RIASEC_CODES, key=lambda c: out["scores"][c], reverse=True)
    out["top_codes"] = [c for c in ranked if out["scores"][c] > TOP_MIN][:2]
    return out


def blend_big_five(existing_big_five: dict | None, window_scores: dict, window_conf: dict) -> dict:
    """Big Five 5축(OCEAN) 블렌딩. N은 canonical(높을수록 신경성) — flip 없음. top_codes 없음."""
    return blend_axes(existing_big_five, window_scores, window_conf, BIGFIVE_CODES, BIGFIVE_SHRINK_K)
