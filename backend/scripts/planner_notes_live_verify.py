# 플래너·노트 라이브 검증 — 실 DB 보드/가드/폴백/백링크 확증

from __future__ import annotations

import sys

sys.stdout.reconfigure(encoding="utf-8"); sys.stderr.reconfigure(encoding="utf-8")

import os
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SCHEDULER_ENABLED", "false")

import asyncio

from sqlalchemy import text

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


async def main() -> int:
    from core.database import AsyncSessionLocal
    from domain.hrowth_journey.hub.services.note_service import NoteService
    from domain.hrowth_journey.hub.services.planner_service import PlannerService

    async with AsyncSessionLocal() as s:
        r = (await s.execute(text("SELECT id FROM users ORDER BY created_at LIMIT 1"))).first()
    if r is None:
        print("SKIP: users 테이블에 레코드 없음 — 전체 스킵")
        return 0
    user_id = str(r.id)

    sprint_id: int | None = None
    task_id: int | None = None
    decompose_task_ids: list[int] = []
    note_a_id: int | None = None
    note_b_id: int | None = None

    try:
        # ---- PlannerService ----
        async with AsyncSessionLocal() as db:
            planner = PlannerService(db)

            today = date.today()
            sprint = await planner.create_sprint(
                user_id, "[verify] 스프린트", None, today, today + timedelta(days=6)
            )
            sprint_id = sprint["id"]
            check(
                "create_sprint 반환·serialize 키",
                sprint.get("id") is not None
                and sprint.get("title") == "[verify] 스프린트"
                and sprint.get("startDate") == today.isoformat()
                and sprint.get("endDate") == (today + timedelta(days=6)).isoformat(),
                str(sprint),
            )

            task = await planner.create_task(user_id, {"title": "[verify] 태스크"})
            task_id = task["id"]
            check("create_task 백로그 sprintId null", task.get("sprintId") is None, str(task))

            moved = await planner.reorder_tasks(user_id, sprint_id, [task_id])
            check("reorder_tasks 이동 건수", moved == 1, str(moved))

            board = await planner.get_board(user_id)
            moved_task = next((t for t in board["tasks"] if t["id"] == task_id), None)
            check(
                "reorder 후 get_board sprintId 이동 확인",
                moved_task is not None and moved_task["sprintId"] == sprint_id,
                str(moved_task),
            )

            # 소유권 가드
            try:
                await planner.reorder_tasks(user_id, 999999999, [task_id])
                check("reorder_tasks 소유권 가드", False, "예외 미발생")
            except ValueError as e:
                check("reorder_tasks 소유권 가드", str(e) == "sprint-not-found", str(e))

            deleted = await planner.delete_sprint(user_id, sprint_id)
            check("delete_sprint 성공", deleted is True)
            sprint_id = None

            board2 = await planner.get_board(user_id)
            back_task = next((t for t in board2["tasks"] if t["id"] == task_id), None)
            check(
                "delete_sprint 후 태스크 백로그 복귀(FK SET NULL)",
                back_task is not None and back_task["sprintId"] is None,
                str(back_task),
            )

            deleted_task = await planner.delete_task(user_id, task_id)
            check("delete_task 성공", deleted_task is True)
            board3 = await planner.get_board(user_id)
            gone = next((t for t in board3["tasks"] if t["id"] == task_id), None)
            check("delete_task 후 보드에서 사라짐", gone is None)
            task_id = None

            # ---- decompose 폴백 경로 ----
            planner._api_key = None
            qrow = (
                await db.execute(
                    text(
                        "SELECT q.quest_key FROM roadmap_quests q "
                        "JOIN user_roadmaps r ON r.id = q.roadmap_id "
                        "WHERE r.user_id = CAST(:uid AS UUID) LIMIT 1"
                    ),
                    {"uid": user_id},
                )
            ).first()
            if qrow is not None:
                result = await planner.decompose(user_id, qrow.quest_key)
                decompose_task_ids = [t["id"] for t in result.get("tasks", [])]
                check(
                    "decompose 폴백 source=template",
                    result.get("source") == "template",
                    str(result.get("source")),
                )
                check(
                    "decompose 폴백 태스크 3개",
                    len(result.get("tasks", [])) == 3,
                    str(len(result.get("tasks", []))),
                )
                check(
                    "decompose 폴백 전체 source=ai",
                    all(t.get("source") == "ai" for t in result.get("tasks", [])),
                    str([t.get("source") for t in result.get("tasks", [])]),
                )
            else:
                result = await planner.decompose(user_id, "__no_such_quest_key__")
                check(
                    "decompose(없는키) source=none·tasks 빈배열",
                    result == {"source": "none", "tasks": []},
                    str(result),
                )

        # ---- NoteService ----
        async with AsyncSessionLocal() as db:
            notes = NoteService(db)

            note_a_title = "verify-note-A"
            note_b_title = "verify-note-B"
            note_a = await notes.create_note(user_id, note_a_title)
            note_a_id = note_a["id"]
            note_b = await notes.create_note(
                user_id, note_b_title, content=f"[[{note_a_title}]] 링크"
            )
            note_b_id = note_b["id"]
            check(
                "create_note B linkedTitles에 A 제목",
                note_a_title in note_b.get("linkedTitles", []),
                str(note_b.get("linkedTitles")),
            )

            a_detail = await notes.get_note(user_id, note_a_id)
            check(
                "get_note A backlinks에 B 포함",
                any(b["id"] == note_b_id for b in a_detail.get("backlinks", [])),
                str(a_detail.get("backlinks")),
            )

            try:
                await notes.create_note(user_id, note_a_title)
                check("create_note 중복 제목 가드", False, "예외 미발생")
            except ValueError as e:
                check("create_note 중복 제목 가드", str(e) == "duplicate-title", str(e))

            updated_b = await notes.update_note(user_id, note_b_id, {"content": "링크 없음"})
            check(
                "update_note B 링크 제거 후 linkedTitles 빈 배열",
                updated_b.get("linkedTitles") == [],
                str(updated_b.get("linkedTitles")),
            )

            a_detail2 = await notes.get_note(user_id, note_a_id)
            check(
                "링크 제거 후 A 백링크에서 B 사라짐",
                not any(b["id"] == note_b_id for b in a_detail2.get("backlinks", [])),
                str(a_detail2.get("backlinks")),
            )

            deleted_a = await notes.delete_note(user_id, note_a_id)
            deleted_b = await notes.delete_note(user_id, note_b_id)
            check("delete_note A·B 성공", deleted_a and deleted_b)
            note_a_id = None
            note_b_id = None

    finally:
        # 잔여물 정리
        async with AsyncSessionLocal() as db:
            if task_id is not None:
                await db.execute(
                    text("DELETE FROM planner_tasks WHERE id = :id"), {"id": task_id}
                )
            if decompose_task_ids:
                await db.execute(
                    text("DELETE FROM planner_tasks WHERE id = ANY(:ids)"),
                    {"ids": decompose_task_ids},
                )
            if sprint_id is not None:
                await db.execute(
                    text("DELETE FROM planner_sprints WHERE id = :id"), {"id": sprint_id}
                )
            if note_a_id is not None:
                await db.execute(
                    text("DELETE FROM roadmap_notes WHERE id = :id"), {"id": note_a_id}
                )
            if note_b_id is not None:
                await db.execute(
                    text("DELETE FROM roadmap_notes WHERE id = :id"), {"id": note_b_id}
                )
            await db.execute(
                text("DELETE FROM planner_tasks WHERE user_id = CAST(:uid AS UUID) AND title = '[verify] 태스크'"),
                {"uid": user_id},
            )
            await db.execute(
                text("DELETE FROM planner_sprints WHERE user_id = CAST(:uid AS UUID) AND title = '[verify] 스프린트'"),
                {"uid": user_id},
            )
            await db.execute(
                text("DELETE FROM roadmap_notes WHERE user_id = CAST(:uid AS UUID) AND title IN (:a, :b)"),
                {"uid": user_id, "a": note_a_title, "b": note_b_title},
            )
            await db.commit()

    print(f"\n합계: PASS {PASS} / FAIL {FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
