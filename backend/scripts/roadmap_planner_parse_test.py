# RoadmapPlanner 순수 파서·템플릿 폴백 무DB 검증 테스트

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.llm.client import _parse_roadmap  # noqa: E402
from domain.hrowth_journey.hub.services.journey_assembler import assemble_quest_tree  # noqa: E402
from domain.hrowth_journey.hub.services.roadmap_planner_service import (  # noqa: E402
    build_planner_context,
    template_roadmap,
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


_VALID = json.dumps(
    {
        "title": "에너지 × AI 로드맵",
        "summary": "방향 고정",
        "skill_pillars": [
            {"id": "p1", "label": "데이터", "blurb": "수집·정제"},
            {"id": "p2", "label": "도메인", "blurb": "규제·지표"},
            {"id": "p3", "label": "AI", "blurb": "배포·관측"},
            {"id": "p4", "label": "넘침", "blurb": "4번째는 잘림"},
        ],
        "bridge_keywords": ["탄소회계", "FastAPI", ""],
        "quests": [
            {"quest_key": "root", "parent_key": None, "title": "시작점", "purpose": "now",
             "difficulty": "입문", "keywords": ["a"], "state": "start", "sort_order": 0},
            {"quest_key": "q-a", "parent_key": "root", "title": "기초", "purpose": "p",
             "difficulty": "쉬움", "keywords": [], "state": "wat", "sort_order": 1},
        ],
    }
)


def test_valid() -> None:
    r = _parse_roadmap(_VALID)
    check("유효 파싱 title", r.get("title") == "에너지 × AI 로드맵")
    check("pillars 최대 3개", len(r["skill_pillars"]) == 3)
    check("bridge 빈 문자열 제거", r["bridge_keywords"] == ["탄소회계", "FastAPI"])
    check("난이도 보정(쉬움→입문)", r["quests"][1]["difficulty"] == "입문")
    check("상태 보정(wat→available)", r["quests"][1]["state"] == "available")
    tree = assemble_quest_tree(r["quests"])
    check("파서 출력이 트리 조립됨", bool(tree) and tree["id"] == "root")


def test_invalid_json() -> None:
    check("깨진 JSON → {}", _parse_roadmap("{bad") == {})


def test_no_title() -> None:
    check("title 없음 → {}", _parse_roadmap(json.dumps({"quests": []})) == {})


def test_no_root() -> None:
    raw = json.dumps({"title": "t", "quests": [
        {"quest_key": "a", "parent_key": "b", "title": "A", "difficulty": "입문", "state": "available"}]})
    check("루트 없음 → {}", _parse_roadmap(raw) == {})


def test_multi_root() -> None:
    raw = json.dumps({"title": "t", "quests": [
        {"quest_key": "a", "parent_key": None, "title": "A", "difficulty": "입문", "state": "start"},
        {"quest_key": "b", "parent_key": None, "title": "B", "difficulty": "입문", "state": "start"}]})
    check("루트 2개 → {}", _parse_roadmap(raw) == {})


def test_root_key_normalized() -> None:
    # quest_key=="root" 인데 parent 가 잘못 채워진 경우 → 루트로 정규화.
    raw = json.dumps({"title": "t", "quests": [
        {"quest_key": "root", "parent_key": "x", "title": "시작", "difficulty": "입문", "state": "done"}]})
    r = _parse_roadmap(raw)
    check("root 정규화 parent None", r["quests"][0]["parent_key"] is None)
    check("root 정규화 state start", r["quests"][0]["state"] == "start")


def test_template_valid() -> None:
    t = template_roadmap(
        {"skills": [{"name": "Python", "level": "중급"}], "summary": "s"},
        "백엔드 엔지니어",
        ["FastAPI", "ESG"],
    )
    check("템플릿 title 직무 반영", "백엔드 엔지니어" in t["title"])
    check("템플릿 pillars 3개", len(t["skill_pillars"]) == 3)
    roots = [q for q in t["quests"] if q["parent_key"] is None]
    check("템플릿 루트 정확히 1개", len(roots) == 1)
    tree = assemble_quest_tree(t["quests"])
    check("템플릿 트리 조립됨", bool(tree) and tree["id"] == "root")


def test_context_builder() -> None:
    ctx = build_planner_context(
        {"skills": [{"name": "SQL", "level": "입문"}], "experiences": [], "education": [], "summary": ""},
        "데이터 분석가",
        ["BI"],
    )
    check("맥락에 목표 직무 포함", "데이터 분석가" in ctx)
    check("맥락에 스킬 포함", "SQL" in ctx)
    check("movers/gaps 없으면 섹션 생략", "Pulse" not in ctx and "Gap" not in ctx)


def test_context_with_market() -> None:
    ctx = build_planner_context(
        {"skills": [], "experiences": [], "education": [], "summary": ""},
        "백엔드",
        [],
        movers=[{"sector_slug": "ai-data", "score": 88, "momentum_pct": 12.5}],
        gaps=[{"problem": "탄소회계 자동화 부재", "chance": "ESG 데이터 엔지니어 수요"}],
    )
    check("맥락에 Pulse 트렌드 포함", "ai-data" in ctx and "Pulse" in ctx)
    check("맥락에 Gap 신호 포함", "탄소회계 자동화 부재" in ctx and "Gap" in ctx)


def main() -> int:
    test_valid()
    test_invalid_json()
    test_no_title()
    test_no_root()
    test_multi_root()
    test_root_key_normalized()
    test_template_valid()
    test_context_builder()
    test_context_with_market()
    print(f"\n결과: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
