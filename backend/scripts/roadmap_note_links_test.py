# 노트 [[링크]] 파서 무DB 검증 테스트

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from domain.hrowth_journey.hub.services.note_service import parse_note_links  # noqa: E402

PASS = 0
FAIL = 0


def check(name: str, cond: bool, extra: str = "") -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"[PASS] {name}")
    else:
        FAIL += 1
        print(f"[FAIL] {name} {extra}")


def test_parse() -> None:
    check("기본 추출", parse_note_links("본문 [[스키마 노트]] 끝") == ["스키마 노트"])
    check(
        "복수 + 중복 제거(순서 보존)",
        parse_note_links("[[A]] 중간 [[B]] 그리고 [[A]]") == ["A", "B"],
    )
    check("트림", parse_note_links("[[  공백 제목  ]]") == ["공백 제목"])
    check("빈 링크 제외", parse_note_links("[[]] [[ ]]") == [])
    check("중첩 대괄호 비탐욕", parse_note_links("[[a]]b]]") == ["a"])
    check("없음 → []", parse_note_links("링크 없는 본문") == [])
    check("빈 본문 → []", parse_note_links("") == [])
    check("120자 초과 제목 제외", parse_note_links(f"[[{'가' * 121}]]") == [])


if __name__ == "__main__":
    test_parse()
    print(f"\n결과: PASS {PASS} / FAIL {FAIL}")
    sys.exit(1 if FAIL else 0)
