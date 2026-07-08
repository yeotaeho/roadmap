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
