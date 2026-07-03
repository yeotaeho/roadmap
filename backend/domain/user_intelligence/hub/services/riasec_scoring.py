# RIASEC 6축 점수 블렌딩 — confidence 가중 증분 평균 + shrinkage + top_codes 파생(순수·결정론)

from __future__ import annotations

RIASEC_CODES = ("R", "I", "A", "S", "E", "C")
NEUTRAL = 50.0
SHRINK_K = 4.0   # 누적 가중치가 이 값에 이르면 raw 를 완전 표현(그 전엔 50 방향 shrink)
TOP_MIN = 55     # display 점수가 이 값 초과인 축만 top_codes 후보


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


def blend_riasec(existing_riasec: dict | None, window_scores: dict, window_conf: dict) -> dict:
    """기존 축별 누적(raw·weights)에 이번 창의 6축 점수를 confidence 가중으로 병합한다.

    반환: {"scores": {6키 int, shrink 적용}, "raw": {6키 float}, "weights": {6키 float}, "top_codes": [코드...]}.
    existing 이 옛 형태({top_codes}만)여도 raw/weights 를 중립·0 으로 취급해 하위호환.
    """
    prev_raw = existing_riasec.get("raw") if isinstance(existing_riasec, dict) else None
    prev_w = existing_riasec.get("weights") if isinstance(existing_riasec, dict) else None

    raw: dict[str, float] = {}
    weights: dict[str, float] = {}
    scores: dict[str, int] = {}
    for c in RIASEC_CODES:
        s_prev = _axis(prev_raw, c, NEUTRAL)
        w_prev = _axis(prev_w, c, 0.0)
        s_win = _clamp(_axis(window_scores, c, NEUTRAL), 0.0, 100.0)
        w_win = _clamp(_axis(window_conf, c, 0.0), 0.0, 1.0)
        w_new = w_prev + w_win
        s_new = (s_prev * w_prev + s_win * w_win) / w_new if w_new > 0 else NEUTRAL
        raw[c] = s_new
        weights[c] = w_new
        shrunk = NEUTRAL + (s_new - NEUTRAL) * min(1.0, w_new / SHRINK_K)
        scores[c] = int(round(_clamp(shrunk, 0.0, 100.0)))

    ranked = sorted(RIASEC_CODES, key=lambda c: scores[c], reverse=True)
    top_codes = [c for c in ranked if scores[c] > TOP_MIN][:2]
    return {"scores": scores, "raw": raw, "weights": weights, "top_codes": top_codes}
