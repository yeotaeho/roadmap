# LangGraph PoC — custom 스트리밍(MemorySaver)·AsyncPostgresSaver Neon 왕복 검증.

from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SCHEDULER_ENABLED", "false")

from typing import TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph

from core.config.settings import get_settings

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


class S(TypedDict, total=False):
    text: str


def _psycopg_dsn(url: str) -> str:
    dsn = url.replace("postgresql+asyncpg://", "postgresql://")
    return dsn.replace("ssl=true", "sslmode=require").replace("ssl=require", "sslmode=require")


async def part_a_custom_stream() -> None:
    """custom 스트리밍 — 노드 안 writer 이벤트가 astream(stream_mode='custom')으로 나오는지."""

    async def talk(state: S) -> dict:
        writer = get_stream_writer()
        for d in ["안", "녕"]:
            writer({"type": "delta", "content": d})
        return {"text": "안녕"}

    g = StateGraph(S)
    g.add_node("talk", talk)
    g.add_edge(START, "talk")
    g.add_edge("talk", END)
    app = g.compile(checkpointer=MemorySaver())
    cfg = {"configurable": {"thread_id": "poc-a"}}
    got = [c async for c in app.astream({"text": ""}, cfg, stream_mode="custom")]
    check("custom 스트림 delta 2건", got == [{"type": "delta", "content": "안"}, {"type": "delta", "content": "녕"}], str(got))
    final = await app.aget_state(cfg)
    check("최종 state text", final.values.get("text") == "안녕", str(final.values))


async def part_b_postgres_saver() -> None:
    """AsyncPostgresSaver — Neon 연결·setup(DDL)·thread 왕복."""
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

    dsn = _psycopg_dsn(get_settings().database_url)
    async with AsyncPostgresSaver.from_conn_string(dsn) as saver:
        await saver.setup()  # 멱등 DDL — 사용자 승인 후 실행
        check("setup 완료", True)

        async def echo(state: S) -> dict:
            return {"text": state.get("text", "") + "!"}

        g = StateGraph(S)
        g.add_node("echo", echo)
        g.add_edge(START, "echo")
        g.add_edge("echo", END)
        app = g.compile(checkpointer=saver)
        cfg = {"configurable": {"thread_id": "poc-b"}}
        await app.ainvoke({"text": "neon"}, cfg)
        st = await app.aget_state(cfg)
        check("Neon 체크포인트 왕복", st.values.get("text") == "neon!", str(st.values))


async def run() -> int:
    await part_a_custom_stream()
    await part_b_postgres_saver()
    print(f"\n결과: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    # Windows ProactorEventLoop은 psycopg async를 지원하지 않아 SelectorEventLoop로 강제 전환.
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    raise SystemExit(asyncio.run(run()))
