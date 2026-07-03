# 상담 대화 LangGraph 런타임 — 상태 그래프(prepare→respond→persist)와 체크포인터 어댑터.

from __future__ import annotations

import logging
from typing import Any, TypedDict

from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph

logger = logging.getLogger(__name__)

_CHECKPOINTER: Any = None  # None=미시도, False=비활성 확정, 그 외=AsyncPostgresSaver


class ConsultState(TypedDict, total=False):
    user_id: str
    session_id: str
    message: str
    summary: str | None
    recent: list[dict]
    system_content: str
    response: str
    error: str | None


def _psycopg_dsn(url: str) -> str:
    """SQLAlchemy asyncpg URL → psycopg DSN. asyncpg 전용 ssl= 파라미터는 sslmode= 로 치환한다."""
    dsn = url.replace("postgresql+asyncpg://", "postgresql://")
    return dsn.replace("ssl=true", "sslmode=require").replace("ssl=require", "sslmode=require")


async def get_checkpointer():
    """AsyncPostgresSaver 프로세스 싱글턴 — 실패 시 경고 후 무체크포인트(fail-open, 상담 불능 방지)."""
    global _CHECKPOINTER
    if _CHECKPOINTER is not None:
        return _CHECKPOINTER or None
    try:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        from core.config.settings import get_settings

        cm = AsyncPostgresSaver.from_conn_string(_psycopg_dsn(get_settings().database_url))
        saver = await cm.__aenter__()  # 프로세스 수명 동안 유지(의도적 미종료)
        await saver.setup()  # 멱등 — 테이블은 Task 1 PoC 승인 시 이미 생성됨
        _CHECKPOINTER = saver
    except Exception as e:
        logger.warning(f"LangGraph 체크포인터 비활성(무체크포인트로 동작): {e}")
        _CHECKPOINTER = False
    return _CHECKPOINTER or None


def build_consult_graph(service: Any, checkpointer: Any | None = None):
    """서비스 심을 노드로 엮은 상담 그래프를 컴파일한다.

    노드는 service 속성(_streamer 등)을 호출 시점에 읽는다 — 테스트의 사후 주입(svc._streamer = fake)과 호환.
    """

    async def prepare(state: ConsultState) -> dict:
        summary = await service._maybe_summarize(state["session_id"])
        recent = await service._load_history(state["session_id"])
        system_content = await service._load_context_system(state["user_id"])
        return {"summary": summary, "recent": recent, "system_content": system_content}

    async def respond(state: ConsultState) -> dict:
        from domain.user_intelligence.hub.services import consult_context

        writer = get_stream_writer()
        messages = consult_context.build_llm_messages(
            state["system_content"], state.get("summary"), state["recent"], state["message"]
        )
        acc = ""
        try:
            async for delta in service._streamer(messages):
                acc += delta
                writer({"type": "delta", "content": delta})
        except Exception as e:  # 스트림 도중 실패 — 에러 이벤트로 알리고 부분 응답은 보존.
            writer({"type": "error", "message": str(e)})
            return {"response": acc, "error": str(e)}
        return {"response": acc, "error": None}

    async def persist(state: ConsultState) -> dict:
        if state.get("response"):
            await service._persist_assistant(state["session_id"], state["response"])
        return {}

    g = StateGraph(ConsultState)
    g.add_node("prepare", prepare)
    g.add_node("respond", respond)
    g.add_node("persist", persist)
    g.add_edge(START, "prepare")
    g.add_edge("prepare", "respond")
    g.add_edge("respond", "persist")
    g.add_edge("persist", END)
    return g.compile(checkpointer=checkpointer)
