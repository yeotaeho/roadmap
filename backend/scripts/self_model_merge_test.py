# 자기모델 병합 규칙 순수 단위 테스트 — user_form 우위·confidence 게이팅·빈 축 채움

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SCHEDULER_ENABLED", "false")

from domain.user_intelligence.hub.services.self_model_service import merge_structured

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
    # 1. 빈 상태 + consult 고신뢰 → 기록
    r = merge_structured(None, {"riasec": {"top_codes": ["I"]}, "axis_confidence": {"riasec": 0.7}}, "consult_extraction")
    check("consult 고신뢰 기록", r["riasec"] == {"top_codes": ["I"]})
    check("source consult", r["source"] == "consult_extraction")

    # 2. consult 저신뢰 → 보류(값 미기록, 신뢰도만 반영)
    r = merge_structured(None, {"riasec": {"top_codes": ["I"]}, "axis_confidence": {"riasec": 0.2}}, "consult_extraction")
    check("저신뢰 값 보류", r["riasec"] is None)
    check("저신뢰 신뢰도 반영", (r["axis_confidence"] or {}).get("riasec") == 0.2)

    # 3. user_form 우위 — 기존 user_form 을 consult 가 못 덮음
    existing = {"riasec": {"top_codes": ["A"]}, "source": "user_form", "axis_confidence": {"riasec": 1.0}}
    r = merge_structured(existing, {"riasec": {"top_codes": ["I"]}, "axis_confidence": {"riasec": 0.9}}, "consult_extraction")
    check("user_form 우위 유지", r["riasec"] == {"top_codes": ["A"]})
    check("source user_form 유지", r["source"] == "user_form")

    # 4. user_form 은 기존 consult 를 덮음
    existing = {"riasec": {"top_codes": ["A"]}, "source": "consult_extraction"}
    r = merge_structured(existing, {"riasec": {"top_codes": ["I"]}}, "user_form")
    check("user_form 덮어쓰기", r["riasec"] == {"top_codes": ["I"]})
    check("source→user_form", r["source"] == "user_form")

    # 5. 빈 축만 consult 채움 (기존 user_form 은 riasec 만, big_five 없음)
    existing = {"riasec": {"top_codes": ["A"]}, "source": "user_form"}
    r = merge_structured(existing, {"big_five": {"openness": 70}, "axis_confidence": {"big_five": 0.8}}, "consult_extraction")
    check("빈 축 consult 채움", r["big_five"] == {"openness": 70})
    check("기존 riasec 보존", r["riasec"] == {"top_codes": ["A"]})

    # 6. user_form riasec 은 consult blend 가 못 덮음 (window_scores 형태 incoming — 실제 blend 분기 경로)
    existing = {
        "riasec": {"scores": {"S": 78}, "raw": {"S": 78.0}, "weights": {"S": 3.0}, "top_codes": ["S"]},
        "source": "user_form",
        "axis_confidence": {"riasec": 1.0},
    }
    incoming = {
        "riasec": {
            "window_scores": {"R": 50, "I": 95, "A": 90, "S": 50, "E": 50, "C": 50},
            "window_conf": {"R": 0.2, "I": 0.9, "A": 0.8, "S": 0.2, "E": 0.2, "C": 0.2},
        },
        "axis_confidence": {"riasec": 0.9},
    }
    r = merge_structured(existing, incoming, "consult_extraction")
    check("user_form riasec blend 미잠식", r["riasec"] == existing["riasec"], str(r["riasec"]))
    check("user_form riasec source 유지", r["source"] == "user_form")

    # 7. user_form big_five 는 consult blend 가 못 덮음 (case6 대칭 — window_scores 형태 incoming)
    existing = {
        "big_five": {"scores": {"C": 78}, "raw": {"C": 78.0}, "weights": {"C": 3.0}},
        "source": "user_form",
        "axis_confidence": {"big_five": 1.0},
    }
    incoming = {
        "big_five": {
            "window_scores": {"O": 50, "C": 95, "E": 90, "A": 50, "N": 50},
            "window_conf": {"O": 0.2, "C": 0.9, "E": 0.8, "A": 0.2, "N": 0.2},
        },
        "axis_confidence": {"big_five": 0.9},
    }
    r = merge_structured(existing, incoming, "consult_extraction")
    check("user_form big_five blend 미잠식", r["big_five"] == existing["big_five"], str(r["big_five"]))
    check("user_form big_five source 유지", r["source"] == "user_form")

    print(f"\n결과: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(run())
