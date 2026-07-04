# 인터뷰 문항 은행·플랜 파서 순수 테스트 — 11축 구조·헬퍼·JSON 파싱 안전 기본값.

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SCHEDULER_ENABLED", "false")

from core.llm.client import _parse_interview_plan
from domain.user_intelligence.hub.services.consult_interview_bank import (
    ALL_AXES,
    INTERVIEW_AXES,
    axis_label,
    first_uncovered,
    probe_hint,
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


def run() -> int:
    check("11축", len(ALL_AXES) == 11 and set(ALL_AXES) == set(INTERVIEW_AXES), str(ALL_AXES))
    check("RIASEC 6 + BF 5",
          all(c in ALL_AXES for c in ("R", "I", "A", "S", "E", "C", "BF_O", "BF_C", "BF_E", "BF_A", "BF_N")))
    check("각 축 label·probes", all(a.get("label") and a.get("probes") for a in INTERVIEW_AXES.values()))
    check("first_uncovered 빈 커버리지", first_uncovered({}) == next(iter(INTERVIEW_AXES)))
    partial = {c: True for c in ALL_AXES if c != "BF_N"}
    check("first_uncovered 부분", first_uncovered(partial) == "BF_N")
    check("first_uncovered 전체 커버", first_uncovered({c: True for c in ALL_AXES}) is None)
    check("axis_label", "탐구" in axis_label("I"))
    check("probe_hint 존재", isinstance(probe_hint("R"), str) and len(probe_hint("R")) > 0)
    check("probe_hint 미지 코드 None", probe_hint("ZZ") is None)

    # 파서 — 정상
    p = _parse_interview_plan('{"mode": "listening", "newly_covered": ["R", "BF_O", "ZZ"], '
                              '"focus_axis": "I", "focus_hint": " 원리 파기 "}')
    check("파서 mode", p["mode"] == "listening")
    check("파서 코드 필터", p["newly_covered"] == ["R", "BF_O"], str(p["newly_covered"]))
    check("파서 focus", p["focus_axis"] == "I" and p["focus_hint"] == "원리 파기", str(p))
    # 파서 — 불량 입력 안전 기본값
    bad = _parse_interview_plan("망가진 json")
    check("파서 불량 기본값", bad == {"mode": "interview", "newly_covered": [], "focus_axis": None, "focus_hint": None, "complete": False}, str(bad))
    check("파서 미지 mode 기본", _parse_interview_plan('{"mode": "chaos"}')["mode"] == "interview")
    check("파서 미지 focus 제외", _parse_interview_plan('{"focus_axis": "ZZ"}')["focus_axis"] is None)

    print(f"\n결과: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(run())
