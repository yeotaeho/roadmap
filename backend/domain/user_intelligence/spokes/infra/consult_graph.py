# 상담 대화 LangGraph 런타임 — 상태 그래프(prepare→respond→persist)와 체크포인터 어댑터.

from __future__ import annotations

import asyncio
import logging
from typing import Any, TypedDict

from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph

from domain.user_intelligence.hub.services.consult_interview_bank import (
    ALL_AXES,
    axis_label,
    first_uncovered,
    probe_hint,
)

logger = logging.getLogger(__name__)

_CHECKPOINTER: Any = None  # None=미시도, False=비활성 확정, 그 외=AsyncPostgresSaver
_CHECKPOINTER_CM: Any = None  # from_conn_string 컨텍스트 매니저 — GC 로 커넥션이 닫히지 않게 프로세스 수명 보관
_CHECKPOINTER_LOCK = asyncio.Lock()


class ConsultState(TypedDict, total=False):
    user_id: str
    session_id: str
    message: str
    summary: str | None
    recent: list[dict]
    system_content: str
    response: str
    error: str | None
    coverage: dict          # 축 코드 → True(신호 확보) — 체크포인터로 턴 간 지속
    mode: str               # interview | listening
    plan: dict              # 이번 턴 계획 {focus_axis, focus_hint}
    round_done: bool        # 이번 세션 라운드 완료·즉시 추출 수행됨


def _psycopg_dsn(url: str) -> str:
    """SQLAlchemy asyncpg URL → psycopg DSN. asyncpg 전용 ssl= 파라미터는 sslmode= 로 치환한다."""
    dsn = url.replace("postgresql+asyncpg://", "postgresql://")
    return dsn.replace("ssl=true", "sslmode=require").replace("ssl=require", "sslmode=require")


async def get_checkpointer():
    """AsyncPostgresSaver 프로세스 싱글턴 — 실패 시 경고 후 무체크포인트(fail-open, 상담 불능 방지)."""
    global _CHECKPOINTER, _CHECKPOINTER_CM
    if _CHECKPOINTER is not None:
        return _CHECKPOINTER or None
    async with _CHECKPOINTER_LOCK:
        if _CHECKPOINTER is not None:
            return _CHECKPOINTER or None
        try:
            from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

            from core.config.settings import get_settings

            cm = AsyncPostgresSaver.from_conn_string(_psycopg_dsn(get_settings().database_url))
            saver = await cm.__aenter__()  # 프로세스 수명 동안 유지(의도적 미종료)
            await saver.setup()  # 멱등 — 테이블은 Task 1 PoC 승인 시 이미 생성됨
            _CHECKPOINTER_CM = cm  # GC 파이널라이저가 커넥션을 닫지 않게 참조 유지
            _CHECKPOINTER = saver
        except Exception as e:
            logger.warning(f"LangGraph 체크포인터 비활성(무체크포인트로 동작): {e}")
            _CHECKPOINTER = False
    return _CHECKPOINTER or None


def disable_checkpointer() -> None:
    """체크포인터를 프로세스 수명 동안 비활성화한다 — 커넥션 사망 등 런타임 강등용."""
    global _CHECKPOINTER
    _CHECKPOINTER = False


def build_consult_graph(service: Any, checkpointer: Any | None = None):
    """서비스 심을 노드로 엮은 상담 그래프를 컴파일한다.

    노드는 service 속성(_streamer 등)을 호출 시점에 읽는다 — 테스트의 사후 주입(svc._streamer = fake)과 호환.
    """

    async def prepare(state: ConsultState) -> dict:
        summary = await service._maybe_summarize(state["session_id"])
        recent = await service._load_history(state["session_id"])
        system_content = await service._load_context_system(state["user_id"])
        return {"summary": summary, "recent": recent, "system_content": system_content}

    async def plan(state: ConsultState) -> dict:
        coverage = dict(state.get("coverage") or {})
        try:
            p = await service._planner(coverage, state["recent"], state["message"])
        except Exception as e:  # 플랜 실패 — 정적 폴백(미커버 첫 축·interview)으로 상담을 지속한다.
            logger.warning(f"인터뷰 플랜 실패(정적 폴백): {e}")
            p = {"mode": "interview", "newly_covered": [], "focus_axis": None, "focus_hint": None}
        for code in p.get("newly_covered") or []:
            if code in ALL_AXES:
                coverage[code] = True
        mode = p.get("mode") if p.get("mode") in ("interview", "listening") else "interview"
        focus = p.get("focus_axis") if p.get("focus_axis") in ALL_AXES else None
        if focus is None and mode != "listening":
            focus = first_uncovered(coverage)
        hint = p.get("focus_hint") or (probe_hint(focus) if focus else None)
        return {"coverage": coverage, "mode": mode, "plan": {"focus_axis": focus, "focus_hint": hint}}

    async def respond(state: ConsultState) -> dict:
        from domain.user_intelligence.hub.services import consult_context

        writer = get_stream_writer()
        guidance = ""
        if state.get("mode") == "listening":
            guidance = "\n\n[이번 턴 지침] 사용자가 고민을 꺼냈다. 조사 질문을 멈추고 경청·공감·반영에 집중하라."
        else:
            plan_info = state.get("plan") or {}
            focus = plan_info.get("focus_axis")
            if focus:
                guidance = (
                    f"\n\n[이번 턴 지침] 대화 흐름을 살리면서 '{axis_label(focus)}' 성향을 알 수 있는 "
                    f"질문을 자연스럽게 하나 던져라. 참고 각도: {plan_info.get('focus_hint') or ''}"
                )
        messages = consult_context.build_llm_messages(
            state["system_content"] + guidance, state.get("summary"), state["recent"], state["message"]
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

    async def extract(state: ConsultState) -> dict:
        if state.get("round_done"):
            return {}
        coverage = state.get("coverage") or {}
        if not all(coverage.get(c) for c in ALL_AXES):
            return {}
        writer = get_stream_writer()
        try:
            await service._extract_round(state["user_id"], state["session_id"])
        except Exception as e:  # 즉시 추출 실패는 치명적이지 않다 — 일일 배치가 수거한다.
            logger.warning(f"라운드 즉시 추출 실패(일일 배치 수거): {e}")
            return {}
        writer({"type": "self_model_updated"})
        return {"round_done": True}

    g = StateGraph(ConsultState)
    g.add_node("prepare", prepare)
    g.add_node("plan", plan)
    g.add_node("respond", respond)
    g.add_node("persist", persist)
    g.add_node("extract", extract)
    g.add_edge(START, "prepare")
    g.add_edge("prepare", "plan")
    g.add_edge("plan", "respond")
    g.add_edge("respond", "persist")
    g.add_edge("persist", "extract")
    g.add_edge("extract", END)
    return g.compile(checkpointer=checkpointer)
