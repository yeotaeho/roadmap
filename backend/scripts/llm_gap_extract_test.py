# Gap 추출 응답 파서(_parse_gap) 무네트워크 결정론적 테스트

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.llm.client import _parse_gap  # noqa: E402

PASS = 0
FAIL = 0


def check(name: str, cond: bool) -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"[PASS] {name}")
    else:
        FAIL += 1
        print(f"[FAIL] {name}")


def test_valid() -> None:
    raw = (
        '{"problem": "청년 주거난", "opportunity": "프롭테크 창업", "detail": "상세 설명.",'
        ' "stakeholders": ["정부", "스타트업"], "next_actions": ["사이드프로젝트", "공모전"]}'
    )
    r = _parse_gap(raw)
    check("problem 파싱", r["problem"] == "청년 주거난")
    check("opportunity 파싱", r["opportunity"] == "프롭테크 창업")
    check("detail 파싱", r["detail"] == "상세 설명.")
    check("stakeholders 파싱", r["stakeholders"] == ["정부", "스타트업"])
    check("next_actions 파싱", r["next_actions"] == ["사이드프로젝트", "공모전"])


def test_abstain() -> None:
    # 문제 또는 기회 하나라도 없으면 전부 무귀속.
    r1 = _parse_gap('{"problem": "x", "opportunity": null}')
    check("opportunity 없으면 problem도 None", r1["problem"] is None)
    r2 = _parse_gap('{"problem": null, "opportunity": "y"}')
    check("problem 없으면 None", r2["problem"] is None)
    r3 = _parse_gap('{"problem": "  ", "opportunity": "y"}')
    check("공백 problem → None", r3["problem"] is None)


def test_edges() -> None:
    r1 = _parse_gap('{"problem": "p", "opportunity": "o", "stakeholders": "not list"}')
    check("stakeholders 비-리스트 → []", r1["stakeholders"] == [])
    check("detail 누락 → None", r1["detail"] is None)
    check("잘못된 JSON → None", _parse_gap("nope")["problem"] is None)
    check("None 입력 → None", _parse_gap(None)["problem"] is None)


def main() -> int:
    for fn in (test_valid, test_abstain, test_edges):
        fn()
    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
