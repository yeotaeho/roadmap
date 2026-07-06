# 퀘스트 분해 파서·폴백 템플릿 무DB 검증 테스트

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.llm.client import _parse_decompose  # noqa: E402

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


_VALID = json.dumps(
    {
        "tasks": [
            {"title": "지표 용어집 정리", "description": "핵심 지표 20개", "estimated_days": 2},
            {"title": "데이터 소스 목록화", "description": "", "estimated_days": 99},
            {"title": "  ", "description": "제목 공백 — 버려야 함", "estimated_days": 3},
            {"title": "미니 파이프라인", "description": "입력→검증→저장", "estimated_days": "5"},
            {"title": "A", "estimated_days": 1},
            {"title": "B", "estimated_days": 1},
            {"title": "C", "estimated_days": 1},
            {"title": "7번째 — 잘려야 함", "estimated_days": 1},
        ]
    }
)


def test_valid() -> None:
    r = _parse_decompose(_VALID)
    check("최대 6개 상한", len(r) <= 6)
    check("공백 제목 제거", all(t["title"].strip() for t in r))
    check("estimated_days 범위 밖 보정(99→3)", r[1]["estimated_days"] == 3)
    check("estimated_days 비정수 보정('5'→3)", r[2]["estimated_days"] == 3)
    check("첫 항목 보존", r[0]["title"] == "지표 용어집 정리" and r[0]["estimated_days"] == 2)


def test_invalid() -> None:
    check("None → []", _parse_decompose(None) == [])
    check("깨진 JSON → []", _parse_decompose("{not json") == [])
    check("tasks 없음 → []", _parse_decompose(json.dumps({"foo": 1})) == [])
    check("tasks 비리스트 → []", _parse_decompose(json.dumps({"tasks": "x"})) == [])


if __name__ == "__main__":
    test_valid()
    test_invalid()
    print(f"\n결과: PASS {PASS} / FAIL {FAIL}")
    sys.exit(1 if FAIL else 0)
