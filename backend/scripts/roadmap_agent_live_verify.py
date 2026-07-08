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
