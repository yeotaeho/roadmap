# 코치 그래프(prepare→agent→persist) 단위 테스트 — 가짜 LLM·가짜 tool 로 이벤트 시퀀스 검증(무DB·무네트워크)

from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SCHEDULER_ENABLED", "false")

from langchain_core.messages import AIMessageChunk
from langchain_core.tools import tool

from domain.ai_coach.spokes.infra.coach_graph import _MAX_TOOL_ROUNDS, build_coach_graph

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


@tool
async def get_pulse_trends(sector_slug: str | None = None) -> dict:
    """가짜 트렌드 tool."""
    return {"sectors": [{"sector": "ai-software", "score": 88}]}


class FakeModel:
    """1회차엔 tool_call, 2회차엔 텍스트 스트림을 내는 가짜 ChatModel."""

    def __init__(self):
        self.round = 0

    def bind_tools(self, tools):
        return self

    async def astream(self, messages):
        self.round += 1
        if self.round == 1:
            chunk = AIMessageChunk(content="", tool_calls=[{"name": "get_pulse_trends", "args": {}, "id": "tc1", "type": "tool_call"}])
            yield chunk
        else:
            yield AIMessageChunk(content="AI 섹터가 ")
            yield AIMessageChunk(content="강세예요.")


class FakeService:
    def __init__(self, model=None):
        self.persisted: list[tuple] = []
        self.model = model or FakeModel()

    async def _maybe_summarize(self, session_id):
        return None

    async def _load_history(self, session_id):
        return []

    async def _load_context_system(self, user_id):
        return "SYS"

    def _chat_model(self):
        return self.model

    def _build_tools(self, user_id):
        return [get_pulse_trends]

    async def _persist_assistant(self, session_id, content):
        self.persisted.append((session_id, content))


class AlwaysToolModel:
    """매 라운드 tool_call 만 반환하는 가짜 ChatModel — 캡 도달·무응답 케이스 검증용."""

    def __init__(self):
        self.round = 0

    def bind_tools(self, tools):
        return self

    async def astream(self, messages):
        self.round += 1
        yield AIMessageChunk(
            content="",
            tool_calls=[{"name": "get_pulse_trends", "args": {}, "id": f"tc{self.round}", "type": "tool_call"}],
        )


class ToolThenFinalAnswerModel:
    """_MAX_TOOL_ROUNDS 회 tool_call 후 강제 최종 라운드에서 텍스트를 내는 가짜 ChatModel."""

    def __init__(self):
        self.round = 0

    def bind_tools(self, tools):
        return self

    async def astream(self, messages):
        self.round += 1
        if self.round <= _MAX_TOOL_ROUNDS:
            yield AIMessageChunk(
                content="",
                tool_calls=[{"name": "get_pulse_trends", "args": {}, "id": f"tc{self.round}", "type": "tool_call"}],
            )
        else:
            yield AIMessageChunk(content="캡 도달 후 ")
            yield AIMessageChunk(content="최종 답변입니다.")


async def main() -> int:
    svc = FakeService()
    graph = build_coach_graph(svc, checkpointer=None)
    events = []
    state = {"user_id": "u1", "session_id": "s1", "message": "요즘 뜨는 분야?"}
    async for chunk in graph.astream(state, {"configurable": {"thread_id": "s1"}}, stream_mode="custom"):
        events.append(chunk)

    types = [e.get("type") for e in events]
    check("tool_call 이벤트", "tool_call" in types)
    check("tool_result 이벤트", "tool_result" in types)
    check("delta 이벤트", types.count("delta") == 2)
    check("tool_call 이 delta 보다 먼저", types.index("tool_call") < types.index("delta"))
    tc = next(e for e in events if e.get("type") == "tool_call")
    check("tool_call 라벨 포함", bool(tc.get("label")))
    check("persist 1회·전체 응답", svc.persisted == [("s1", "AI 섹터가 강세예요.")])

    # 캡 도달 + 최종 라운드도 무응답 → error 이벤트, response 빈 문자열, persist 미호출.
    svc_cap = FakeService(model=AlwaysToolModel())
    graph_cap = build_coach_graph(svc_cap, checkpointer=None)
    events_cap = []
    state_cap = {"user_id": "u1", "session_id": "s2", "message": "질문"}
    async for chunk in graph_cap.astream(state_cap, {"configurable": {"thread_id": "s2"}}, stream_mode="custom"):
        events_cap.append(chunk)

    types_cap = [e.get("type") for e in events_cap]
    check(
        f"tool_call 이벤트 정확히 {_MAX_TOOL_ROUNDS}회",
        types_cap.count("tool_call") == _MAX_TOOL_ROUNDS,
        str(types_cap.count("tool_call")),
    )
    check("캡 도달 무응답 시 error 이벤트", "error" in types_cap)
    check("persist 미호출(무응답)", svc_cap.persisted == [])

    # 캡 도달 후 강제 최종 라운드에서 텍스트를 반환하는 정상 경로.
    svc_final = FakeService(model=ToolThenFinalAnswerModel())
    graph_final = build_coach_graph(svc_final, checkpointer=None)
    events_final = []
    state_final = {"user_id": "u1", "session_id": "s3", "message": "질문"}
    async for chunk in graph_final.astream(state_final, {"configurable": {"thread_id": "s3"}}, stream_mode="custom"):
        events_final.append(chunk)

    types_final = [e.get("type") for e in events_final]
    check(
        f"tool_call 이벤트 정확히 {_MAX_TOOL_ROUNDS}회(최종 응답 케이스)",
        types_final.count("tool_call") == _MAX_TOOL_ROUNDS,
        str(types_final.count("tool_call")),
    )
    check("최종 라운드 응답 저장", svc_final.persisted == [("s3", "캡 도달 후 최종 답변입니다.")])
    check("최종 응답 케이스 error 이벤트 없음", "error" not in types_final)

    print(f"\n합계: PASS {PASS} / FAIL {FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
