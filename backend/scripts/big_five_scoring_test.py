# Big Five 5축 블렌딩·K=8 shrinkage·하위호환 순수 테스트

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from domain.user_intelligence.hub.services.riasec_scoring import (
    BIGFIVE_CODES,
    BIGFIVE_SHRINK_K,
    blend_big_five,
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
    return {c: v for c in BIGFIVE_CODES}


def run() -> int:
    check("코드 OCEAN", BIGFIVE_CODES == ("O", "C", "E", "A", "N"))
    check("K=8", BIGFIVE_SHRINK_K == 8)

    hi = {**_full(50), "C": 90, "N": 20}
    conf = {**_full(0.2), "C": 0.9, "N": 0.8}
    r = blend_big_five(None, hi, conf)
    check("첫관측 raw=window", r["raw"]["C"] == 90 and r["raw"]["N"] == 20, str(r["raw"]))
    check("top_codes 없음", "top_codes" not in r, str(r.keys()))
    check("5축 존재", set(r["scores"].keys()) == set(BIGFIVE_CODES))
    # K=8 이므로 첫 관측(weight 0.9)은 RIASEC(K=4)보다 더 강하게 50 방향 shrink
    expected_C = round(50 + (90 - 50) * min(1, 0.9 / BIGFIVE_SHRINK_K))
    check("K=8 shrinkage C", r["scores"]["C"] == expected_C, f'{r["scores"]["C"]} vs {expected_C}')

    # 반복 누적 8회면 weight 커져 C 가 raw(90)에 근접
    acc = None
    for _ in range(8):
        acc = blend_big_five(acc, hi, conf)
    check("반복 누적 C 상승", acc["scores"]["C"] >= 80, str(acc["scores"]["C"]))
    check("반복 누적 N 하강", acc["scores"]["N"] <= 30, str(acc["scores"]["N"]))

    # 하위호환 — existing None(빈 big_five)
    check("None existing raw=window", blend_big_five(None, hi, conf)["raw"]["C"] == 90)
    # 옛/누락 형태(raw/weights 없음) → 50·0 취급
    check("누락형태 하위호환", blend_big_five({"foo": 1}, hi, conf)["raw"]["C"] == 90)

    print(f"\n결과: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(run())
