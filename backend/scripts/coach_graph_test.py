# 코치 그래프(prepare→agent→persist) 단위 테스트 — 가짜 LLM·가짜 tool 로 이벤트 시퀀스 검증(무DB·무네트워크)

from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SCHEDULER_ENABLED", "false")

from langchain_core.messages import AIMessageChunk
from langchain_core.tools import tool

from domain.ai_coach.spokes.infra.coach_graph import build_coach_graph

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
    def __init__(self):
        self.persisted: list[tuple] = []
        self.model = FakeModel()

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

    print(f"\n합계: PASS {PASS} / FAIL {FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
