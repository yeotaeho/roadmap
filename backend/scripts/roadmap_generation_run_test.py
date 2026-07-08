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
