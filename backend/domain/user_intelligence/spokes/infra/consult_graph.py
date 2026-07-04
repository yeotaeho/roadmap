# 상담 대화 LangGraph 런타임 — 상태 그래프(prepare→plan→respond→persist→extract)와 체크포인터 어댑터.

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

# 상담사 종료 신호(plan.complete)로 즉시 추출을 인정하는 최소 진행 — recent 윈도우 길이 기준
# (turn1=0·turn2=2·turn3=4개). 개시 직후 조기 종료(turn 1~2)를 차단한다.
_MIN_RECENT_FOR_COMPLETE = 4

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


async def _checkpoint_schema_ready() -> bool:
    """체크포인트 핵심 테이블(checkpoints)이 이미 존재하는지 확인 — setup() 실패 시 강등 여부 판단용."""
    from sqlalchemy import text

    from core.database import AsyncSessionLocal

    try:
        async with AsyncSessionLocal() as db:
            reg = (await db.execute(text("SELECT to_regclass('public.checkpoints')"))).scalar()
            return reg is not None
    except Exception:
        return False


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
            try:
                await saver.setup()  # 최초 1회 스키마·마이그레이션 생성
            except Exception as se:
                # langgraph setup() 은 이미 마이그레이션된 Neon(pgbouncer) DB 에 재실행되면 버전 감지가
                # 어긋나 checkpoint_migrations 중복키로 실패할 수 있다 — 스키마가 이미 존재하는 이 경우만
                # 관용해 saver 를 유지하고 재시작 시 영구 비활성을 막는다. 그 외 실패(스키마 미생성·신규
                # 마이그레이션 적용 실패 등)는 재-raise 해 fail-open(무체크포인트) 으로 강등한다.
                if "checkpoint_migrations" not in str(se) or not await _checkpoint_schema_ready():
                    raise
                logger.warning(f"체크포인터 setup 스킵(이미 초기화된 스키마·중복키 무시): {se}")
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

    노드는 service 속성(_streamer·_planner·_extract_round 등)을 호출 시점에 읽는다 —
    테스트의 사후 주입(svc._streamer = fake)과 호환.
    """

    async def prepare(state: ConsultState) -> dict:
        summary = await service._maybe_summarize(state["session_id"])
        recent = await service._load_history(state["session_id"])
        system_content = await service._load_context_system(state["user_id"])
        return {"summary": summary, "recent": recent, "system_content": system_content}

    async def plan(state: ConsultState) -> dict:
        if state.get("round_done"):
            # 라운드 완료 후에는 조사 계획이 불필요 — 플래너 호출을 건너뛰고 일반 상담으로 응답한다.
            # 단, coverage 는 재방출해 리로드 시 배지가 사라지지 않게 한다.
            cov = state.get("coverage") or {}
            get_stream_writer()({
                "type": "coverage",
                "covered": sum(1 for a in ALL_AXES if cov.get(a)),
                "total": len(ALL_AXES),
            })
            return {"mode": "interview", "plan": {}}
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
        focus = None if mode == "listening" else (p.get("focus_axis") if p.get("focus_axis") in ALL_AXES else None)
        if focus is not None and coverage.get(focus):
            focus = None  # 이미 커버된 축은 무시 — 미커버 폴백으로 라운드 진행을 보장한다.
        if focus is None and mode != "listening":
            focus = first_uncovered(coverage)
        hint = p.get("focus_hint") or (probe_hint(focus) if focus else None)
        complete = bool(p.get("complete")) and mode == "interview"  # 경청 턴은 종료로 보지 않음
        get_stream_writer()({
            "type": "coverage",
            "covered": sum(1 for a in ALL_AXES if coverage.get(a)),
            "total": len(ALL_AXES),
        })
        return {"coverage": coverage, "mode": mode, "plan": {"focus_axis": focus, "focus_hint": hint, "complete": complete}}

    async def respond(state: ConsultState) -> dict:
        from domain.user_intelligence.hub.services import consult_context

        writer = get_stream_writer()
        guidance = ""
        if state.get("mode") == "listening":
            guidance = "\n\n[이번 턴 지침] 사용자가 고민을 꺼냈다. 조사 질문을 멈추고 경청·공감·반영에 집중하라."
        elif (state.get("plan") or {}).get("complete"):
            guidance = (
                "\n\n[이번 턴 지침] 성향 파악이 충분하다. 새 질문을 던지지 말고, 지금까지 파악한 강점·흥미를 "
                "따뜻하게 요약해 확인한 뒤, 구체적 진로·실행 계획은 로드맵 코치에서 이어감을 안내하며 자연스럽게 마무리하라."
            )
        else:
            plan_info = state.get("plan") or {}
            focus = plan_info.get("focus_axis")
            if focus:
                hint = plan_info.get("focus_hint") or ""
                guidance = (
                    f"\n\n[이번 턴 지침] 이번 턴의 핵심은 '{axis_label(focus)}' 성향 파악이다. 사용자의 마지막 말에 "
                    f"짧게 공감한 뒤, 그 축을 파고드는 질문을 네가 주도적으로 던져라. 사용자가 아이디어·해결책 쪽으로 "
                    f'새면 부드럽게 자기이해로 되돌리고 필요 시 코치 위임을 안내하라. 참고 질문 각도: "{hint}"'
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
        all_covered = all(coverage.get(c) for c in ALL_AXES)
        # 종료 트리거: 전 11축 커버(기계적) 또는 상담사의 종료 판단(LLM 종료 신호). 후자는 조기
        # 종료 방지를 위해 최소 진행(recent ≥ _MIN_RECENT_FOR_COMPLETE) 조건에서만 인정한다.
        plan_complete = bool((state.get("plan") or {}).get("complete"))
        progressed = len(state.get("recent") or []) >= _MIN_RECENT_FOR_COMPLETE
        if not (all_covered or (plan_complete and progressed)):
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
