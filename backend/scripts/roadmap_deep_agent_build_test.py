# 딥 에이전트 빌드 테스트 — 서브에이전트 구성·task 미노출·thinking disabled·산출 파싱 폴백
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-dummy")
os.environ.setdefault("TAVILY_API_KEY", "tvly-dummy")
os.environ.setdefault("WATERCRAWL_API_KEY", "wc-dummy")

_pass = 0
_fail = 0


def check(name: str, cond: bool) -> None:
    global _pass, _fail
    if cond:
        _pass += 1
        print(f"PASS {name}")
    else:
        _fail += 1
        print(f"FAIL {name}")


class _FakeAI:
    type = "ai"

    def __init__(self, content):
        self.content = content


def main() -> int:
    from core.config.settings import get_settings

    get_settings.cache_clear() if hasattr(get_settings, "cache_clear") else None

    from domain.hrowth_journey.spokes.agents.roadmap_deep_agent import (
        build_roadmap_deep_agent,
        build_subagent_specs,
        parse_agent_output,
    )
    from domain.hrowth_journey.spokes.agents.roadmap_agent_prompts import (
        build_generation_brief,
    )

    specs = build_subagent_specs("00000000-0000-0000-0000-000000000000")
    names = [s["name"] for s in specs]
    check("서브에이전트 3종", names == ["market_analyst", "opportunity_scout", "quest_designer"])
    for s in specs:
        tool_names = {t.name for t in s["tools"]}
        check(f"{s['name']} task 미노출", "task" not in tool_names)
        check(
            f"{s['name']} thinking disabled",
            getattr(s["model"], "thinking", None) == {"type": "disabled"},
        )
    check(
        "analyst tool 배분",
        {t.name for t in specs[0]["tools"]} == {"get_pulse_trends", "get_gap_issues", "get_sync_snapshot"},
    )
    check(
        "scout tool 배분(웹 포함)",
        {t.name for t in specs[1]["tools"]} == {"get_chance_matches", "web_search"},
    )
    check("designer tool 배분", {t.name for t in specs[2]["tools"]} == {"get_user_profile"})
    # user_id 클로저 — LLM 인자 스키마에 user_id 없음.
    for s in specs:
        for t in s["tools"]:
            schema = t.args_schema.model_json_schema() if t.args_schema else {"properties": {}}
            check(f"{t.name} user_id 인자 없음", "user_id" not in schema.get("properties", {}))
            break  # 서브에이전트당 대표 1개만(중복 출력 방지).

    agent = build_roadmap_deep_agent("00000000-0000-0000-0000-000000000000")
    check("컴파일 astream", hasattr(agent, "astream"))

    valid = {
        "title": "T", "summary": "", "skill_pillars": [], "bridge_keywords": [],
        "quests": [{"quest_key": "root", "parent_key": None, "title": "r",
                    "difficulty": "입문", "state": "start", "sort_order": 0}],
        "tasks": [{"quest_key": "root", "title": "t1", "estimated_days": 2}],
    }
    rm, tasks = parse_agent_output({"files": {"/roadmap_result.json": json.dumps(valid, ensure_ascii=False)}})
    check("파일 경로 파싱", rm.get("title") == "T" and len(tasks) == 1)
    rm2, _ = parse_agent_output(
        {"files": {}, "messages": [_FakeAI("서문\n" + json.dumps(valid, ensure_ascii=False))]}
    )
    check("메시지 JSON 폴백", rm2.get("title") == "T")
    rm3, t3 = parse_agent_output({"files": {}, "messages": [_FakeAI("JSON 없음")]})
    check("무산출 시 빈 결과", rm3 == {} and t3 == [])
    # 루트 2개 등 스키마 위반은 _parse_roadmap 이 {} 반환.
    bad = dict(valid)
    bad["quests"] = valid["quests"] + [{"quest_key": "r2", "parent_key": None, "title": "x",
                                        "difficulty": "입문", "state": "start", "sort_order": 1}]
    rm4, _ = parse_agent_output({"files": {"/roadmap_result.json": json.dumps(bad, ensure_ascii=False)}})
    check("루트 2개 거부", rm4 == {})

    brief = build_generation_brief("[목표 직무] 데이터 분석가", [], set())
    check("최초 생성 브리프", "최초 생성 모드" in brief)
    brief2 = build_generation_brief(
        "ctx",
        [{"quest_key": "q-a", "parent_key": "root", "title": "a", "state": "done"}],
        {"q-a"},
    )
    check("재생성 브리프 done 명시", "q-a" in brief2 and "재생성 모드" in brief2)

    print(f"\nRESULT: PASS {_pass} / FAIL {_fail}")
    return 0 if _fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
