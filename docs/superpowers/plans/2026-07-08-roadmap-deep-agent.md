# R-1 로드맵 딥 에이전트 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** deepagents 기반 로드맵 생성 딥 에이전트(서브에이전트 3종) + 생성 런 상태 모델 + SSE 진행률 + 코치 발주 tool을 구현한다.

**Architecture:** `POST /roadmap/generate`가 `roadmap_generation_runs` 행을 만들고 asyncio 백그라운드 태스크로 딥 에이전트를 실행한다. 진행률은 인프로세스 RunHub(asyncio.Queue) + DB progress JSONB로 이원 기록되어 SSE 재구독·코치 발주 후 탭 진입을 모두 지원한다. 에이전트 산출(JSON)은 루프 밖 서비스 코드가 검증→진행 보존 병합→WBS 백로그 시드로 저장하며, 실패 시 기존 로드맵 무손상(없으면 template 폴백)을 보장한다.

**Tech Stack:** deepagents 0.6.12, langchain-anthropic(ChatAnthropic, thinking disabled), FastAPI SSE, PostgreSQL(Neon), Next.js/TanStack Query.

## Global Constraints

- 새 소스 파일 첫 줄: 한 줄 한국어 주석(역할 명시).
- 한국어 문장 종결은 `.` `?` `!` 만.
- 테스트는 pytest가 아니라 `backend/scripts/<name>_test.py` 스탠드얼론 — `check(name, cond)` PASS/FAIL 카운터, 실패 있으면 exit 1. 스크립트 상단 `sys.stdout.reconfigure(encoding="utf-8")`(Windows cp949 방지).
- 한 프로세스에서 `asyncio.run()`은 정확히 1회(임베딩 클라이언트 lru_cache 루프 바인딩).
- tool·서브에이전트는 전부 read-only. DB 쓰기는 에이전트 루프 밖 서비스 코드만.
- §9 계약: 자기모델은 `ConsultMemoryService.read_for_coach()` 단일 관문(get_user_profile tool 경유). Bronze 직접 조회 금지.
- Sonnet 5 함정: ChatAnthropic은 반드시 `thinking={"type": "disabled"}` 명시.
- deepagents 함정: 서브에이전트 recursion_limit=25 고정(프롬프트로 tool 호출 ≤5회 지시), 서브에이전트 `tools`에 `task` 미포함(재귀 스폰 차단).
- 커밋 메시지 트레일러: `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.
- Docker 컨테이너 `roadmap-api-1`은 이미지 재빌드 전까지 `docker exec roadmap-api-1 pip install ...` 수동 설치 필요(라이브 verify는 컨테이너 실행).
- 백엔드 실행·테스트는 `C:\project\roadmap\backend`에서. `.env`는 프로젝트 루트(pydantic-settings 자동 로드).

---

### Task 1: deepagents 설치 + 호환 스모크

**Files:**
- Modify: `backend/requirements.txt` (langchain-anthropic 근처)
- Create: `backend/scripts/deepagents_smoke_test.py`

**Interfaces:**
- Produces: 설치 확정된 `deepagents==0.6.12` + 실제 임포트 경로 확인 결과(`create_deep_agent`, `StateBackend`). 이후 태스크가 이 임포트 경로를 사용.

- [ ] **Step 1: 회귀 베이스라인 기록**

의존성 승격 전 기존 스위트 결과를 기록한다(설치 후 비교 기준).

```bash
cd /c/project/roadmap/backend
for f in scripts/*_test.py; do python "$f" >/dev/null 2>&1 && echo "PASS $f" || echo "FAIL $f"; done | tee /tmp/r1_baseline.txt
```

Expected: 기존 스위트 대부분 PASS(FAIL이 있으면 그대로 기록 — 설치 후 동일해야 함).

- [ ] **Step 2: requirements.txt에 deepagents 추가**

`langchain-anthropic>=0.3.0` 줄 아래에 추가.

```
deepagents==0.6.12
```

- [ ] **Step 3: 로컬 설치 + 버전 확인**

```bash
cd /c/project/roadmap/backend && pip install "deepagents==0.6.12"
pip show deepagents langchain-core langchain langchain-anthropic langgraph | grep -E "^(Name|Version)"
```

Expected: deepagents 0.6.12, langchain-core 1.4.8+, langchain 1.3.11+, langchain-anthropic 1.4.7+ 로 승격. langgraph 버전 기록.

- [ ] **Step 4: 스모크 테스트 작성**

`backend/scripts/deepagents_smoke_test.py`:

```python
# deepagents 0.6.12 설치·호환 스모크 — 임포트 경로·시그니처·무네트워크 빌드 확인
from __future__ import annotations

import inspect
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


def main() -> int:
    import importlib.metadata as md

    print("deepagents:", md.version("deepagents"))
    print("langchain-core:", md.version("langchain-core"))
    print("langchain:", md.version("langchain"))
    print("langchain-anthropic:", md.version("langchain-anthropic"))
    try:
        print("langgraph:", md.version("langgraph"))
    except md.PackageNotFoundError:
        print("langgraph: (미설치 — transitive 아님)")

    from deepagents import create_deep_agent

    sig = inspect.signature(create_deep_agent)
    for p in ("model", "tools", "system_prompt", "subagents", "backend", "checkpointer", "response_format"):
        check(f"create_deep_agent 파라미터 {p}", p in sig.parameters)

    # StateBackend 임포트 경로 확정(이후 태스크가 사용) — 실패 시 대체 경로 출력.
    try:
        from deepagents.backends import StateBackend  # noqa: F401

        check("StateBackend 임포트(deepagents.backends)", True)
    except ImportError:
        import deepagents as da

        print("deepagents 공개 심볼:", [n for n in dir(da) if "ackend" in n])
        check("StateBackend 임포트(deepagents.backends)", False)

    # 무네트워크 빌드 — 더미 키 ChatAnthropic 인스턴스 + 서브에이전트 1종.
    from langchain_anthropic import ChatAnthropic
    from langchain_core.tools import tool

    @tool
    def _noop(q: str) -> str:
        """스모크용 무동작 tool."""
        return q

    model = ChatAnthropic(
        model="claude-sonnet-5", api_key="sk-dummy", max_tokens=1024,
        thinking={"type": "disabled"},
    )
    agent = create_deep_agent(
        model=model,
        system_prompt="스모크 오케스트레이터.",
        subagents=[{
            "name": "smoke_sub", "description": "스모크 서브에이전트.",
            "system_prompt": "스모크.", "tools": [_noop], "model": model,
        }],
    )
    check("컴파일 그래프 astream 지원", hasattr(agent, "astream"))
    check("컴파일 그래프 ainvoke 지원", hasattr(agent, "ainvoke"))

    print(f"\nRESULT: PASS {_pass} / FAIL {_fail}")
    return 0 if _fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: 스모크 실행**

```bash
cd /c/project/roadmap/backend && python scripts/deepagents_smoke_test.py
```

Expected: `RESULT: PASS n / FAIL 0`. StateBackend 임포트가 FAIL이면 출력된 대체 경로를 Task 4에 전달(태스크 보고에 기록).

- [ ] **Step 6: 회귀 재실행·비교**

```bash
cd /c/project/roadmap/backend
for f in scripts/*_test.py; do python "$f" >/dev/null 2>&1 && echo "PASS $f" || echo "FAIL $f"; done | tee /tmp/r1_after.txt
diff /tmp/r1_baseline.txt /tmp/r1_after.txt && echo "REGRESSION-FREE"
```

Expected: `REGRESSION-FREE`(차이 없음). 차이가 나면 해당 스위트를 직접 실행해 원인(의존성 승격 breaking)을 보고하고 멈춘다.

- [ ] **Step 7: 컨테이너 설치**

```bash
docker exec roadmap-api-1 pip install "deepagents==0.6.12"
docker exec roadmap-api-1 python -c "import deepagents, importlib.metadata as m; print(m.version('deepagents'))"
```

Expected: `0.6.12`.

- [ ] **Step 8: Commit**

```bash
cd /c/project/roadmap
git add backend/requirements.txt backend/scripts/deepagents_smoke_test.py
git commit -m "chore(roadmap-agent): deepagents 0.6.12 도입 — 호환 스모크·기존 스위트 회귀 없음 확인

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: 생성 런 테이블 + 레포 + RunHub

**Files:**
- Create: `backend/domain/hrowth_journey/models/bases/roadmap_generation_run.py`
- Create: `backend/alembic/versions/<autogen>_add_roadmap_generation_runs.py`
- Create: `backend/domain/hrowth_journey/hub/repositories/generation_run_repository.py`
- Create: `backend/domain/hrowth_journey/spokes/infra/run_hub.py`
- Test: `backend/scripts/roadmap_generation_run_test.py`

**Interfaces:**
- Produces:
  - `GenerationRunRepository(session)` — `async create_run(user_id, trigger) -> dict | None`(활성 run 있으면 None), `async fetch_latest(user_id) -> dict | None`(stale lazy 마킹 포함), `async update_progress(run_id, progress: dict) -> None`, `async finish(run_id, status, result=None, error=None) -> None`. run dict 키: `run_id, status, trigger, progress, result, error, started_at, finished_at`.
  - `run_hub` 모듈 싱글턴 — `subscribe(user_id) -> asyncio.Queue`, `unsubscribe(user_id, q)`, `publish(user_id, event: dict)`.

- [ ] **Step 1: ORM 모델 작성**

`backend/domain/hrowth_journey/models/bases/roadmap_generation_run.py`:

```python
# 로드맵 생성 런 ORM — 사용자당 활성(pending/running) 1개, 진행률·결과 JSONB 기록
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from core.database import Base


class RoadmapGenerationRun(Base):
    __tablename__ = "roadmap_generation_runs"
    __table_args__ = (
        Index(
            "uq_roadmap_gen_run_active",
            "user_id",
            unique=True,
            postgresql_where=text("status IN ('pending','running')"),
        ),
        {"comment": "로드맵 딥 에이전트 생성 런 — 사용자당 활성 1개, 진행률 JSONB"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, unique=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", name="fk_roadmap_gen_run_user", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # pending | running | succeeded | failed
    status: Mapped[str] = mapped_column(String(12), nullable=False, server_default="pending")
    # tab | coach
    trigger: Mapped[str] = mapped_column(String(10), nullable=False, server_default="tab")
    progress: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
```

`backend/domain/hrowth_journey/models/bases/__init__.py`에 기존 스타일대로 import를 추가한다(파일을 열어 기존 나열을 확인 후 `RoadmapGenerationRun` 한 줄 추가).

- [ ] **Step 2: 마이그레이션 생성·검토**

```bash
cd /c/project/roadmap/backend && python -m alembic heads
python -m alembic revision --autogenerate -m "add roadmap_generation_runs"
```

- `alembic heads`가 다중 head를 보고하면 멈추지 말고 플래너 계보(`e7b3a1c5d9f2`의 후손) head에 `--head <rev>@head`로 체인한다. 생성 파일을 열어 **roadmap_generation_runs 외의 무관 diff는 전부 제거**하고, 부분 유니크 인덱스(`postgresql_where`)가 포함됐는지 확인한다(autogenerate가 놓치면 `op.create_index(..., postgresql_where=sa.text("status IN ('pending','running')"), unique=True)` 수동 추가).

```bash
python -m alembic upgrade head
```

Expected: 적용 성공. Neon에서 `\d roadmap_generation_runs` 상당(psql 불가 시 아래 테스트가 검증).

- [ ] **Step 3: 레포 작성**

`backend/domain/hrowth_journey/hub/repositories/generation_run_repository.py`:

```python
# 로드맵 생성 런 리포지토리 — 활성 run 유니크 보장·stale lazy 마킹·진행률 갱신
from __future__ import annotations

import json
import uuid

from sqlalchemy import text

from domain.auth.hub.repositories.base_repository import BaseRepository

_STALE_MINUTES = 10

_INSERT_RUN = text(
    """
    INSERT INTO roadmap_generation_runs (run_id, user_id, status, trigger, started_at, updated_at)
    VALUES (CAST(:run_id AS UUID), CAST(:user_id AS UUID), 'running', :trigger, now(), now())
    ON CONFLICT (user_id) WHERE status IN ('pending','running') DO NOTHING
    RETURNING run_id, status, trigger
    """
)

_MARK_STALE = text(
    """
    UPDATE roadmap_generation_runs
    SET status = 'failed', error = 'stale', finished_at = now(), updated_at = now()
    WHERE user_id = CAST(:user_id AS UUID)
      AND status IN ('pending','running')
      AND updated_at < now() - make_interval(mins => :stale_min)
    """
)

_FETCH_LATEST = text(
    """
    SELECT run_id, status, trigger, progress, result, error, started_at, finished_at
    FROM roadmap_generation_runs
    WHERE user_id = CAST(:user_id AS UUID)
    ORDER BY id DESC
    LIMIT 1
    """
)

_UPDATE_PROGRESS = text(
    """
    UPDATE roadmap_generation_runs
    SET progress = CAST(:progress AS JSONB), updated_at = now()
    WHERE run_id = CAST(:run_id AS UUID)
    """
)

_FINISH_RUN = text(
    """
    UPDATE roadmap_generation_runs
    SET status = :status, result = CAST(:result AS JSONB), error = :error,
        finished_at = now(), updated_at = now()
    WHERE run_id = CAST(:run_id AS UUID)
    """
)


def _row_to_dict(r) -> dict:
    return {
        "run_id": str(r.run_id),
        "status": r.status,
        "trigger": r.trigger,
        "progress": r.progress,
        "result": r.result,
        "error": r.error,
        "started_at": r.started_at.isoformat() if r.started_at else None,
        "finished_at": r.finished_at.isoformat() if r.finished_at else None,
    }


class GenerationRunRepository(BaseRepository):
    async def create_run(self, user_id: str, trigger: str) -> dict | None:
        """활성 run이 없으면 running 으로 생성. 있으면 None(이미 진행 중)."""
        # 좀비가 자리를 차지하지 않도록 생성 직전에 stale 정리.
        await self.session.execute(
            _MARK_STALE, {"user_id": user_id, "stale_min": _STALE_MINUTES}
        )
        row = (
            await self.session.execute(
                _INSERT_RUN,
                {"run_id": str(uuid.uuid4()), "user_id": user_id, "trigger": trigger},
            )
        ).first()
        await self.session.commit()
        if row is None:
            return None
        return {"run_id": str(row.run_id), "status": row.status, "trigger": row.trigger}

    async def fetch_latest(self, user_id: str) -> dict | None:
        """최근 run 1건 — 조회 시점에 stale run 을 failed 로 lazy 마킹한다."""
        await self.session.execute(
            _MARK_STALE, {"user_id": user_id, "stale_min": _STALE_MINUTES}
        )
        await self.session.commit()
        r = (await self.session.execute(_FETCH_LATEST, {"user_id": user_id})).first()
        return _row_to_dict(r) if r else None

    async def update_progress(self, run_id: str, progress: dict) -> None:
        await self.session.execute(
            _UPDATE_PROGRESS, {"run_id": run_id, "progress": json.dumps(progress, ensure_ascii=False)}
        )
        await self.session.commit()

    async def finish(
        self, run_id: str, status: str, result: dict | None = None, error: str | None = None
    ) -> None:
        await self.session.execute(
            _FINISH_RUN,
            {
                "run_id": run_id,
                "status": status,
                "result": json.dumps(result, ensure_ascii=False) if result else None,
                "error": error,
            },
        )
        await self.session.commit()
```

- [ ] **Step 4: RunHub 작성**

`backend/domain/hrowth_journey/spokes/infra/run_hub.py` (`spokes/infra/`에 `__init__.py`가 없으면 빈 파일 생성):

```python
# 생성 런 인프로세스 브로드캐스트 허브 — user_id 별 SSE 구독 큐 팬아웃
from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger(__name__)

_QUEUE_MAX = 200


class RunHub:
    """user_id → 구독 큐 집합. 프로세스 로컬(진실원본은 DB progress)."""

    def __init__(self) -> None:
        self._subs: dict[str, set[asyncio.Queue]] = {}

    def subscribe(self, user_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=_QUEUE_MAX)
        self._subs.setdefault(user_id, set()).add(q)
        return q

    def unsubscribe(self, user_id: str, q: asyncio.Queue) -> None:
        subs = self._subs.get(user_id)
        if subs is not None:
            subs.discard(q)
            if not subs:
                self._subs.pop(user_id, None)

    def publish(self, user_id: str, event: dict) -> None:
        for q in self._subs.get(user_id, ()):  # 구독자 없으면 무동작.
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:  # 느린 구독자는 이벤트를 잃는다 — DB 스냅샷이 보정.
                logger.warning("RunHub 큐 가득 참 — 이벤트 드롭")


run_hub = RunHub()
```

- [ ] **Step 5: 테스트 작성**

`backend/scripts/roadmap_generation_run_test.py` (실 DB 사용 — 끝에 생성 행 정리):

```python
# 생성 런 레포·RunHub 테스트 — 활성 유니크·stale 마킹·진행률 갱신·팬아웃
from __future__ import annotations

import asyncio
import sys
import uuid
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


async def main() -> int:
    from sqlalchemy import text

    from core.database import AsyncSessionLocal
    from domain.hrowth_journey.hub.repositories.generation_run_repository import (
        GenerationRunRepository,
    )
    from domain.hrowth_journey.spokes.infra.run_hub import RunHub

    async with AsyncSessionLocal() as db:
        row = (await db.execute(text("SELECT id FROM users ORDER BY created_at DESC LIMIT 1"))).first()
        if row is None:
            print("SKIP: users 비어 있음")
            return 1
        user_id = str(row[0])

    async with AsyncSessionLocal() as db:
        repo = GenerationRunRepository(db)
        # 잔여 활성 run 정리(이전 실패 잔재).
        await db.execute(
            text("DELETE FROM roadmap_generation_runs WHERE user_id = CAST(:u AS UUID)"),
            {"u": user_id},
        )
        await db.commit()

        run = await repo.create_run(user_id, "tab")
        check("create_run 성공", run is not None and run["status"] == "running")
        dup = await repo.create_run(user_id, "coach")
        check("활성 중복 create_run 차단", dup is None)

        await repo.update_progress(run["run_id"], {"stage": "market", "percent": 30})
        latest = await repo.fetch_latest(user_id)
        check("progress 반영", latest is not None and (latest["progress"] or {}).get("percent") == 30)
        check("run_id 일치", latest["run_id"] == run["run_id"])

        # stale: updated_at 을 과거로 조작 → fetch_latest 가 failed(stale) 마킹.
        await db.execute(
            text(
                "UPDATE roadmap_generation_runs SET updated_at = now() - interval '11 minutes' "
                "WHERE run_id = CAST(:r AS UUID)"
            ),
            {"r": run["run_id"]},
        )
        await db.commit()
        latest = await repo.fetch_latest(user_id)
        check("stale run failed 마킹", latest["status"] == "failed" and latest["error"] == "stale")

        # stale 이후 새 run 생성 가능.
        run2 = await repo.create_run(user_id, "coach")
        check("stale 후 재생성 가능", run2 is not None)
        await repo.finish(run2["run_id"], "succeeded", result={"source": "llm", "quest_count": 5})
        latest = await repo.fetch_latest(user_id)
        check("finish 반영", latest["status"] == "succeeded" and latest["result"]["quest_count"] == 5)
        check("finished_at 기록", latest["finished_at"] is not None)

        await db.execute(
            text("DELETE FROM roadmap_generation_runs WHERE user_id = CAST(:u AS UUID)"),
            {"u": user_id},
        )
        await db.commit()

    hub = RunHub()
    q1 = hub.subscribe("u1")
    q2 = hub.subscribe("u1")
    q_other = hub.subscribe("u2")
    hub.publish("u1", {"type": "progress"})
    check("구독자 팬아웃", q1.qsize() == 1 and q2.qsize() == 1)
    check("타 사용자 격리", q_other.qsize() == 0)
    hub.unsubscribe("u1", q1)
    hub.publish("u1", {"type": "done"})
    check("해지 후 미수신", q1.qsize() == 1 and q2.qsize() == 2)

    print(f"\nRESULT: PASS {_pass} / FAIL {_fail}")
    return 0 if _fail == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
```

- [ ] **Step 6: 실행·확인**

```bash
cd /c/project/roadmap/backend && python scripts/roadmap_generation_run_test.py
```

Expected: `RESULT: PASS 10 / FAIL 0`.

- [ ] **Step 7: Commit**

```bash
cd /c/project/roadmap
git add backend/domain/hrowth_journey/models/bases/ backend/domain/hrowth_journey/hub/repositories/generation_run_repository.py backend/domain/hrowth_journey/spokes/infra/ backend/alembic/versions/ backend/scripts/roadmap_generation_run_test.py
git commit -m "feat(roadmap-agent): 생성 런 상태 모델 — runs 테이블(활성 유니크·stale lazy)·레포·RunHub

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: 진행 보존 병합 + save_roadmap_merged + WBS 시드 필터

**Files:**
- Create: `backend/domain/hrowth_journey/hub/services/roadmap_merge.py`
- Modify: `backend/domain/hrowth_journey/hub/repositories/roadmap_repository.py`
- Test: `backend/scripts/roadmap_merge_test.py`

**Interfaces:**
- Consumes: `_parse_roadmap`(core/llm/client.py — 루트 1개 강제 검증)의 출력 형태 `{title, summary, skill_pillars, bridge_keywords, quests:[{quest_key,parent_key,title,purpose,difficulty,keywords,state,sort_order}]}`.
- Produces:
  - `merge_roadmap(old_quests: list[dict], new_roadmap: dict, planner_keys: set[str]) -> dict` — 병합된 로드맵(무네트워크 순수 함수).
  - `validate_wbs_tasks(raw_tasks, merged_quests, existing_task_keys: set[str]) -> list[dict]` — 시드 가능한 태스크만 `{quest_key,title,description,estimated_days}`로 정제.
  - `RoadmapRepository.save_roadmap_merged(user_id, roadmap) -> int` — diff upsert(전체 DELETE 없음).
  - `RoadmapRepository.fetch_quest_rows(user_id) -> list[dict]`, `RoadmapRepository.fetch_planner_quest_keys(user_id) -> set[str]`.

- [ ] **Step 1: 병합 순수 함수 작성**

`backend/domain/hrowth_journey/hub/services/roadmap_merge.py`:

```python
# 로드맵 진행 보존 병합 — done/active·플래너 연결 생존을 코드로 강제(무네트워크 순수 함수)
from __future__ import annotations

_PRESERVED_STATES = {"done", "active"}
_VALID_REINSERT_STATES = {"done", "active", "available", "locked"}
_MAX_TASKS_PER_QUEST = 5
_MAX_EST_DAYS = 90


def merge_roadmap(old_quests: list[dict], new_roadmap: dict, planner_keys: set[str]) -> dict:
    """에이전트 산출을 기존 트리와 병합한다. new_roadmap 은 _parse_roadmap 검증 통과본.

    규칙:
    1. 살아남은 key 가 기존 done/active 면 state 무조건 보존(에이전트 제안 무시).
    2. 새 key 는 done 금지(available 강등). start 는 루트만(비루트 start 는 available 강등).
    3. 사라진 key 중 done 또는 플래너 참조 퀘스트는 자동 재삽입(원 부모 생존 시 그 아래, 아니면 새 루트 아래).
       재삽입 노드가 옛 루트(parent None)였으면 새 루트 아래로 편입, start 상태는 done 으로 강등.
    4. 사라진 미진행·미참조 퀘스트는 삭제 허용.
    """
    old_by_key = {q["quest_key"]: q for q in old_quests}
    new_quests = [dict(q) for q in new_roadmap["quests"]]
    new_keys = {q["quest_key"] for q in new_quests}
    root_key = next(q["quest_key"] for q in new_quests if q["parent_key"] is None)

    for q in new_quests:
        old = old_by_key.get(q["quest_key"])
        if old is not None and old["state"] in _PRESERVED_STATES:
            q["state"] = old["state"]
        elif old is None and q["state"] == "done":
            q["state"] = "available"
        if q["state"] == "start" and q["parent_key"] is not None:
            q["state"] = "available"

    reinserted = []
    for key, old in old_by_key.items():
        if key in new_keys:
            continue
        if old["state"] != "done" and key not in planner_keys:
            continue  # 미진행·미참조 — 삭제 허용.
        parent = old.get("parent_key")
        if parent is None or parent not in new_keys:
            parent = root_key
        state = old["state"] if old["state"] in _VALID_REINSERT_STATES else "done"
        reinserted.append(
            {
                "quest_key": key,
                "parent_key": parent,
                "title": old["title"],
                "purpose": old.get("purpose") or "",
                "difficulty": old.get("difficulty") or "입문",
                "keywords": old.get("keywords") or [],
                "state": state,
                "sort_order": 900 + len(reinserted),  # 뒤쪽 배치 — 형제 정렬 안정.
            }
        )

    return {**new_roadmap, "quests": new_quests + reinserted}


def validate_wbs_tasks(
    raw_tasks, merged_quests: list[dict], existing_task_keys: set[str]
) -> list[dict]:
    """WBS 초안 검증 — 병합 트리에 있는 미완료·태스크 없는 퀘스트에만, 퀘스트당 최대 5개."""
    if not isinstance(raw_tasks, list):
        return []
    valid_keys = {q["quest_key"] for q in merged_quests}
    done_keys = {q["quest_key"] for q in merged_quests if q["state"] == "done"}
    out: list[dict] = []
    per_quest: dict[str, int] = {}
    for t in raw_tasks:
        if not isinstance(t, dict):
            continue
        key = t.get("quest_key")
        title = t.get("title")
        if not isinstance(key, str) or key not in valid_keys or key in done_keys:
            continue
        if key in existing_task_keys:
            continue  # 이미 태스크가 있는 퀘스트는 시드 스킵(소스 불문).
        if not isinstance(title, str) or not title.strip():
            continue
        if per_quest.get(key, 0) >= _MAX_TASKS_PER_QUEST:
            continue
        est = t.get("estimated_days")
        if not isinstance(est, int) or not (1 <= est <= _MAX_EST_DAYS):
            est = None
        desc = t.get("description")
        out.append(
            {
                "quest_key": key,
                "title": title.strip()[:200],
                "description": desc.strip()[:2000] if isinstance(desc, str) and desc.strip() else None,
                "estimated_days": est,
            }
        )
        per_quest[key] = per_quest.get(key, 0) + 1
    return out
```

- [ ] **Step 2: 레포에 diff upsert·조회 추가**

`backend/domain/hrowth_journey/hub/repositories/roadmap_repository.py` — 모듈 상수 영역에 추가:

```python
from sqlalchemy import bindparam

_UPSERT_QUEST = text(
    """
    INSERT INTO roadmap_quests
        (roadmap_id, quest_key, parent_key, title, purpose, difficulty, keywords, state, sort_order)
    VALUES (:roadmap_id, :quest_key, :parent_key, :title, :purpose, :difficulty,
            CAST(:keywords AS JSONB), :state, :sort_order)
    ON CONFLICT (roadmap_id, quest_key) DO UPDATE SET
        parent_key = EXCLUDED.parent_key, title = EXCLUDED.title, purpose = EXCLUDED.purpose,
        difficulty = EXCLUDED.difficulty, keywords = EXCLUDED.keywords,
        state = EXCLUDED.state, sort_order = EXCLUDED.sort_order
    """
)

_DELETE_QUESTS_NOT_IN = text(
    "DELETE FROM roadmap_quests WHERE roadmap_id = :roadmap_id AND quest_key NOT IN :keys"
).bindparams(bindparam("keys", expanding=True))

_FETCH_PLANNER_QUEST_KEYS = text(
    """
    SELECT DISTINCT quest_key FROM planner_tasks
    WHERE user_id = CAST(:user_id AS UUID) AND quest_key IS NOT NULL
    """
)
```

클래스에 메서드 추가(기존 `save_roadmap` 바로 아래):

```python
    async def save_roadmap_merged(self, user_id: str, roadmap: dict) -> int:
        """병합 저장 — 헤더 upsert + 퀘스트 diff upsert. 전체 DELETE 없음(부분 실패에도 트리 무손상)."""
        rid = (
            await self.session.execute(
                _UPSERT_ROADMAP,
                {
                    "user_id": user_id,
                    "title": roadmap["title"],
                    "summary": roadmap.get("summary") or "",
                    "pillars": json.dumps(roadmap.get("skill_pillars") or []),
                    "bridge": json.dumps(roadmap.get("bridge_keywords") or []),
                },
            )
        ).scalar_one()
        quests = roadmap.get("quests") or []
        for q in quests:
            await self.session.execute(
                _UPSERT_QUEST,
                {
                    "roadmap_id": rid,
                    "quest_key": q["quest_key"],
                    "parent_key": q.get("parent_key"),
                    "title": q["title"],
                    "purpose": q.get("purpose") or "",
                    "difficulty": q["difficulty"],
                    "keywords": json.dumps(q.get("keywords") or []),
                    "state": q["state"],
                    "sort_order": q.get("sort_order") or 0,
                },
            )
        keys = [q["quest_key"] for q in quests]
        if keys:
            await self.session.execute(
                _DELETE_QUESTS_NOT_IN, {"roadmap_id": rid, "keys": keys}
            )
        await self.session.commit()
        return rid

    async def fetch_quest_rows(self, user_id: str) -> list[dict]:
        """병합 입력용 — 사용자의 현재 퀘스트 행 전부(로드맵 없으면 빈 목록)."""
        header = (await self.session.execute(_FETCH_ROADMAP, {"user_id": user_id})).first()
        if header is None:
            return []
        rows = (
            await self.session.execute(_FETCH_QUESTS, {"roadmap_id": header.id})
        ).mappings().all()
        return [dict(r) for r in rows]

    async def fetch_planner_quest_keys(self, user_id: str) -> set[str]:
        rows = (
            await self.session.execute(_FETCH_PLANNER_QUEST_KEYS, {"user_id": user_id})
        ).all()
        return {r[0] for r in rows}
```

- [ ] **Step 3: 테스트 작성**

`backend/scripts/roadmap_merge_test.py` (순수 함수만 — 무DB·무네트워크):

```python
# 병합·WBS 검증 순수 함수 테스트 — done/active 보존·재삽입·시드 스킵 정책
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


def q(key, parent, state="available", title=None, sort=0):
    return {
        "quest_key": key, "parent_key": parent, "title": title or key,
        "purpose": "", "difficulty": "입문", "keywords": [], "state": state,
        "sort_order": sort,
    }


def main() -> int:
    from domain.hrowth_journey.hub.services.roadmap_merge import (
        merge_roadmap,
        validate_wbs_tasks,
    )

    old = [
        q("root", None, "start"),
        q("q-a", "root", "done"),
        q("q-b", "root", "active"),
        q("q-c", "q-b", "available"),
        q("q-d", "root", "available"),  # 미진행·미참조 — 삭제 허용 대상.
        q("q-e", "q-d", "done"),        # done 인데 새 트리에서 사라짐 + 부모도 사라짐.
    ]
    new = {
        "title": "새 로드맵", "summary": "", "skill_pillars": [], "bridge_keywords": [],
        "quests": [
            q("root", None, "start"),
            q("q-a", "root", "available"),   # 에이전트가 상태를 되돌림 → done 보존돼야 함.
            q("q-b", "root", "locked"),      # active 보존돼야 함.
            q("q-new", "q-b", "done"),       # 새 key 의 done → available 강등.
            q("q-new2", "q-new", "start"),   # 비루트 start → available 강등.
        ],
    }
    merged = merge_roadmap(old, new, planner_keys={"q-c"})
    by_key = {x["quest_key"]: x for x in merged["quests"]}

    check("done 보존", by_key["q-a"]["state"] == "done")
    check("active 보존", by_key["q-b"]["state"] == "active")
    check("새 key done 강등", by_key["q-new"]["state"] == "available")
    check("비루트 start 강등", by_key["q-new2"]["state"] == "available")
    check("플래너 참조 재삽입", "q-c" in by_key)
    check("재삽입 부모 생존", by_key["q-c"]["parent_key"] == "q-b")
    check("사라진 done 재삽입", "q-e" in by_key)
    check("재삽입 부모 소실 시 루트", by_key["q-e"]["parent_key"] == "root")
    check("미진행 미참조 삭제", "q-d" not in by_key)
    roots = [x for x in merged["quests"] if x["parent_key"] is None]
    check("루트 1개 유지", len(roots) == 1)

    tasks = validate_wbs_tasks(
        [
            {"quest_key": "q-new", "title": "리서치", "description": "시장 조사", "estimated_days": 3},
            {"quest_key": "q-new", "title": "실습", "estimated_days": 200},   # est 범위 밖 → None.
            {"quest_key": "q-a", "title": "이미 done", "estimated_days": 2},   # done 스킵.
            {"quest_key": "q-c", "title": "이미 태스크 있음"},                  # existing 스킵.
            {"quest_key": "없는키", "title": "무효"},
            {"quest_key": "q-new2", "title": ""},                              # 빈 제목 스킵.
            {"quest_key": "q-new", "title": "3"}, {"quest_key": "q-new", "title": "4"},
            {"quest_key": "q-new", "title": "5"}, {"quest_key": "q-new", "title": "6"},  # 6번째 컷.
        ],
        merged["quests"],
        existing_task_keys={"q-c"},
    )
    keys = [t["quest_key"] for t in tasks]
    check("유효 시드만 통과", set(keys) == {"q-new"})
    check("퀘스트당 5개 상한", keys.count("q-new") == 5)
    check("est 범위 밖 None", tasks[1]["estimated_days"] is None)
    check("done 퀘스트 스킵", all(t["quest_key"] != "q-a" for t in tasks))

    print(f"\nRESULT: PASS {_pass} / FAIL {_fail}")
    return 0 if _fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: 실행**

```bash
cd /c/project/roadmap/backend && python scripts/roadmap_merge_test.py
```

Expected: `RESULT: PASS 14 / FAIL 0`.

- [ ] **Step 5: Commit**

```bash
cd /c/project/roadmap
git add backend/domain/hrowth_journey/hub/services/roadmap_merge.py backend/domain/hrowth_journey/hub/repositories/roadmap_repository.py backend/scripts/roadmap_merge_test.py
git commit -m "feat(roadmap-agent): 진행 보존 병합 — done/active·플래너 연결 생존 + diff upsert 저장·WBS 시드 검증

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: 딥 에이전트 빌더 + 프롬프트 + settings

**Files:**
- Modify: `backend/core/config/settings.py` (코치 LLM 블록 아래)
- Create: `backend/domain/hrowth_journey/spokes/agents/roadmap_agent_prompts.py`
- Create: `backend/domain/hrowth_journey/spokes/agents/roadmap_deep_agent.py`
- Test: `backend/scripts/roadmap_deep_agent_build_test.py`

**Interfaces:**
- Consumes: `build_internal_tools(user_id)`(ai_coach, tool 이름 get_pulse_trends/get_gap_issues/get_chance_matches/get_sync_snapshot/get_user_profile/search_insights), `build_web_tools()`(web_search/fetch_url, 키 없으면 목록 제외), `resolve_coach_llm(settings)`, Task 1의 deepagents 임포트 경로.
- Produces:
  - `build_roadmap_deep_agent(user_id, settings=None) -> CompiledStateGraph`.
  - `build_subagent_specs(user_id, settings) -> list[dict]`(테스트 노출용).
  - `parse_agent_output(final_state) -> tuple[dict, list]`(검증된 roadmap dict 또는 `{}`, raw tasks list).
  - `build_generation_brief(persona_context, old_quests, planner_keys) -> str` — 오케스트레이터 초기 메시지.
  - settings: `roadmap_agent_cheap_model`(기본 "claude-haiku-4-5"), `roadmap_agent_timeout_s`(300), `roadmap_agent_recursion_limit`(50), `roadmap_agent_web_call_limit`(6).

- [ ] **Step 1: settings 추가**

`backend/core/config/settings.py`의 `# 코치 웹 tool (C-2)` 블록 아래에:

```python
    # 로드맵 딥 에이전트 (R-1)
    roadmap_agent_cheap_model: str = Field(
        default="claude-haiku-4-5", validation_alias="ROADMAP_AGENT_CHEAP_MODEL"
    )
    roadmap_agent_timeout_s: int = Field(default=300, validation_alias="ROADMAP_AGENT_TIMEOUT_S")
    roadmap_agent_recursion_limit: int = Field(
        default=50, validation_alias="ROADMAP_AGENT_RECURSION_LIMIT"
    )
    roadmap_agent_web_call_limit: int = Field(
        default=6, validation_alias="ROADMAP_AGENT_WEB_CALL_LIMIT"
    )
```

- [ ] **Step 2: 프롬프트 모듈 작성**

`backend/domain/hrowth_journey/spokes/agents/roadmap_agent_prompts.py` (`spokes/agents/`에 `__init__.py` 없으면 빈 파일 생성):

```python
# 로드맵 딥 에이전트 프롬프트 — 오케스트레이터·서브에이전트 3종·생성 브리프 조립
from __future__ import annotations

import json

RESULT_FILE = "roadmap_result.json"

ORCHESTRATOR_PROMPT = """당신은 Roadmap 플랫폼의 로드맵 설계 오케스트레이터다. 청년 사용자의 성장 로드맵
(퀘스트 트리 + 실행 태스크 초안)을 서브에이전트들과 함께 설계한다.

[절차 — 반드시 이 순서로]
1. write_todos 로 작업 계획을 만든다.
2. task 로 market_analyst 를 호출해 시장 분석을 /market_analysis.md 에 쓰게 한다.
3. task 로 opportunity_scout 를 호출해 기회 조사를 /opportunities.md 에 쓰게 한다.
4. task 로 quest_designer 를 호출해 퀘스트 트리 초안을 /quest_tree_draft.json 에 쓰게 한다.
5. 초안을 읽고 최종 검토·보정한 뒤, 최종 산출 JSON 을 /roadmap_result.json 에 write_file 로 쓴다.

[최종 산출 JSON 스키마 — /roadmap_result.json]
{
  "title": "로드맵 제목(120자 이내)",
  "summary": "한 줄 요약",
  "skill_pillars": [{"id": "pillar-...", "label": "역량축", "blurb": "설명"}],   // 정확히 3개
  "bridge_keywords": ["키워드"],                                                  // 3~8개
  "quests": [{"quest_key": "...", "parent_key": null 또는 "부모key", "title": "...",
              "purpose": "...", "difficulty": "입문|중급|심화", "keywords": ["..."],
              "state": "start|available|active|done|locked", "sort_order": 0}],
  "tasks": [{"quest_key": "...", "title": "실행 태스크", "description": "...", "estimated_days": 3}]
}

[퀘스트 규칙]
- parent_key 가 null 인 루트는 정확히 1개. 나머지는 존재하는 quest_key 를 부모로 가진다.
- 퀘스트는 8~15개, 깊이 2~4. 브리프의 기존 트리가 있으면: 같은 의미의 퀘스트는 기존
  quest_key 를 반드시 재사용하고, done 퀘스트는 트리에서 제거하지 않는다.
- tasks 는 새로 만들거나 크게 바뀐 퀘스트에만, 퀘스트당 2~4개(전체 20개 이내).

[원칙]
- 근거는 서브에이전트가 조회한 실데이터. 수치·공고를 지어내지 않는다.
- 사용자 성향(quest_designer 가 조회)과 시장 신호를 잇는 것이 로드맵의 가치다.
- 서브에이전트 호출은 각 1회씩만. 재호출하지 않는다.
"""

MARKET_ANALYST_PROMPT = """당신은 시장 분석가다. tool 로 실데이터를 조회해 청년 진로 관점의 시장 분석을 쓴다.
- get_pulse_trends 로 섹터 트렌드·모멘텀, get_gap_issues 로 미해결 기회, get_sync_snapshot 으로
  사용자 섹터 적합도를 조회한다. tool 호출은 총 5회 이내.
- 결과를 /market_analysis.md 에 write_file 로 쓴다: 유망 방향 후보 3~5개(섹터·근거 수치·기회 신호·
  사용자 적합도 연결). 파일 작성이 완료 조건이다."""

OPPORTUNITY_SCOUT_PROMPT = """당신은 기회 스카우트다. 실행 가능한 기회(공고·프로그램·학습 자원)를 수집한다.
- get_chance_matches 로 맞춤 공고를 먼저 조회한다. web_search 는 최신 동향·요건 확인이 필요할 때만
  최대 3회, 본문 확인이 꼭 필요할 때만 fetch_url 을 쓴다. tool 호출은 총 5회 이내.
- 결과를 /opportunities.md 에 write_file 로 쓴다: 기회 목록(제목·유형·요건·마감·출처 URL).
  웹 출처는 URL 을 반드시 남긴다. 파일 작성이 완료 조건이다."""

QUEST_DESIGNER_PROMPT = """당신은 퀘스트 설계자다. 사용자 성향과 시장 분석을 잇는 퀘스트 트리를 설계한다.
- get_user_profile 로 자기모델(성향·근거·상담 요약)을 조회하고, read_file 로 /market_analysis.md 와
  /opportunities.md 를 읽는다. tool 호출은 총 5회 이내.
- 오케스트레이터 브리프의 최종 산출 스키마와 동일한 형태(tasks 포함)의 초안 JSON 을
  /quest_tree_draft.json 에 write_file 로 쓴다. 기존 트리가 있으면 quest_key 재사용·done 유지 규칙을
  지킨다. 파일 작성이 완료 조건이다."""


def build_generation_brief(
    persona_context: str, old_quests: list[dict], planner_keys: set[str]
) -> str:
    """오케스트레이터 초기 메시지 — 사용자 맥락 + 기존 트리 + 보존 규칙."""
    parts = ["다음 사용자의 성장 로드맵을 설계하라.", "", "[사용자·시장 맥락]", persona_context]
    if old_quests:
        done = sorted(q["quest_key"] for q in old_quests if q["state"] == "done")
        active = sorted(q["quest_key"] for q in old_quests if q["state"] == "active")
        slim = [
            {k: q[k] for k in ("quest_key", "parent_key", "title", "state")} for q in old_quests
        ]
        parts += [
            "",
            "[기존 퀘스트 트리 — 재생성 모드]",
            json.dumps(slim, ensure_ascii=False),
            f"[완료(done) — 제거 금지] {', '.join(done) or '없음'}",
            f"[진행중(active)] {', '.join(active) or '없음'}",
            f"[플래너 태스크가 참조 중 — 제거 금지] {', '.join(sorted(planner_keys)) or '없음'}",
            "같은 의미의 퀘스트는 위 quest_key 를 그대로 재사용하라.",
        ]
    else:
        parts += ["", "[기존 트리 없음 — 최초 생성 모드]"]
    return "\n".join(parts)
```

- [ ] **Step 3: 딥 에이전트 빌더 작성**

`backend/domain/hrowth_journey/spokes/agents/roadmap_deep_agent.py`:

```python
# 로드맵 딥 에이전트 빌더 — deepagents 서브에이전트 3종·모델 믹스·산출 파싱(3단 폴백)
from __future__ import annotations

import json
import logging
import re

from langchain_core.tools import StructuredTool

from core.llm.client import _parse_roadmap

logger = logging.getLogger(__name__)

RESULT_FILE_CANDIDATES = ("/roadmap_result.json", "roadmap_result.json")


def _limited(tools: list, limit: int) -> list:
    """웹 tool 공유 호출 카운터 래핑 — 상한 초과 시 error dict 반환(대화 비파괴)."""
    counter = {"n": 0}
    wrapped = []
    for t in tools:
        async def _run(_t=t, **kwargs):
            if counter["n"] >= limit:
                return {"error": "웹 호출 한도를 초과했습니다. 지금까지 수집한 정보로 진행하세요."}
            counter["n"] += 1
            return await _t.ainvoke(kwargs)

        wrapped.append(
            StructuredTool(
                name=t.name, description=t.description,
                args_schema=t.args_schema, coroutine=_run,
            )
        )
    return wrapped


def _chat_model(model_name: str, api_key: str, max_tokens: int):
    from langchain_anthropic import ChatAnthropic

    # Sonnet 5 는 thinking 미지정 시 adaptive 활성 → tool 라운드 재전송 400. 반드시 비활성 명시.
    return ChatAnthropic(
        model=model_name, api_key=api_key, max_tokens=max_tokens,
        thinking={"type": "disabled"},
    )


def build_subagent_specs(user_id: str, settings=None) -> list[dict]:
    """서브에이전트 3종 선언 — tools 명시 리스트(task 미포함=재귀 스폰 차단)."""
    from core.config.settings import get_settings
    from core.llm.provider import resolve_coach_llm
    from domain.ai_coach.spokes.agents.tools.internal_tools import build_internal_tools
    from domain.ai_coach.spokes.agents.tools.web_tools import build_web_tools

    from domain.hrowth_journey.spokes.agents.roadmap_agent_prompts import (
        MARKET_ANALYST_PROMPT,
        OPPORTUNITY_SCOUT_PROMPT,
        QUEST_DESIGNER_PROMPT,
    )

    settings = settings or get_settings()
    api_key, sonnet_model = resolve_coach_llm(settings)
    cheap = _chat_model(settings.roadmap_agent_cheap_model, api_key, 4096)
    sonnet = _chat_model(sonnet_model, api_key, 8192)

    internal = {t.name: t for t in build_internal_tools(user_id)}
    web = _limited(build_web_tools(settings), settings.roadmap_agent_web_call_limit)

    return [
        {
            "name": "market_analyst",
            "description": "시장 트렌드·미해결 기회·사용자 적합도를 종합해 유망 방향 후보를 분석한다.",
            "system_prompt": MARKET_ANALYST_PROMPT,
            "tools": [internal["get_pulse_trends"], internal["get_gap_issues"], internal["get_sync_snapshot"]],
            "model": cheap,
        },
        {
            "name": "opportunity_scout",
            "description": "맞춤 공고와 웹 최신 동향으로 실행 가능한 기회·요건을 수집한다.",
            "system_prompt": OPPORTUNITY_SCOUT_PROMPT,
            "tools": [internal["get_chance_matches"], *web],
            "model": cheap,
        },
        {
            "name": "quest_designer",
            "description": "사용자 자기모델과 시장 분석을 잇는 퀘스트 트리 초안을 설계한다.",
            "system_prompt": QUEST_DESIGNER_PROMPT,
            "tools": [internal["get_user_profile"]],
            "model": sonnet,
        },
    ]


def build_roadmap_deep_agent(user_id: str, settings=None):
    """딥 에이전트 컴파일 — 오케스트레이터 Sonnet, 기본 StateBackend(스레드 스코프 가상 FS)."""
    from deepagents import create_deep_agent

    from core.config.settings import get_settings
    from core.llm.provider import resolve_coach_llm
    from domain.hrowth_journey.spokes.agents.roadmap_agent_prompts import ORCHESTRATOR_PROMPT

    settings = settings or get_settings()
    api_key, sonnet_model = resolve_coach_llm(settings)
    return create_deep_agent(
        model=_chat_model(sonnet_model, api_key, 8192),
        system_prompt=ORCHESTRATOR_PROMPT,
        subagents=build_subagent_specs(user_id, settings),
    )


def _extract_json_block(content) -> dict | None:
    """AIMessage content(문자열/블록 리스트)에서 마지막 JSON 오브젝트 추출."""
    if isinstance(content, list):
        content = "".join(
            b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"
        )
    if not isinstance(content, str):
        return None
    matches = re.findall(r"\{[\s\S]*\}", content)
    for raw in reversed(matches):
        try:
            obj = json.loads(raw)
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            continue
    return None


def parse_agent_output(final_state: dict) -> tuple[dict, list]:
    """최종 state → (검증된 roadmap dict 또는 {}, raw tasks). 1) 결과 파일 2) 마지막 AIMessage JSON."""
    obj: dict | None = None
    files = final_state.get("files") or {}
    for key in RESULT_FILE_CANDIDATES:
        raw = files.get(key)
        if raw is None:
            continue
        content = raw.get("content") if isinstance(raw, dict) else raw
        if isinstance(content, list):  # 일부 버전은 라인 리스트로 저장.
            content = "\n".join(str(x) for x in content)
        try:
            obj = json.loads(content)
            break
        except (json.JSONDecodeError, TypeError):
            logger.warning(f"결과 파일 파싱 실패({key}) — 메시지 폴백 시도")
    if obj is None:
        for msg in reversed(final_state.get("messages") or []):
            if getattr(msg, "type", None) == "ai":
                obj = _extract_json_block(getattr(msg, "content", None))
                if obj:
                    break
    if not isinstance(obj, dict):
        return {}, []
    raw_tasks = obj.get("tasks") if isinstance(obj.get("tasks"), list) else []
    roadmap = _parse_roadmap(json.dumps(obj, ensure_ascii=False))
    return roadmap, raw_tasks
```

주의: `_parse_roadmap`은 `core/llm/client.py`의 모듈 함수다. 프라이빗 이름 import가 걸리면(린트) 그대로 두되 태스크 보고에 남긴다 — 검증 규칙 단일 소스 유지가 우선.

- [ ] **Step 4: 빌드 테스트 작성**

`backend/scripts/roadmap_deep_agent_build_test.py` (무네트워크 — 더미 키로 빌드):

```python
# 딥 에이전트 빌드 테스트 — 서브에이전트 구성·task 미노출·thinking disabled·산출 파싱 폴백
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-dummy")
os.environ.setdefault("TAVILY_API_KEY", "tvly-dummy")
os.environ.setdefault("WATERCRAWL_API_KEY", "wc-dummy")

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


class _FakeAI:
    type = "ai"

    def __init__(self, content):
        self.content = content


def main() -> int:
    from core.config.settings import get_settings

    get_settings.cache_clear() if hasattr(get_settings, "cache_clear") else None

    from domain.hrowth_journey.spokes.agents.roadmap_deep_agent import (
        build_roadmap_deep_agent,
        build_subagent_specs,
        parse_agent_output,
    )
    from domain.hrowth_journey.spokes.agents.roadmap_agent_prompts import (
        build_generation_brief,
    )

    specs = build_subagent_specs("00000000-0000-0000-0000-000000000000")
    names = [s["name"] for s in specs]
    check("서브에이전트 3종", names == ["market_analyst", "opportunity_scout", "quest_designer"])
    for s in specs:
        tool_names = {t.name for t in s["tools"]}
        check(f"{s['name']} task 미노출", "task" not in tool_names)
        check(
            f"{s['name']} thinking disabled",
            getattr(s["model"], "thinking", None) == {"type": "disabled"},
        )
    check(
        "analyst tool 배분",
        {t.name for t in specs[0]["tools"]} == {"get_pulse_trends", "get_gap_issues", "get_sync_snapshot"},
    )
    check(
        "scout tool 배분(웹 포함)",
        {t.name for t in specs[1]["tools"]} == {"get_chance_matches", "web_search", "fetch_url"},
    )
    check("designer tool 배분", {t.name for t in specs[2]["tools"]} == {"get_user_profile"})
    # user_id 클로저 — LLM 인자 스키마에 user_id 없음.
    for s in specs:
        for t in s["tools"]:
            schema = t.args_schema.model_json_schema() if t.args_schema else {"properties": {}}
            check(f"{t.name} user_id 인자 없음", "user_id" not in schema.get("properties", {}))
            break  # 서브에이전트당 대표 1개만(중복 출력 방지).

    agent = build_roadmap_deep_agent("00000000-0000-0000-0000-000000000000")
    check("컴파일 astream", hasattr(agent, "astream"))

    valid = {
        "title": "T", "summary": "", "skill_pillars": [], "bridge_keywords": [],
        "quests": [{"quest_key": "root", "parent_key": None, "title": "r",
                    "difficulty": "입문", "state": "start", "sort_order": 0}],
        "tasks": [{"quest_key": "root", "title": "t1", "estimated_days": 2}],
    }
    rm, tasks = parse_agent_output({"files": {"/roadmap_result.json": json.dumps(valid, ensure_ascii=False)}})
    check("파일 경로 파싱", rm.get("title") == "T" and len(tasks) == 1)
    rm2, _ = parse_agent_output(
        {"files": {}, "messages": [_FakeAI("서문\n" + json.dumps(valid, ensure_ascii=False))]}
    )
    check("메시지 JSON 폴백", rm2.get("title") == "T")
    rm3, t3 = parse_agent_output({"files": {}, "messages": [_FakeAI("JSON 없음")]})
    check("무산출 시 빈 결과", rm3 == {} and t3 == [])
    # 루트 2개 등 스키마 위반은 _parse_roadmap 이 {} 반환.
    bad = dict(valid)
    bad["quests"] = valid["quests"] + [{"quest_key": "r2", "parent_key": None, "title": "x",
                                        "difficulty": "입문", "state": "start", "sort_order": 1}]
    rm4, _ = parse_agent_output({"files": {"/roadmap_result.json": json.dumps(bad, ensure_ascii=False)}})
    check("루트 2개 거부", rm4 == {})

    brief = build_generation_brief("[목표 직무] 데이터 분석가", [], set())
    check("최초 생성 브리프", "최초 생성 모드" in brief)
    brief2 = build_generation_brief(
        "ctx",
        [{"quest_key": "q-a", "parent_key": "root", "title": "a", "state": "done"}],
        {"q-a"},
    )
    check("재생성 브리프 done 명시", "q-a" in brief2 and "재생성 모드" in brief2)

    print(f"\nRESULT: PASS {_pass} / FAIL {_fail}")
    return 0 if _fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
```

주의: 실 `.env`가 로드되므로 `os.environ.setdefault`는 키가 이미 있으면 그대로 둔다(무해 — 어차피 네트워크 호출 없음).

- [ ] **Step 5: 실행**

```bash
cd /c/project/roadmap/backend && python scripts/roadmap_deep_agent_build_test.py
```

Expected: `RESULT: PASS 20 / FAIL 0` 안팎(체크 수는 구현 시 확정). FAIL 0 필수.

- [ ] **Step 6: Commit**

```bash
cd /c/project/roadmap
git add backend/core/config/settings.py backend/domain/hrowth_journey/spokes/agents/ backend/scripts/roadmap_deep_agent_build_test.py
git commit -m "feat(roadmap-agent): 딥 에이전트 빌더 — 서브에이전트 3종·모델 믹스·웹 상한·산출 3단 파싱

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 5: 생성 서비스 + API 3종 + 진행 이벤트

**Files:**
- Create: `backend/domain/hrowth_journey/spokes/infra/progress_events.py`
- Create: `backend/domain/hrowth_journey/hub/services/roadmap_generation_service.py`
- Modify: `backend/api/v1/roadmap/roadmap_routor.py` (refine 아래에 generate 3종 추가)
- Test: `backend/scripts/roadmap_progress_event_test.py`, `backend/scripts/roadmap_generate_endpoint_test.py`

**Interfaces:**
- Consumes: Task 2 `GenerationRunRepository`/`run_hub`, Task 3 `merge_roadmap`/`validate_wbs_tasks`/`save_roadmap_merged`, Task 4 `build_roadmap_deep_agent`/`parse_agent_output`/`build_generation_brief`, 기존 `build_planner_context`/`template_roadmap`(roadmap_planner_service), `PlannerRepository.insert_task`.
- Produces:
  - `map_agent_event(mode: str, payload) -> list[dict]` — 시맨틱 이벤트(`{"kind": "todos"|"subagent_start"|"subagent_end", ...}`).
  - `RoadmapGenerationService(session)` — `async start_run(user_id, trigger) -> dict`(`{"started": True, "run_id"}` 또는 `{"already_running": True, "run_id"}`), `stream_events(user_id) -> AsyncGenerator[str]`(SSE 직렬화 문자열).
  - SSE 이벤트 계약: `{"type": "status|progress|done|error|none", "stage"?, "percent"?, "label"?, "todos"?, "result"?, "message"?}`.
  - HTTP: `POST /api/roadmap/generate`(202/409), `GET /api/roadmap/generate/status`, `GET /api/roadmap/generate/stream`.

- [ ] **Step 1: 진행 이벤트 매퍼 작성**

`backend/domain/hrowth_journey/spokes/infra/progress_events.py`:

```python
# 딥 에이전트 스트림 청크 → 시맨틱 진행 이벤트 매핑(무네트워크 순수 함수)
from __future__ import annotations

STAGE_PERCENT = {
    "start": 5,
    "market_analyst": 30,
    "opportunity_scout": 50,
    "quest_designer": 80,
    "saving": 95,
    "done": 100,
}

STAGE_LABEL = {
    "start": "생성 준비",
    "market_analyst": "시장 분석",
    "opportunity_scout": "기회 조사",
    "quest_designer": "퀘스트 설계",
    "saving": "검증·저장",
    "done": "완료",
}


def _todos_of(update: dict) -> list | None:
    todos = update.get("todos")
    if not isinstance(todos, list):
        return None
    out = []
    for t in todos:
        if isinstance(t, dict) and t.get("content"):
            out.append({"content": str(t["content"])[:120], "status": t.get("status") or ""})
    return out


def map_agent_event(mode: str, payload) -> list[dict]:
    """astream(stream_mode=["updates","custom"]) 청크 → 시맨틱 이벤트 목록.

    반환 kind: todos(할 일 갱신) / subagent_start / subagent_end. 미해당 청크는 [].
    """
    events: list[dict] = []
    if mode != "updates" or not isinstance(payload, dict):
        return events
    for update in payload.values():
        if not isinstance(update, dict):
            continue
        todos = _todos_of(update)
        if todos is not None:
            events.append({"kind": "todos", "todos": todos})
        for msg in update.get("messages") or []:
            for tc in getattr(msg, "tool_calls", None) or []:
                if tc.get("name") == "task":
                    sub = (tc.get("args") or {}).get("subagent_type") or "unknown"
                    events.append({"kind": "subagent_start", "name": sub})
            if getattr(msg, "type", None) == "tool" and getattr(msg, "name", None) == "task":
                events.append({"kind": "subagent_end"})
    return events
```

- [ ] **Step 2: 생성 서비스 작성**

`backend/domain/hrowth_journey/hub/services/roadmap_generation_service.py`:

```python
# 로드맵 생성 런 서비스 — 백그라운드 딥 에이전트 실행·진행 브로드캐스트·검증 병합 저장
from __future__ import annotations

import asyncio
import json
import logging
import time

from sqlalchemy.ext.asyncio import AsyncSession

from core.config.settings import get_settings
from core.database import AsyncSessionLocal
from domain.hrowth_journey.hub.repositories.generation_run_repository import (
    GenerationRunRepository,
)
from domain.hrowth_journey.hub.repositories.roadmap_repository import RoadmapRepository
from domain.hrowth_journey.hub.services.roadmap_merge import merge_roadmap, validate_wbs_tasks
from domain.hrowth_journey.hub.services.roadmap_planner_service import (
    build_planner_context,
    template_roadmap,
)
from domain.hrowth_journey.spokes.infra.progress_events import (
    STAGE_LABEL,
    STAGE_PERCENT,
    map_agent_event,
)
from domain.hrowth_journey.spokes.infra.run_hub import run_hub

logger = logging.getLogger(__name__)

_SUBAGENT_ORDER = ["market_analyst", "opportunity_scout", "quest_designer"]
_PROGRESS_THROTTLE_S = 1.0
_BG_TASKS: set[asyncio.Task] = set()  # GC 방지 — 완료 시 자동 이탈.


def _sse(obj: dict) -> str:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


class RoadmapGenerationService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self._settings = get_settings()

    # ---- 발주 ----

    async def start_run(self, user_id: str, trigger: str) -> dict:
        """run 생성 + 백그라운드 실행 시작. 이미 진행 중이면 already_running."""
        run = await GenerationRunRepository(self.session).create_run(user_id, trigger)
        if run is None:
            latest = await GenerationRunRepository(self.session).fetch_latest(user_id)
            return {"already_running": True, "run_id": (latest or {}).get("run_id")}
        task = asyncio.create_task(self._execute_run(user_id, run["run_id"]))
        _BG_TASKS.add(task)
        task.add_done_callback(_BG_TASKS.discard)
        return {"started": True, "run_id": run["run_id"]}

    # ---- 실행 (백그라운드 — request 세션 사용 금지) ----

    async def _execute_run(self, user_id: str, run_id: str) -> None:
        try:
            await self._run_inner(user_id, run_id)
        except Exception as e:  # 마지막 안전망 — run 을 failed 로 남긴다.
            logger.error(f"로드맵 생성 런 실패: {e}", exc_info=True)
            try:
                async with AsyncSessionLocal() as db:
                    await GenerationRunRepository(db).finish(run_id, "failed", error=str(e)[:500])
            finally:
                run_hub.publish(user_id, {"type": "error", "message": "로드맵 생성에 실패했습니다."})

    async def _publish(self, user_id: str, run_id: str, stage: str, todos=None, throttle_state=None):
        event = {
            "type": "progress",
            "stage": stage,
            "percent": STAGE_PERCENT.get(stage, 5),
            "label": STAGE_LABEL.get(stage, stage),
        }
        if todos is not None:
            event["todos"] = todos
        run_hub.publish(user_id, event)
        now = time.monotonic()
        if throttle_state is None or now - throttle_state.get("last", 0) >= _PROGRESS_THROTTLE_S:
            if throttle_state is not None:
                throttle_state["last"] = now
            async with AsyncSessionLocal() as db:
                await GenerationRunRepository(db).update_progress(
                    run_id, {k: event[k] for k in ("stage", "percent", "label") if k in event}
                )

    async def _run_inner(self, user_id: str, run_id: str) -> None:
        from domain.hrowth_journey.spokes.agents.roadmap_agent_prompts import (
            build_generation_brief,
        )
        from domain.hrowth_journey.spokes.agents.roadmap_deep_agent import (
            build_roadmap_deep_agent,
            parse_agent_output,
        )

        throttle = {"last": 0.0}
        await self._publish(user_id, run_id, "start", throttle_state=throttle)

        # 1) 입력 수집.
        async with AsyncSessionLocal() as db:
            repo = RoadmapRepository(db)
            persona = await repo.fetch_persona(user_id)
            sync = await repo.fetch_sync_profile(user_id)
            movers = await repo.fetch_top_movers()
            gaps = await repo.fetch_recent_gaps()
            old_quests = await repo.fetch_quest_rows(user_id)
            planner_keys = await repo.fetch_planner_quest_keys(user_id)
        context = build_planner_context(
            persona, sync["target_job"], sync["interest_keywords"], movers, gaps
        )
        brief = build_generation_brief(context, old_quests, planner_keys)

        # 2) 딥 에이전트 실행(타임아웃 가드) — 스트림 소비하며 최종 state 확보.
        agent = build_roadmap_deep_agent(user_id, self._settings)
        config = {"recursion_limit": self._settings.roadmap_agent_recursion_limit}
        final_state: dict = {}
        subagent_done = 0
        try:
            async with asyncio.timeout(self._settings.roadmap_agent_timeout_s):
                async for mode, payload in agent.astream(
                    {"messages": [{"role": "user", "content": brief}]},
                    config,
                    stream_mode=["updates", "values"],
                ):
                    if mode == "values":
                        final_state = payload  # 마지막 values 가 최종 state.
                        continue
                    for ev in map_agent_event(mode, payload):
                        if ev["kind"] == "subagent_start":
                            stage = ev["name"] if ev["name"] in _SUBAGENT_ORDER else None
                            if stage:
                                await self._publish(user_id, run_id, stage, throttle_state=throttle)
                        elif ev["kind"] == "subagent_end":
                            subagent_done = min(subagent_done + 1, len(_SUBAGENT_ORDER))
                        elif ev["kind"] == "todos":
                            cur = (
                                _SUBAGENT_ORDER[subagent_done]
                                if subagent_done < len(_SUBAGENT_ORDER)
                                else "quest_designer"
                            )
                            await self._publish(
                                user_id, run_id, cur, todos=ev["todos"], throttle_state=throttle
                            )
        except TimeoutError:
            logger.warning("로드맵 딥 에이전트 타임아웃 — 폴백 경로 진입")
            final_state = {}
        except Exception as e:
            logger.warning(f"로드맵 딥 에이전트 실행 오류(폴백 경로 진입): {e}")
            final_state = {}

        # 3) 산출 검증 → 병합 → 저장 (에이전트 루프 밖 — 유일한 쓰기 경로).
        await self._publish(user_id, run_id, "saving", throttle_state=None)
        roadmap, raw_tasks = parse_agent_output(final_state) if final_state else ({}, [])
        source = "deep_agent"
        if not roadmap:
            if old_quests:
                # 기존 로드맵 보유자 — 무변경 실패(트리 무손상 보장).
                async with AsyncSessionLocal() as db:
                    await GenerationRunRepository(db).finish(
                        run_id, "failed", error="agent_output_invalid"
                    )
                run_hub.publish(
                    user_id,
                    {"type": "error", "message": "생성 결과가 유효하지 않아 기존 로드맵을 유지합니다."},
                )
                return
            roadmap = template_roadmap(persona, sync["target_job"], sync["interest_keywords"])
            raw_tasks = []
            source = "template"

        async with AsyncSessionLocal() as db:
            repo = RoadmapRepository(db)
            if old_quests and source == "deep_agent":
                merged = merge_roadmap(old_quests, roadmap, planner_keys)
                rid = await repo.save_roadmap_merged(user_id, merged)
                quests = merged["quests"]
            else:
                rid = await repo.save_roadmap(user_id, roadmap)
                quests = roadmap["quests"]

            seeded = 0
            if source == "deep_agent":
                from domain.hrowth_journey.hub.repositories.planner_repository import (
                    PlannerRepository,
                )

                existing = await repo.fetch_planner_quest_keys(user_id)
                planner_repo = PlannerRepository(db)
                for t in validate_wbs_tasks(raw_tasks, quests, existing):
                    await planner_repo.insert_task(user_id, {**t, "source": "ai"})
                    seeded += 1

            result = {
                "source": source, "quest_count": len(quests),
                "tasks_seeded": seeded, "roadmap_id": rid,
            }
            await GenerationRunRepository(db).finish(run_id, "succeeded", result=result)
        run_hub.publish(user_id, {"type": "done", "result": result})

    # ---- SSE 구독 ----

    async def stream_events(self, user_id: str):
        """활성 run 스냅샷 + 실시간 이벤트 중계. 활성 run 없으면 none 후 종료."""
        run = await GenerationRunRepository(self.session).fetch_latest(user_id)
        if run is None or run["status"] in ("succeeded", "failed"):
            if run is not None and run["status"] == "succeeded":
                yield _sse({"type": "done", "result": run["result"] or {}})
            elif run is not None and run["status"] == "failed":
                yield _sse({"type": "error", "message": run["error"] or "생성 실패"})
            else:
                yield _sse({"type": "none"})
            return
        prog = run["progress"] or {}
        yield _sse({"type": "status", "status": run["status"], **prog})
        q = run_hub.subscribe(user_id)
        try:
            while True:
                try:
                    event = await asyncio.wait_for(q.get(), timeout=30.0)
                except asyncio.TimeoutError:
                    # keepalive + DB 재확인(프로세스 재시작·이벤트 유실 대비).
                    async with AsyncSessionLocal() as db:
                        cur = await GenerationRunRepository(db).fetch_latest(user_id)
                    if cur is None or cur["status"] == "failed":
                        yield _sse({"type": "error", "message": (cur or {}).get("error") or "생성 실패"})
                        return
                    if cur["status"] == "succeeded":
                        yield _sse({"type": "done", "result": cur["result"] or {}})
                        return
                    yield _sse({"type": "status", "status": cur["status"], **(cur["progress"] or {})})
                    continue
                yield _sse(event)
                if event.get("type") in ("done", "error"):
                    return
        finally:
            run_hub.unsubscribe(user_id, q)
```

주의: `stream_mode=["updates", "values"]` — `values`의 마지막 청크가 최종 state(파일 포함)라 `ainvoke` 재실행 없이 산출을 얻는다. 스모크에서 이 형태(`(mode, payload)` 튜플)가 확인 안 되면 태스크 보고에 남기고 라이브 verify에서 실제 청크 형태를 출력해 보정한다.

- [ ] **Step 3: 라우터 추가**

`backend/api/v1/roadmap/roadmap_routor.py` — import에 `from fastapi.responses import StreamingResponse`와 `from domain.hrowth_journey.hub.services.roadmap_generation_service import RoadmapGenerationService`를 추가하고, `refine` 아래에:

```python
# ── 로드맵 딥 에이전트 생성 런 (R-1) ──


@router.post("/generate", status_code=202)
async def start_generation(
    user_id: str = Depends(get_authenticated_user_id),
    db: AsyncSession = Depends(get_db),
):
    """딥 에이전트 로드맵 생성 발주 — 202(시작) 또는 409(이미 진행 중)."""
    try:
        result = await RoadmapGenerationService(db).start_run(user_id, trigger="tab")
    except Exception as e:
        logger.error(f"Roadmap 생성 발주 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Roadmap 생성 발주 실패: {str(e)}")
    if result.get("already_running"):
        raise HTTPException(status_code=409, detail="이미 로드맵 생성이 진행 중입니다.")
    return {"success": True, "runId": result["run_id"], "status": "running"}


@router.get("/generate/status")
async def generation_status(
    user_id: str = Depends(get_authenticated_user_id),
    db: AsyncSession = Depends(get_db),
):
    """최근 생성 런 상태 — 탭 진입·폴링용(run 없으면 run: null)."""
    try:
        run = await GenerationRunRepository(db).fetch_latest(user_id)
    except Exception as e:
        logger.error(f"Roadmap 생성 상태 조회 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Roadmap 생성 상태 조회 실패: {str(e)}")
    if run is None:
        return {"success": True, "run": None}
    prog = run["progress"] or {}
    return {
        "success": True,
        "run": {
            "runId": run["run_id"], "status": run["status"], "trigger": run["trigger"],
            "stage": prog.get("stage"), "percent": prog.get("percent"),
            "label": prog.get("label"), "error": run["error"],
            "result": run["result"],
        },
    }


@router.get("/generate/stream")
async def generation_stream(
    user_id: str = Depends(get_authenticated_user_id),
    db: AsyncSession = Depends(get_db),
):
    """생성 진행률 SSE — 스냅샷 1건 후 실시간 중계."""
    service = RoadmapGenerationService(db)
    return StreamingResponse(
        service.stream_events(user_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
```

`GenerationRunRepository` import도 라우터 상단에 추가한다.

- [ ] **Step 4: 이벤트 매퍼 테스트 작성**

`backend/scripts/roadmap_progress_event_test.py`:

```python
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
```

- [ ] **Step 5: 엔드포인트 테스트 작성**

`backend/scripts/roadmap_generate_endpoint_test.py` (라우트 등록·인증 가드 — 코치 `coach_endpoint_test.py` 패턴을 열어 동일 방식으로):

```python
# generate 엔드포인트 계약 테스트 — 라우트 등록·인증 가드(무LLM)
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


def main() -> int:
    from main import app

    paths = {getattr(r, "path", None): r for r in app.routes}
    check("POST /generate 등록", "/api/roadmap/generate" in paths)
    check("GET /generate/status 등록", "/api/roadmap/generate/status" in paths)
    check("GET /generate/stream 등록", "/api/roadmap/generate/stream" in paths)

    from fastapi.testclient import TestClient

    client = TestClient(app)
    check("무인증 generate 401", client.post("/api/roadmap/generate").status_code == 401)
    check("무인증 status 401", client.get("/api/roadmap/generate/status").status_code == 401)
    check("무인증 stream 401", client.get("/api/roadmap/generate/stream").status_code == 401)

    print(f"\nRESULT: PASS {_pass} / FAIL {_fail}")
    return 0 if _fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
```

주의: 무인증 응답 코드가 401이 아니라 403이면 기존 `coach_endpoint_test.py`가 기대하는 코드와 맞춘다(먼저 그 파일을 읽고 동일 기준 적용).

- [ ] **Step 6: 실행**

```bash
cd /c/project/roadmap/backend && python scripts/roadmap_progress_event_test.py && python scripts/roadmap_generate_endpoint_test.py
```

Expected: 두 스크립트 모두 FAIL 0.

- [ ] **Step 7: Commit**

```bash
cd /c/project/roadmap
git add backend/domain/hrowth_journey/spokes/infra/progress_events.py backend/domain/hrowth_journey/hub/services/roadmap_generation_service.py backend/api/v1/roadmap/roadmap_routor.py backend/scripts/roadmap_progress_event_test.py backend/scripts/roadmap_generate_endpoint_test.py
git commit -m "feat(roadmap-agent): 생성 런 서비스·SSE 3종 API — 백그라운드 실행·진행 중계·검증 병합 저장

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 6: 코치 launch tool + 프론트 진행 UI

**Files:**
- Create: `backend/domain/ai_coach/spokes/agents/tools/action_tools.py`
- Modify: `backend/domain/ai_coach/hub/services/coach_service.py` (`_build_tools` + 프롬프트 원칙 5)
- Modify: `backend/domain/ai_coach/spokes/infra/coach_graph.py` (`_ALL_TOOL_LABELS` 병합)
- Modify: `www.yeotaeho.kr/src/lib/api/roadmap.ts`, `www.yeotaeho.kr/src/hooks/useRoadmap.ts`, `www.yeotaeho.kr/src/components/features/roadmap/JourneyMapTab.tsx`
- Test: `backend/scripts/coach_tools_test.py` 확장(launch tool 검증 추가)

**Interfaces:**
- Consumes: Task 5 `RoadmapGenerationService.start_run`, SSE 이벤트 계약, `GET /generate/status` 응답 형태.
- Produces: 코치 tool `launch_roadmap_generation`(인자 없음 — user_id 클로저), 프론트 훅 `useRoadmapGeneration(loggedIn)`.

- [ ] **Step 1: action_tools 작성**

`backend/domain/ai_coach/spokes/agents/tools/action_tools.py`:

```python
# 코치 액션 tool — 로드맵 딥 에이전트 생성 발주(fire-and-forget, 유일한 비조회 tool)
from __future__ import annotations

from langchain_core.tools import tool

from core.database import AsyncSessionLocal

ACTION_TOOL_LABELS: dict[str, str] = {
    "launch_roadmap_generation": "로드맵 생성 발주",
}


def build_action_tools(user_id: str) -> list:
    """user_id 클로저 고정 — LLM 인자로 user_id 를 받지 않는다(권한 상승 차단)."""

    @tool
    async def launch_roadmap_generation() -> dict:
        """사용자가 로드맵 생성·개편을 원할 때 로드맵 딥 에이전트를 발주한다. 수 분 걸리는
        백그라운드 작업이므로, 발주 후 사용자에게 '로드맵 탭에서 진행 상황을 확인하라'고 안내한다.
        이미 진행 중이면 새로 발주하지 말고 그 사실을 알린다."""
        from domain.hrowth_journey.hub.services.roadmap_generation_service import (
            RoadmapGenerationService,
        )

        async with AsyncSessionLocal() as db:
            result = await RoadmapGenerationService(db).start_run(user_id, trigger="coach")
        if result.get("already_running"):
            return {"already_running": True, "message": "이미 로드맵 생성이 진행 중입니다."}
        return {"started": True, "message": "로드맵 생성을 시작했습니다. 로드맵 탭에서 진행 상황을 볼 수 있습니다."}

    return [launch_roadmap_generation]
```

- [ ] **Step 2: 코치 통합**

`coach_service.py`:
- import에 `from domain.ai_coach.spokes.agents.tools.action_tools import build_action_tools` 추가.
- `_build_tools`를 `return build_internal_tools(user_id) + build_web_tools() + build_action_tools(user_id)`로 변경.
- `_COACH_SYSTEM_PROMPT` 원칙 5를 다음으로 교체:

```
5. 역할 경계 — 성향을 새로 캐묻는 심층 조사는 상담실 몫이다. 코치는 파악된 성향을 활용해 방향·실행을 다룬다.
   사용자가 로드맵 생성·개편을 원하면 launch_roadmap_generation 으로 발주하고, 결과를 기다리지 말고
   "로드맵 탭에서 진행 상황을 확인하라"고 안내한다. 이미 진행 중이라는 응답이면 그 사실만 전한다.
```

`coach_graph.py`:
- import에 `from domain.ai_coach.spokes.agents.tools.action_tools import ACTION_TOOL_LABELS` 추가.
- `_ALL_TOOL_LABELS = {**TOOL_LABELS, **WEB_TOOL_LABELS}`를 `_ALL_TOOL_LABELS = {**TOOL_LABELS, **WEB_TOOL_LABELS, **ACTION_TOOL_LABELS}`로 변경.

- [ ] **Step 3: coach_tools_test 확장**

`backend/scripts/coach_tools_test.py`를 열어 기존 check 패턴 끝에 추가(기존 체크는 수정하지 않는다):

```python
    # R-1: launch_roadmap_generation tool 계약.
    from domain.ai_coach.spokes.agents.tools.action_tools import (
        ACTION_TOOL_LABELS,
        build_action_tools,
    )

    action = build_action_tools(user_id)
    check("action tool 1종", len(action) == 1 and action[0].name == "launch_roadmap_generation")
    check("action 라벨 등록", "launch_roadmap_generation" in ACTION_TOOL_LABELS)
    schema = action[0].args_schema.model_json_schema() if action[0].args_schema else {"properties": {}}
    check("launch user_id 인자 없음", "user_id" not in schema.get("properties", {}))
```

실행:

```bash
cd /c/project/roadmap/backend && python scripts/coach_tools_test.py
```

Expected: 기존 체크 + 신규 3개 전부 PASS.

- [ ] **Step 4: 프론트 API 클라이언트 추가**

`www.yeotaeho.kr/src/lib/api/roadmap.ts` 끝에 추가(기존 import 스타일 유지 — axios 클라이언트는 파일 상단의 기존 것, 스트림은 coach.ts처럼 raw fetch + `getStore`):

```ts
// ── 로드맵 딥 에이전트 생성 런 (R-1) ──
import { getStore } from '@/store';

const RAW_API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export interface GenerationRun {
  runId: string;
  status: 'pending' | 'running' | 'succeeded' | 'failed';
  stage?: string | null;
  percent?: number | null;
  label?: string | null;
  error?: string | null;
  result?: { source?: string; questCount?: number } | null;
}

export interface GenerationStreamHandlers {
  onProgress: (e: { stage?: string; percent?: number; label?: string }) => void;
  onDone: (result?: unknown) => void;
  onError: (message: string) => void;
  onNone?: () => void;
}

export async function startGeneration(): Promise<{ started: boolean; alreadyRunning: boolean }> {
  const token = getStore().getState().token;
  const res = await fetch(`${RAW_API_BASE}/api/roadmap/generate`, {
    method: 'POST',
    headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    credentials: 'include',
  });
  if (res.status === 409) return { started: false, alreadyRunning: true };
  if (!res.ok) throw new Error(`generate failed: ${res.status}`);
  return { started: true, alreadyRunning: false };
}

export async function fetchGenerationStatus(): Promise<GenerationRun | null> {
  const token = getStore().getState().token;
  const res = await fetch(`${RAW_API_BASE}/api/roadmap/generate/status`, {
    headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    credentials: 'include',
  });
  if (!res.ok) return null;
  const data = await res.json();
  return data?.run ?? null;
}

export async function streamGeneration(
  handlers: GenerationStreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const token = getStore().getState().token;
  const res = await fetch(`${RAW_API_BASE}/api/roadmap/generate/stream`, {
    headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    credentials: 'include',
    signal,
  });
  if (!res.ok || !res.body) throw new Error(`generation stream failed: ${res.status}`);
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const events = buffer.split('\n\n');
    buffer = events.pop() ?? '';
    for (const evt of events) {
      const dataLine = evt.split('\n').find((l) => l.startsWith('data:'));
      if (!dataLine) continue;
      try {
        const obj = JSON.parse(dataLine.slice(5).trim()) as {
          type?: string; stage?: string; percent?: number; label?: string;
          message?: string; result?: unknown;
        };
        if (obj.type === 'progress' || obj.type === 'status') handlers.onProgress(obj);
        if (obj.type === 'done') handlers.onDone(obj.result);
        if (obj.type === 'error') handlers.onError(obj.message ?? '로드맵 생성에 실패했어요.');
        if (obj.type === 'none') handlers.onNone?.();
      } catch {
        /* 파싱 불가 조각 무시 */
      }
    }
  }
}
```

주의: `roadmap.ts`에 이미 `getStore`/베이스 URL 상수가 있으면 중복 선언하지 말고 기존 것을 재사용한다(파일을 먼저 읽고 맞춘다).

- [ ] **Step 5: 생성 훅 추가**

`www.yeotaeho.kr/src/hooks/useRoadmap.ts` 끝에 추가:

```ts
import { useCallback, useEffect, useRef, useState } from 'react';

import {
  fetchGenerationStatus,
  GenerationRun,
  startGeneration,
  streamGeneration,
} from '@/lib/api/roadmap';

export interface GenerationView {
  running: boolean;
  stage?: string | null;
  percent?: number | null;
  label?: string | null;
  error?: string | null;
}

/** 생성 런 상태 — 탭 진입 시 status 1회 조회, running 이면 SSE 구독으로 승격. */
export function useRoadmapGeneration(loggedIn: boolean) {
  const qc = useQueryClient();
  const [view, setView] = useState<GenerationView>({ running: false });
  const abortRef = useRef<AbortController | null>(null);

  const finish = useCallback(
    (error?: string) => {
      abortRef.current?.abort();
      abortRef.current = null;
      setView({ running: false, error: error ?? null });
      if (!error) {
        qc.invalidateQueries({ queryKey: ['roadmap-journey'] });
        qc.invalidateQueries({ queryKey: ['planner-board'] });
      }
    },
    [qc],
  );

  const subscribe = useCallback(() => {
    if (abortRef.current) return;
    const ac = new AbortController();
    abortRef.current = ac;
    streamGeneration(
      {
        onProgress: (e) =>
          setView({ running: true, stage: e.stage, percent: e.percent, label: e.label }),
        onDone: () => finish(),
        onError: (m) => finish(m),
        onNone: () => finish(),
      },
      ac.signal,
    ).catch(() => {
      // 스트림 자체 실패 — 폴링 폴백 없이 조용히 종료(status 재조회로 복구 가능).
      if (abortRef.current === ac) finish();
    });
  }, [finish]);

  useEffect(() => {
    if (!loggedIn) return;
    let cancelled = false;
    fetchGenerationStatus().then((run: GenerationRun | null) => {
      if (cancelled || !run) return;
      if (run.status === 'running' || run.status === 'pending') {
        setView({ running: true, stage: run.stage, percent: run.percent, label: run.label });
        subscribe();
      }
    });
    return () => {
      cancelled = true;
      abortRef.current?.abort();
      abortRef.current = null;
    };
  }, [loggedIn, subscribe]);

  const start = useCallback(async () => {
    setView({ running: true, percent: 5, label: '생성 준비' });
    try {
      await startGeneration(); // 409 는 alreadyRunning — 그대로 구독.
      subscribe();
    } catch {
      finish('로드맵 생성을 시작하지 못했어요.');
    }
  }, [subscribe, finish]);

  return { view, start };
}
```

주의: `planner-board` 쿼리 키는 `usePlanner.ts`를 열어 실제 키 문자열과 일치시킨다(다르면 그쪽 키 사용).

- [ ] **Step 6: JourneyMapTab 교체**

`JourneyMapTab.tsx`:
- `useRefreshRoadmap` 대신 `useRoadmapGeneration` 사용: `const { view: gen, start: startGen } = useRoadmapGeneration(loggedIn);`
- 버튼(59-69행)을 다음으로 교체:

```tsx
            {loggedIn ? (
              <button
                type="button"
                onClick={() => startGen()}
                disabled={gen.running}
                className="inline-flex items-center gap-1.5 rounded-xl bg-indigo-600 px-3 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-indigo-700 disabled:opacity-60"
              >
                <Sparkles className="h-4 w-4" />
                {gen.running ? "생성 중…" : isLive ? "로드맵 다시 생성" : "내 로드맵 생성"}
              </button>
            ) : null}
```

- 역량 3축 칩 위(버튼 행 바로 아래)에 진행 스트립 추가:

```tsx
        {gen.running ? (
          <div className="mt-3 rounded-xl border border-indigo-100 bg-indigo-50/60 p-3 dark:border-indigo-900/40 dark:bg-indigo-900/15">
            <div className="flex items-center justify-between text-xs font-semibold text-indigo-800 dark:text-indigo-300">
              <span>{gen.label ?? "로드맵 생성 중"}</span>
              <span>{gen.percent ?? 0}%</span>
            </div>
            <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-indigo-100 dark:bg-indigo-900/40">
              <div
                className="h-full rounded-full bg-indigo-600 transition-all duration-700"
                style={{ width: `${gen.percent ?? 0}%` }}
              />
            </div>
          </div>
        ) : null}
        {gen.error ? (
          <p className="mt-2 text-xs text-rose-600 dark:text-rose-400">{gen.error}</p>
        ) : null}
```

- `useRefreshRoadmap` import 제거(훅 자체는 다른 소비자가 없으면 유지 — refine 경로는 deprecated 존치).

- [ ] **Step 7: 프론트 타입 검증**

```bash
cd /c/project/roadmap/www.yeotaeho.kr && pnpm exec tsc --noEmit
```

Expected: 신규 코드 관련 에러 0(기존 에러가 있으면 신규 파일 관련만 확인). `tsc` 스크립트가 없으면 `pnpm build`로 대체.

- [ ] **Step 8: Commit**

```bash
cd /c/project/roadmap
git add backend/domain/ai_coach/spokes/agents/tools/action_tools.py backend/domain/ai_coach/hub/services/coach_service.py backend/domain/ai_coach/spokes/infra/coach_graph.py backend/scripts/coach_tools_test.py www.yeotaeho.kr/src/lib/api/roadmap.ts www.yeotaeho.kr/src/hooks/useRoadmap.ts www.yeotaeho.kr/src/components/features/roadmap/JourneyMapTab.tsx
git commit -m "feat(roadmap-agent): 코치 발주 tool + 로드맵 탭 진행 UI — fire-and-forget·SSE 진행 스트립

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 7: 라이브 verify + 문서 현행화

**Files:**
- Create: `backend/scripts/roadmap_agent_live_verify.py`
- Modify: `docs/superpowers/specs/2026-07-05-ai-coach-roadmap-agent-design.md` (§6 현행화 — 사용자 경로 승인 완료)
- Modify: `backend/domain/hrowth_journey/docs/audit_trail.md` (최신 항목 맨 위 — 사용자 경로 승인 완료)

**Interfaces:**
- Consumes: Task 5 서비스 전체. 실 LLM·실 DB — **스크립트 실행은 최대 2회**(1회 = 딥 에이전트 완주 1번).

- [ ] **Step 1: 라이브 verify 작성**

`backend/scripts/roadmap_agent_live_verify.py`:

```python
# 로드맵 딥 에이전트 라이브 verify — 실 DB·실 LLM 로 run 1회 완주(SSE·병합·시드 확인)
from __future__ import annotations

import argparse
import asyncio
import json
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


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--user-id", required=True)
    args = parser.parse_args()
    user_id = args.user_id

    from sqlalchemy import text

    from core.database import AsyncSessionLocal
    from domain.hrowth_journey.hub.services.roadmap_generation_service import (
        RoadmapGenerationService,
    )

    async with AsyncSessionLocal() as db:
        pre_quests = (
            await db.execute(
                text(
                    "SELECT q.quest_key, q.state FROM roadmap_quests q "
                    "JOIN user_roadmaps r ON r.id = q.roadmap_id "
                    "WHERE r.user_id = CAST(:u AS UUID)"
                ),
                {"u": user_id},
            )
        ).all()
        pre_done = {r.quest_key for r in pre_quests if r.state == "done"}
        pre_task_count = (
            await db.execute(
                text("SELECT COUNT(*) FROM planner_tasks WHERE user_id = CAST(:u AS UUID)"),
                {"u": user_id},
            )
        ).scalar_one()
    print(f"사전 상태: 퀘스트 {len(pre_quests)}개(done {len(pre_done)}), 태스크 {pre_task_count}개")

    async with AsyncSessionLocal() as db:
        svc = RoadmapGenerationService(db)
        started = await svc.start_run(user_id, trigger="tab")
    check("발주 성공", started.get("started") is True)

    # SSE 구독으로 완주 관찰(별도 서비스 인스턴스 — 요청과 동일 형태).
    events: list[dict] = []
    async with AsyncSessionLocal() as db:
        svc2 = RoadmapGenerationService(db)
        async for sse in svc2.stream_events(user_id):
            obj = json.loads(sse.removeprefix("data: ").strip())
            events.append(obj)
            print("event:", obj.get("type"), obj.get("stage") or "", obj.get("percent") or "")
            if obj.get("type") in ("done", "error"):
                break

    types = [e["type"] for e in events]
    check("progress 이벤트 수신", "progress" in types or "status" in types)
    check("done 종결", types[-1] == "done")
    result = events[-1].get("result") or {}
    print("result:", result)
    check("결과 소스 기록", result.get("source") in ("deep_agent", "template"))

    async with AsyncSessionLocal() as db:
        post_quests = (
            await db.execute(
                text(
                    "SELECT q.quest_key, q.state FROM roadmap_quests q "
                    "JOIN user_roadmaps r ON r.id = q.roadmap_id "
                    "WHERE r.user_id = CAST(:u AS UUID)"
                ),
                {"u": user_id},
            )
        ).all()
        post_by_key = {r.quest_key: r.state for r in post_quests}
        post_task_count = (
            await db.execute(
                text("SELECT COUNT(*) FROM planner_tasks WHERE user_id = CAST(:u AS UUID)"),
                {"u": user_id},
            )
        ).scalar_one()
        run_row = (
            await db.execute(
                text(
                    "SELECT status, result FROM roadmap_generation_runs "
                    "WHERE user_id = CAST(:u AS UUID) ORDER BY id DESC LIMIT 1"
                ),
                {"u": user_id},
            )
        ).first()

    check("퀘스트 저장", len(post_quests) >= 4)
    check("run succeeded", run_row is not None and run_row.status == "succeeded")
    if pre_done:
        preserved = all(post_by_key.get(k) == "done" for k in pre_done if k in post_by_key)
        survived = sum(1 for k in pre_done if k in post_by_key)
        check("기존 done 보존(생존 key)", preserved)
        print(f"done 생존: {survived}/{len(pre_done)}")
    if result.get("source") == "deep_agent":
        print(f"태스크 시드: {pre_task_count} → {post_task_count} (+{result.get('tasks_seeded')})")
        check("시드 수 정합", post_task_count - pre_task_count == result.get("tasks_seeded", 0))

    print(f"\nRESULT: PASS {_pass} / FAIL {_fail}")
    return 0 if _fail == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
```

- [ ] **Step 2: 컨테이너에서 실행 (1회차 — 재생성 검증)**

기존 로드맵이 있는 실사용자 대상(자기모델 보유 사용자 uuid는 `user_self_model`에서 조회).

```bash
docker exec roadmap-api-1 python - <<'EOF'
import asyncio, sys
sys.path.insert(0, "/app")
async def f():
    from sqlalchemy import text
    from core.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        r = (await db.execute(text("SELECT user_id FROM user_self_model LIMIT 1"))).first()
        print(r[0] if r else "없음")
asyncio.run(f())
EOF
MSYS_NO_PATHCONV=1 docker exec roadmap-api-1 python /app/scripts/roadmap_agent_live_verify.py --user-id <uuid>
```

Expected: `RESULT: PASS n / FAIL 0`, `done 종결`, 기존 done 보존. **총 실행은 2회 이내**(실패 디버깅으로 초과가 필요하면 멈추고 보고). 이벤트 형태(astream 튜플)가 코드 가정과 다르면 스크립트가 출력한 실제 이벤트를 근거로 `map_agent_event`/`stream_mode` 소비부를 수정하고 남은 1회로 재검증한다.

- [ ] **Step 3: 스펙 §6 현행화**

`docs/superpowers/specs/2026-07-05-ai-coach-roadmap-agent-design.md` §6을 구현 실체로 갱신(§8 R-1 행도 완료 기준 그대로 유지하되 현행 반영):
- 산출 = 퀘스트 트리 + WBS 백로그 시드(source='ai', 빈 퀘스트만). 진행 보존 병합(done/active·플래너 연결 생존, diff upsert).
- 실행 = `roadmap_generation_runs`(활성 유니크·stale lazy) + RunHub, `POST /generate`(202/409)·`GET /generate/status`·`GET /generate/stream`. `/refine`은 deprecated 경량 폴백.
- 체크포인터 미주입(재실행=새 run), response_format 미사용(파일 산출+3단 폴백) — 원설계와의 차이를 "변경 이력" 줄로 명시.

- [ ] **Step 4: 감사 기록**

`backend/domain/hrowth_journey/docs/audit_trail.md` 맨 위에 관례 형식(무엇/왜/어디/검증/후속)으로 R-1 항목 추가.

- [ ] **Step 5: Commit**

```bash
cd /c/project/roadmap
git add backend/scripts/roadmap_agent_live_verify.py docs/superpowers/specs/2026-07-05-ai-coach-roadmap-agent-design.md backend/domain/hrowth_journey/docs/audit_trail.md
git commit -m "test(roadmap-agent): 라이브 verify — 딥 에이전트 완주·done 보존·시드 정합 + 스펙 §6 현행화·감사 기록

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```
