# 코치 대화 LangGraph 런타임 — prepare→agent(tool 루프)→persist. 델타·tool 이벤트를 custom 스트림으로 방출.

from __future__ import annotations

import json
import logging
from typing import Any, TypedDict

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph

from domain.ai_coach.spokes.agents.tools.internal_tools import TOOL_LABELS

logger = logging.getLogger(__name__)

_MAX_TOOL_ROUNDS = 4  # tool 호출 루프 상한 — 폭주 방지(스펙 §5).


class CoachState(TypedDict, total=False):
    user_id: str
    session_id: str
    message: str
    summary: str | None
    recent: list[dict]
    system_content: str
    response: str
    error: str | None


def _chunk_text(chunk: Any) -> str:
    """AIMessageChunk.content(str | block list) → 순수 텍스트. Anthropic 은 블록 리스트를 준다."""
    content = getattr(chunk, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"
        )
    return ""


def _to_lc_messages(system: str, summary: str | None, recent: list[dict], message: str) -> list:
    """시스템+요약블록+최근 히스토리+현재 메시지 → LangChain 메시지 리스트."""
    out: list = [SystemMessage(content=system)]
    if summary:
        out.append(SystemMessage(content=f"[이전 대화 요약]\n{summary}"))
    for m in recent:
        role = m.get("role")
        content = m.get("content") or ""
        out.append(HumanMessage(content=content) if role == "user" else AIMessage(content=content))
    out.append(HumanMessage(content=message))
    return out


def build_coach_graph(service: Any, checkpointer: Any | None = None):
    """서비스 심을 노드로 엮은 코치 그래프 컴파일 — 노드는 service 속성을 호출 시점에 읽는다(테스트 주입 호환)."""

    async def prepare(state: CoachState) -> dict:
        summary = await service._maybe_summarize(state["session_id"])
        recent = await service._load_history(state["session_id"])
        system_content = await service._load_context_system(state["user_id"])
        return {"summary": summary, "recent": recent, "system_content": system_content}

    async def agent(state: CoachState) -> dict:
        writer = get_stream_writer()
        tools = service._build_tools(state["user_id"])
        tool_map = {t.name: t for t in tools}
        llm = service._chat_model().bind_tools(tools)
        messages = _to_lc_messages(
            state["system_content"], state.get("summary"), state["recent"], state["message"]
        )
        acc = ""
        try:
            for _ in range(_MAX_TOOL_ROUNDS + 1):
                final = None
                async for chunk in llm.astream(messages):
                    text = _chunk_text(chunk)
                    if text:
                        acc += text
                        writer({"type": "delta", "content": text})
                    final = chunk if final is None else final + chunk
                calls = list(getattr(final, "tool_calls", None) or [])
                if not calls:
                    break
                messages.append(final)
                for tc in calls:
                    name = tc.get("name")
                    writer({"type": "tool_call", "name": name, "label": TOOL_LABELS.get(name, name)})
                    tool_obj = tool_map.get(name)
                    if tool_obj is None:
                        result: Any = {"error": f"알 수 없는 tool: {name}"}
                    else:
                        try:
                            result = await tool_obj.ainvoke(tc.get("args") or {})
                        except Exception as te:  # tool 실패는 대화를 끊지 않는다 — 에러를 관찰로 되돌린다.
                            logger.warning(f"코치 tool 실패({name}): {te}")
                            result = {"error": str(te)}
                    writer({"type": "tool_result", "name": name})
                    messages.append(
                        ToolMessage(
                            content=json.dumps(result, ensure_ascii=False, default=str),
                            tool_call_id=tc.get("id") or "",
                        )
                    )
        except Exception as e:  # 스트림 도중 실패 — 에러 이벤트로 알리고 부분 응답은 보존.
            writer({"type": "error", "message": str(e)})
            return {"response": acc, "error": str(e)}
        return {"response": acc, "error": None}

    async def persist(state: CoachState) -> dict:
        if state.get("response"):
            await service._persist_assistant(state["session_id"], state["response"])
        return {}

    g = StateGraph(CoachState)
    g.add_node("prepare", prepare)
    g.add_node("agent", agent)
    g.add_node("persist", persist)
    g.add_edge(START, "prepare")
    g.add_edge("prepare", "agent")
    g.add_edge("agent", "persist")
    g.add_edge("persist", END)
    return g.compile(checkpointer=checkpointer)
