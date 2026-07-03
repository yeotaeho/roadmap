# 상담 LangGraph 런타임 순수 테스트 — 노드 흐름·custom 델타·부분 응답 보존·심 호출 시점 주입.

from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SCHEDULER_ENABLED", "false")

from domain.user_intelligence.spokes.infra import consult_graph
from domain.user_intelligence.spokes.infra.consult_graph import build_consult_graph

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


class FakeService:
    def __init__(self):
        self.persisted: list[tuple[str, str]] = []
        self.seen_messages: list[dict] | None = None

        async def default_streamer(messages):
            self.seen_messages = messages
            for d in ["안", "녕"]:
                yield d

        self._streamer = default_streamer

    async def _maybe_summarize(self, session_id):
        return "요약본"

    async def _load_history(self, session_id):
        return [{"role": "user", "content": "이전 질문"}, {"role": "assistant", "content": "이전 답"}]

    async def _load_context_system(self, user_id):
        return "시스템 프롬프트\n\n[사용자 맥락]"

    async def _persist_assistant(self, session_id, content):
        self.persisted.append((session_id, content))


async def collect(graph, state_in, cfg):
    return [c async for c in graph.astream(state_in, cfg, stream_mode="custom")]


async def run() -> int:
    svc = FakeService()
    graph = build_consult_graph(svc)  # 체크포인터 없음(순수)
    cfg = {"configurable": {"thread_id": "t1"}}
    chunks = await collect(graph, {"user_id": "u1", "session_id": "s1", "message": "안녕하세요"}, cfg)

    check("델타 2건 순서", chunks == [{"type": "delta", "content": "안"}, {"type": "delta", "content": "녕"}], str(chunks))
    check("어시스턴트 저장", svc.persisted == [("s1", "안녕")], str(svc.persisted))
    check("시스템 메시지 선두", svc.seen_messages[0]["role"] == "system" and "시스템 프롬프트" in svc.seen_messages[0]["content"], str(svc.seen_messages[0]))
    check("요약 블록 주입", any("요약본" in m["content"] for m in svc.seen_messages if m["role"] == "system"), str(svc.seen_messages))
    check("현재 user 메시지 말미", svc.seen_messages[-1] == {"role": "user", "content": "안녕하세요"}, str(svc.seen_messages[-1]))

    # 에러 경로 — 첫 델타 후 폭발 → error 이벤트 + 부분 응답 보존 저장
    svc2 = FakeService()

    async def boom(messages):
        yield "부"
        raise RuntimeError("stream fail")

    svc2._streamer = boom  # 심을 호출 시점에 읽는지(주입 호환) 겸사 검증
    graph2 = build_consult_graph(svc2)
    chunks2 = await collect(graph2, {"user_id": "u1", "session_id": "s2", "message": "hi"}, {"configurable": {"thread_id": "t2"}})
    check("에러 이벤트 방출", any(c.get("type") == "error" for c in chunks2), str(chunks2))
    check("부분 응답 보존 저장", svc2.persisted == [("s2", "부")], str(svc2.persisted))

    # 빈 응답이면 저장 안 함
    svc3 = FakeService()

    async def empty(messages):
        if False:
            yield ""

    svc3._streamer = empty
    graph3 = build_consult_graph(svc3)
    await collect(graph3, {"user_id": "u1", "session_id": "s3", "message": "x"}, {"configurable": {"thread_id": "t3"}})
    check("빈 응답 미저장", svc3.persisted == [], str(svc3.persisted))

    # 강등 함수 — 전역을 직접 조작해 검증(순수, Neon 연결 없음)
    consult_graph._CHECKPOINTER = "sentinel"
    consult_graph.disable_checkpointer()
    demoted = await consult_graph.get_checkpointer()
    check("disable_checkpointer 후 get_checkpointer None", demoted is None, str(demoted))

    print(f"\n결과: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
