# 플래너 서비스 순수 함수(직렬화·분해 폴백) 무DB 검증 테스트

from __future__ import annotations

import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from domain.hrowth_journey.hub.services.planner_service import (  # noqa: E402
    serialize_sprint,
    serialize_task,
    template_decompose,
)

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


def test_serialize() -> None:
    s = serialize_sprint(
        {"id": 1, "title": "1주차", "goal": None, "start_date": date(2026, 7, 6),
         "end_date": date(2026, 7, 12), "state": "active", "position": 0}
    )
    check("sprint camelCase", s["startDate"] == "2026-07-06" and s["endDate"] == "2026-07-12")
    check("sprint goal None 유지", s["goal"] is None)

    t = serialize_task(
        {"id": 9, "sprint_id": None, "quest_key": "q-a", "title": "t", "description": "",
         "status": "todo", "start_date": None, "due_date": date(2026, 7, 10),
         "estimated_days": 3, "position": 2, "source": "ai"}
    )
    check("task 백로그 sprintId null", t["sprintId"] is None)
    check("task dueDate 직렬화", t["dueDate"] == "2026-07-10" and t["startDate"] is None)
    check("task 나머지 키", t["questKey"] == "q-a" and t["estimatedDays"] == 3 and t["source"] == "ai")


def test_template_decompose() -> None:
    r = template_decompose({"title": "탄소 스키마", "difficulty": "중급", "purpose": "p"})
    check("폴백 3개", len(r) == 3)
    check("폴백 제목에 퀘스트 반영", any("탄소 스키마" in t["title"] for t in r))
    check("폴백 estimated_days 범위", all(1 <= t["estimated_days"] <= 30 for t in r))
    r2 = template_decompose({})
    check("빈 퀘스트도 3개 폴백", len(r2) == 3)


if __name__ == "__main__":
    test_serialize()
    test_template_decompose()
    print(f"\n결과: PASS {PASS} / FAIL {FAIL}")
    sys.exit(1 if FAIL else 0)
