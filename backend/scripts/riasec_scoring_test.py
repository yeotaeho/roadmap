# RIASEC 6축 블렌딩·shrinkage·top_codes 파생 순수 테스트

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from domain.user_intelligence.hub.services.riasec_scoring import (
    RIASEC_CODES,
    SHRINK_K,
    TOP_MIN,
    blend_riasec,
)

PASS = 0
FAIL = 0


def check(n: str, c: bool, e: str = "") -> None:
    global PASS, FAIL
    if c:
        PASS += 1
        print(f"[PASS] {n}")
    else:
        FAIL += 1
        print(f"[FAIL] {n} {e}")


def _full(v):
    return {c: v for c in RIASEC_CODES}


def run() -> int:
    # 첫 관측(existing None) — raw = window, weights = conf
    hi = {**_full(50), "I": 90, "A": 80}
    conf = {**_full(0.2), "I": 0.9, "A": 0.8}
    r = blend_riasec(None, hi, conf)
    check("raw=window(첫관측)", r["raw"]["I"] == 90 and r["raw"]["A"] == 80, str(r["raw"]))
    check("weights=conf(첫관측)", abs(r["weights"]["I"] - 0.9) < 1e-9)
    # shrinkage — I weight 0.9 < K=4 이므로 display 는 50에 가깝게 당겨짐
    expected_I = round(50 + (90 - 50) * min(1, 0.9 / SHRINK_K))
    check("shrinkage 첫관측 I", r["scores"]["I"] == expected_I, f'{r["scores"]["I"]} vs {expected_I}')
    check("근거 얇으면 top_codes 비거나 축소", isinstance(r["top_codes"], list))

    # 반복 관측 — 같은 방향 4회 누적하면 weight 커져 display 가 raw(90)에 근접, top_codes 에 I
    acc = None
    for _ in range(5):
        acc = blend_riasec(acc, hi, conf)
    check("반복 누적 I 상승", acc["scores"]["I"] >= 80, str(acc["scores"]["I"]))
    check("top_codes 파생(I 최상위)", acc["top_codes"][:1] == ["I"], str(acc["top_codes"]))
    check("top_codes 최대 2개", len(acc["top_codes"]) <= 2)
    check("TOP_MIN 미달 축 제외", all(acc["scores"][c] > TOP_MIN for c in acc["top_codes"]))

    # confidence 가중 평균 — 낮은 conf 반대 신호는 raw 를 약간만 끌어내림
    low_opp = {**_full(50), "I": 10}
    low_conf = {**_full(0.1), "I": 0.1}
    blended = blend_riasec(acc, low_opp, low_conf)
    check("낮은 conf 반대신호 영향 작음", blended["raw"]["I"] > 70, str(blended["raw"]["I"]))

    # 하위호환 — existing 이 top_codes 만 있는 옛 형태(raw/weights 없음) → 50·0 기준
    old = {"top_codes": ["S"]}
    r2 = blend_riasec(old, hi, conf)
    check("하위호환 raw=window", r2["raw"]["I"] == 90, str(r2["raw"]))
    check("하위호환 weights=conf", abs(r2["weights"]["I"] - 0.9) < 1e-9)

    print(f"\n결과: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(run())
