# 진행 이벤트 매퍼 테스트 — todos·task 호출/종료 매핑(합성 청크, 무네트워크)
from __future__ import annotations

import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

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


class _Msg:
    def __init__(self, type_=None, name=None, tool_calls=None, content=""):
        self.type = type_
        self.name = name
        self.tool_calls = tool_calls or []
        self.content = content


def main() -> int:
    from domain.hrowth_journey.spokes.infra.progress_events import (
        STAGE_PERCENT,
        map_agent_event,
    )

    evs = map_agent_event(
        "updates",
        {"agent": {"todos": [{"content": "시장 분석", "status": "in_progress"}]}},
    )
    check("todos 매핑", evs and evs[0]["kind"] == "todos" and evs[0]["todos"][0]["content"] == "시장 분석")

    evs = map_agent_event(
        "updates",
        {"agent": {"messages": [_Msg(type_="ai", tool_calls=[
            {"name": "task", "args": {"subagent_type": "market_analyst", "description": "x"}}
        ])]}},
    )
    check("subagent_start 매핑", evs and evs[0] == {"kind": "subagent_start", "name": "market_analyst"})

    evs = map_agent_event("updates", {"tools": {"messages": [_Msg(type_="tool", name="task")]}})
    check("subagent_end 매핑", evs and evs[0]["kind"] == "subagent_end")

    check("custom 모드 무시", map_agent_event("custom", {"whatever": 1}) == [])
    check("values 모드 무시", map_agent_event("values", {"messages": []}) == [])
    check("빈 update 무이벤트", map_agent_event("updates", {"agent": {}}) == [])
    check("task 아닌 tool_call 무시", map_agent_event(
        "updates",
        {"agent": {"messages": [_Msg(type_="ai", tool_calls=[{"name": "get_pulse_trends", "args": {}}])]}},
    ) == [])
    check("percent 단조 증가", STAGE_PERCENT["start"] < STAGE_PERCENT["market_analyst"]
          < STAGE_PERCENT["opportunity_scout"] < STAGE_PERCENT["quest_designer"]
          < STAGE_PERCENT["saving"] < STAGE_PERCENT["done"])

    print(f"\nRESULT: PASS {_pass} / FAIL {_fail}")
    return 0 if _fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
