# 자기모델 추출 응답 순수 파서 테스트 — RIASEC 6축 점수·confidence 클램프·dimension 닫힌집합.

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SCHEDULER_ENABLED", "false")

from core.llm.client import _parse_self_model_extract

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


def run() -> int:
    ok = _parse_self_model_extract(json.dumps({
        "riasec_scores": {"R": -5, "I": 120, "A": 80, "S": 40, "E": 55, "C": 30},
        "riasec_axis_confidence": {"R": 0.1, "I": 1.5, "A": 0.8, "S": 0.4, "E": 0.5, "C": 0.2},
        "narrative": "  탐구·표현 지향  ",
        "evidence": [
            {"dimension": "like", "polarity": "like", "content": "발표를 좋아함", "confidence": 0.9, "is_sensitive": False},
            {"dimension": "unknown_dim", "polarity": "??", "content": "x", "confidence": 2.0, "is_sensitive": True},
            {"dimension": "value", "polarity": None, "content": "  ", "confidence": 0.5, "is_sensitive": False},
        ],
    }))
    check("scores 6키", set(ok["riasec_scores"].keys()) == {"R", "I", "A", "S", "E", "C"}, str(ok["riasec_scores"]))
    check("scores 클램프 0~100", ok["riasec_scores"]["R"] == 0 and ok["riasec_scores"]["I"] == 100, str(ok["riasec_scores"]))
    check("axis_conf 클램프 0~1", ok["riasec_axis_confidence"]["I"] == 1.0 and ok["riasec_axis_confidence"]["R"] == 0.1)
    check("narrative strip", ok["narrative"] == "탐구·표현 지향")
    # content 있으면 유지(dimension 닫힌집합 외는 'other' 로 보정될 뿐 드롭 아님) — 빈 content 만 드롭.
    check(
        "evidence 빈 content만 드롭(2건, dimension 보정)",
        len(ok["evidence"]) == 2
        and ok["evidence"][0]["content"] == "발표를 좋아함"
        and ok["evidence"][1]["dimension"] == "other"
        and ok["evidence"][1]["polarity"] is None,
        str(ok["evidence"]),
    )

    # 누락 키 → score 50·conf 0
    partial = _parse_self_model_extract(json.dumps({"riasec_scores": {"I": 70}}))
    check("누락 축 score 50", partial["riasec_scores"]["R"] == 50, str(partial["riasec_scores"]))
    check("누락 축 conf 0", partial["riasec_axis_confidence"]["R"] == 0.0)
    check("있는 축 반영", partial["riasec_scores"]["I"] == 70)

    # 비JSON·비dict → 전 축 50·conf 0·narrative None·evidence []
    empty = _parse_self_model_extract("not json")
    check("비JSON scores 50", all(v == 50 for v in empty["riasec_scores"].values()), str(empty["riasec_scores"]))
    check("비JSON conf 0", all(v == 0.0 for v in empty["riasec_axis_confidence"].values()))
    check("비JSON narrative None", empty["narrative"] is None and empty["evidence"] == [])

    print(f"\n결과: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(run())
