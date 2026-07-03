# SP-8a 상담 엔진 LangGraph 전환 (동작 동등) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 상담 대화 엔진을 LangGraph StateGraph(+AsyncPostgresSaver 체크포인터)로 전환하되 **행동은 동일**하게 유지한다 — 기존 consult 테스트 스위트가 무수정 green이 게이트.

**Architecture:** 스펙 `backend/docs/superpowers/specs/2026-07-04-consult-redesign-langgraph-interview-design.md` §D SP-8a. LangGraph 런타임은 `user_intelligence/spokes/infra/consult_graph.py`(신설)에 두고, `ConsultService`는 얇은 어댑터로 그래프를 구동한다. 그래프 노드는 서비스 심(`_maybe_summarize`·`_streamer` 등)을 **호출 시점에** 읽어 기존 테스트의 주입(`svc._streamer = fake`)과 호환된다. 토큰 스트리밍은 `stream_mode="custom"` + `get_stream_writer()`로 기존 `LlmClient.stream_chat`을 그대로 감싼다(파리티 — langchain 모델로 교체하지 않음).

**Tech Stack:** langgraph 1.1.10(설치됨) · langgraph-checkpoint-postgres(신규 설치, psycopg 기반) · FastAPI SSE · SQLAlchemy 2.0 async.

## Global Constraints

- 한국어 문장 종결 `.` `?` `!` 만. 새 소스 파일 첫 줄 한 줄 한국어 역할 주석.
- 커밋 논리 단위, `git add .` 금지(파일 명시, `.superpowers/`·`__pycache__` 제외). 커밋 트레일러 `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
- **동작 동등 게이트** — 기존 7개 consult 스위트(`consult_context`·`consult_endpoint`·`consult_extract_repo`·`consult_service`·`consult_session_models_import`·`consult_session_repository`·`consult_stream`) **무수정** green. SSE 계약(`delta`/`done`/`error`)·`consult_messages` 저장·`context_summary` 롤링 요약·API 키 미설정 폴백 전부 유지.
- 체크포인터는 **fail-open** — 초기화 실패 시 경고 로그 후 무체크포인트로 동작(상담 불능이 되면 안 됨).
- `AsyncPostgresSaver.setup()`은 Neon DDL — **사용자 승인 후에만 실행**(Task 1 Step 4). langgraph 자체 관리 테이블이라 alembic 밖(예외 사유를 커밋 메시지에 명시).
- 백엔드 테스트 관행 `backend/scripts/*_test.py`(PASS/FAIL check, cwd `backend/`).
- DSN: `settings.database_url`(NEON_DATABASE_URL)은 `postgresql+asyncpg://` — psycopg용으로 `postgresql://` 변환 + `ssl=` → `sslmode=` 치환.

---

### Task 1: PoC — checkpoint-postgres 설치·Neon 검증·custom 스트리밍

**Files:**
- Modify: `backend/requirements.txt` (langgraph-checkpoint-postgres 추가)
- Create: `backend/scripts/langgraph_neon_poc.py`

**Interfaces:**
- Produces: Neon에 langgraph 체크포인터 테이블(setup, 승인 게이트). 이후 태스크가 의존하는 사실 확인 — psycopg DSN 변환식·`get_stream_writer` 동작.

- [ ] **Step 1: 패키지 설치 + requirements 반영**

Run: `pip install langgraph-checkpoint-postgres` (cwd 무관)
`backend/requirements.txt`의 `langgraph>=0.0.40` 아래에 추가:
```
langgraph-checkpoint-postgres>=2.0.0
```
Run: `pip show langgraph-checkpoint-postgres` → Version 출력 확인.

- [ ] **Step 2: PoC 스크립트 작성**

`backend/scripts/langgraph_neon_poc.py` 생성.

```python
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
    raise SystemExit(asyncio.run(run()))
```

- [ ] **Step 3: 실행 (Neon DDL 승인 게이트)**

스크립트가 Part B에서 `saver.setup()`을 호출해 Neon에 langgraph 체크포인터 테이블(checkpoints 등)을 생성한다. **사용자 승인이 이미 확보된 경우에만** 실행한다(오케스트레이터가 디스패치 시 승인 여부를 명시).

Run: `python scripts/langgraph_neon_poc.py` (cwd `backend/`)
Expected: `결과: PASS=4 FAIL=0`.

실패 시(예: pgbouncer·pipeline 모드 비호환) 에러 전문을 보고하고 중단 — 폴백(비풀 DSN 또는 자체 JSONB 체크포인터)은 오케스트레이터 판단.

- [ ] **Step 4: 커밋**

```bash
git add backend/requirements.txt backend/scripts/langgraph_neon_poc.py
git commit -m "feat(sp8a): langgraph-checkpoint-postgres 도입 PoC — Neon setup·custom 스트리밍 검증"
```

---

### Task 2: 그래프 런타임 (spokes/infra) + 순수 단위 테스트

**Files:**
- Create: `backend/domain/user_intelligence/spokes/infra/consult_graph.py`
- Test(신규): `backend/scripts/consult_graph_test.py`

**Interfaces:**
- Consumes: 서비스 심 규약(덕 타이핑) — `_maybe_summarize(session_id)->str|None` · `_load_history(session_id)->list[dict]` · `_load_context_system(user_id)->str` · `_streamer(messages)->async gen[str]` · `_persist_assistant(session_id, content)->None`. (Task 3이 ConsultService에 구현.)
- Produces: `build_consult_graph(service, checkpointer=None) -> CompiledGraph` · `ConsultState` · `get_checkpointer() -> AsyncPostgresSaver|None`(fail-open 싱글턴) · `_psycopg_dsn(url)->str`.

- [ ] **Step 1: 실패 테스트 작성**

`backend/scripts/consult_graph_test.py` 생성.

```python
# 상담 LangGraph 런타임 순수 테스트 — 노드 흐름·custom 델타·부분 응답 보존·심 호출 시점 주입.

from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SCHEDULER_ENABLED", "false")

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

    print(f"\n결과: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
```

- [ ] **Step 2: 실패 확인**

Run: `python scripts/consult_graph_test.py` (cwd `backend/`)
Expected: `ModuleNotFoundError`(consult_graph 미존재).

- [ ] **Step 3: 런타임 구현**

`backend/domain/user_intelligence/spokes/infra/consult_graph.py` 생성.

```python
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
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python scripts/consult_graph_test.py`
Expected: `결과: PASS=8 FAIL=0`.

- [ ] **Step 5: 커밋**

```bash
git add backend/domain/user_intelligence/spokes/infra/consult_graph.py backend/scripts/consult_graph_test.py
git commit -m "feat(sp8a): 상담 LangGraph 런타임 — prepare/respond/persist 그래프 + fail-open 체크포인터"
```

---

### Task 3: ConsultService 어댑터 전환 + 동작 동등 게이트

**Files:**
- Modify: `backend/domain/user_intelligence/hub/services/consult_service.py` (stream_sse 그래프 구동으로 교체·심 메서드 추출)

**Interfaces:**
- Consumes: Task 2의 `build_consult_graph`·`get_checkpointer`.
- Produces: 공개 표면 불변 — `ConsultService.stream_sse(user_id, session_id, message)` async gen[str(SSE)] · `create_session`·`get_or_create_session`·`verify_owner`·`get_messages`·`end_session`·`_maybe_summarize`·`_streamer`·`_summarizer` 전부 기존 시그니처 유지. 신규 심 `_load_history`·`_load_context_system`·`_persist_assistant`·`_get_graph`.

- [ ] **Step 1: 심 메서드 추출 + stream_sse 교체**

`consult_service.py`에서 import에 추가:
```python
from domain.user_intelligence.spokes.infra.consult_graph import build_consult_graph, get_checkpointer
```
`__init__` 말미에 `self._graph = None` 추가. 기존 `stream_sse`를 다음으로 교체하고, 그 위에 심 3개와 `_get_graph`를 추가한다(`_maybe_summarize`는 무변경 유지).

```python
    async def _load_history(self, session_id: str) -> list[dict]:
        """최근 윈도우 히스토리 — 방금 저장된 현재 user 메시지는 제외(별도 주입)."""
        async with AsyncSessionLocal() as db:
            all_msgs = await ConsultSessionRepository(db).fetch_messages(session_id)
        history = all_msgs[:-1] if all_msgs and all_msgs[-1]["role"] == "user" else all_msgs
        _older, recent = consult_context.split_history(history, _WINDOW_N)
        return recent

    async def _load_context_system(self, user_id: str) -> str:
        """상담 시스템 프롬프트 + 사용자 맥락. 맥락 로드 실패 시 프롬프트만(조용히 삼키지 않음)."""
        try:
            async with AsyncSessionLocal() as db:
                ctx = await ConsultContextRepository(db).fetch_context(user_id)
            context_str = build_consult_context(ctx)
        except Exception as e:
            logger.warning(f"상담 맥락 로드 실패(맥락 없이 진행): {e}")
            context_str = ""
        return _CONSULT_SYSTEM_PROMPT + ("\n\n" + context_str if context_str else "")

    async def _persist_assistant(self, session_id: str, content: str) -> None:
        async with AsyncSessionLocal() as db:
            await ConsultSessionRepository(db).add_message(session_id, "assistant", content)

    async def _get_graph(self):
        if self._graph is None:
            self._graph = build_consult_graph(self, await get_checkpointer())
        return self._graph

    async def stream_sse(self, user_id: str, session_id: str, message: str):
        """사용자 메시지 저장 → LangGraph(prepare→respond→persist) 구동 → custom 델타를 SSE 로 중계."""
        async with AsyncSessionLocal() as db:
            await ConsultSessionRepository(db).add_message(session_id, "user", message)

        if not self._api_key:
            yield _sse({"type": "delta", "content": "현재 AI 상담이 비활성화되어 있습니다(API 키 미설정)."})
            yield _sse({"type": "done"})
            return

        graph = await self._get_graph()
        config = {"configurable": {"thread_id": session_id}}
        state_in = {"user_id": user_id, "session_id": session_id, "message": message}
        async for chunk in graph.astream(state_in, config, stream_mode="custom"):
            yield _sse(chunk)
        yield _sse({"type": "done"})
```

기존 stream_sse 본문에서 이관된 로직(히스토리 분리·맥락 로드·저장)은 위 심으로 옮겨졌으므로 중복 잔재가 남지 않게 확인한다.

- [ ] **Step 2: 동작 동등 게이트 — 7개 스위트 무수정 실행**

Run (cwd `backend/`, 각각):
```bash
python scripts/consult_context_test.py
python scripts/consult_service_test.py
python scripts/consult_stream_test.py
python scripts/consult_endpoint_test.py
python scripts/consult_session_repository_test.py
python scripts/consult_session_models_import_test.py
python scripts/consult_extract_repo_test.py
```
Expected: 전부 FAIL=0, **테스트 파일 수정 0줄**. 실패 시 테스트를 고치지 말고 구현을 고친다(동작 동등이 목적).

- [ ] **Step 3: 그래프·추출 회귀**

Run: `python scripts/consult_graph_test.py; python scripts/self_model_extraction_test.py`
Expected: 각 FAIL=0.

- [ ] **Step 4: 커밋**

```bash
git add backend/domain/user_intelligence/hub/services/consult_service.py
git commit -m "feat(sp8a): ConsultService 를 LangGraph 어댑터로 전환 — SSE·저장·요약 동작 동등"
```

---

## 최종 검증 (whole-branch)

- [ ] 백엔드 (cwd `backend/`, 각 FAIL=0): 7개 consult 스위트 + `consult_graph_test` + `langgraph_neon_poc` + `self_model_extraction_test` + `self_model_user_edits_test`.
- [ ] 프론트 무변경(SSE 계약 동일) — tsc 불필요.
- [ ] 리뷰 게이트 — code-reviewer whole-branch → Codex `--base <시작 ref> --scope branch`.
