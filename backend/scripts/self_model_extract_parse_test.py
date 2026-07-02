# 자기모델 추출 응답 순수 파서 테스트 — RIASEC 필터·confidence 클램프·dimension 닫힌집합

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
        "riasec_top_codes": ["I", "A", "Z"], "riasec_confidence": 1.5,
        "narrative": "탐구·표현 지향",
        "evidence": [
            {"dimension": "like", "polarity": "like", "content": "발표를 좋아함", "confidence": 0.8},
            {"dimension": "weird", "content": "장거리 통근 싫음", "is_sensitive": True},
            {"dimension": "value", "content": "  ", "confidence": 0.5},
        ],
    }))
    check("RIASEC 유효코드만", ok["riasec_top_codes"] == ["I", "A"], str(ok["riasec_top_codes"]))
    check("confidence 클램프", ok["riasec_confidence"] == 1.0)
    check("narrative", ok["narrative"] == "탐구·표현 지향")
    check("dimension 닫힌집합 보정", ok["evidence"][1]["dimension"] == "other")
    check("is_sensitive 유지", ok["evidence"][1]["is_sensitive"] is True)
    check("빈 content 드롭", len(ok["evidence"]) == 2, str(ok["evidence"]))

    empty = _parse_self_model_extract("not json")
    check("파싱불가 빈결과", empty == {"riasec_top_codes": [], "riasec_confidence": 0.0, "narrative": None, "evidence": []})

    nocode = _parse_self_model_extract(json.dumps({"riasec_top_codes": [], "riasec_confidence": 0.9}))
    check("코드 없으면 confidence 0", nocode["riasec_confidence"] == 0.0)

    print(f"\n결과: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(run())
