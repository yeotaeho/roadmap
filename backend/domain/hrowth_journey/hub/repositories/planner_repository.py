# 플래너 리포지토리 — planner_sprints·planner_tasks 조회·CRUD·재정렬

from __future__ import annotations

from datetime import date

from sqlalchemy import text

from domain.auth.hub.repositories.base_repository import BaseRepository

_FETCH_SPRINTS = text(
    """
    SELECT id, title, goal, start_date, end_date, state, position
    FROM planner_sprints
    WHERE user_id = CAST(:user_id AS UUID)
    ORDER BY position, start_date, id
    """
)

_FETCH_TASKS = text(
    """
    SELECT id, sprint_id, quest_key, title, description, status,
           start_date, due_date, estimated_days, position, source
    FROM planner_tasks
    WHERE user_id = CAST(:user_id AS UUID)
    ORDER BY position, id
    """
)

_INSERT_SPRINT = text(
    """
    INSERT INTO planner_sprints (user_id, title, goal, start_date, end_date, state, position)
    VALUES (CAST(:user_id AS UUID), :title, :goal, :start_date, :end_date, :state,
            COALESCE((SELECT MAX(position) + 1 FROM planner_sprints
                      WHERE user_id = CAST(:user_id AS UUID)), 0))
    RETURNING id, title, goal, start_date, end_date, state, position
    """
)

_DELETE_SPRINT = text(
    """
    DELETE FROM planner_sprints
    WHERE id = :sprint_id AND user_id = CAST(:user_id AS UUID)
    """
)

_INSERT_TASK = text(
    """
    INSERT INTO planner_tasks
        (user_id, sprint_id, quest_key, title, description, status,
         start_date, due_date, estimated_days, position, source)
    VALUES (CAST(:user_id AS UUID), :sprint_id, :quest_key, :title, :description, :status,
            :start_date, :due_date, :estimated_days,
            COALESCE((SELECT MAX(position) + 1 FROM planner_tasks
                      WHERE user_id = CAST(:user_id AS UUID)
                        AND sprint_id IS NOT DISTINCT FROM :sprint_id), 0),
            :source)
    RETURNING id, sprint_id, quest_key, title, description, status,
              start_date, due_date, estimated_days, position, source
    """
)

_DELETE_TASK = text(
    """
    DELETE FROM planner_tasks
    WHERE id = :task_id AND user_id = CAST(:user_id AS UUID)
    """
)

_REORDER_TASK = text(
    """
    UPDATE planner_tasks
    SET sprint_id = :sprint_id, position = :position, updated_at = now()
    WHERE id = :task_id AND user_id = CAST(:user_id AS UUID)
    """
)

_OWNS_SPRINT = text(
    """
    SELECT 1 FROM planner_sprints
    WHERE id = :sprint_id AND user_id = CAST(:user_id AS UUID)
    """
)

# 퀘스트 조회 — 사용자 활성 로드맵에서 quest_key 매칭(분해 컨텍스트용)
_FETCH_QUEST = text(
    """
    SELECT q.quest_key, q.title, q.purpose, q.difficulty, q.keywords
    FROM roadmap_quests q
    JOIN user_roadmaps r ON r.id = q.roadmap_id
    WHERE r.user_id = CAST(:user_id AS UUID) AND q.quest_key = :quest_key
    """
)

# 사용자 Sync 프로필 조회 — RoadmapRepository._FETCH_SYNC_PROFILE 과 동일 SQL(분해 컨텍스트용)
_FETCH_SYNC_PROFILE = text(
    """
    SELECT target_job, interest_keywords
    FROM user_sync_profiles WHERE user_id = CAST(:user_id AS UUID)
    """
)

# 부분 수정 허용 컬럼 화이트리스트 — SQL 조립은 이 키에 한정
_SPRINT_FIELDS = {"title", "goal", "start_date", "end_date", "state", "position"}
_TASK_FIELDS = {
    "sprint_id", "quest_key", "title", "description", "status",
    "start_date", "due_date", "estimated_days", "position",
}


class PlannerRepository(BaseRepository):
    async def fetch_sprints(self, user_id: str) -> list[dict]:
        rows = (await self.session.execute(_FETCH_SPRINTS, {"user_id": user_id})).mappings().all()
        return [dict(r) for r in rows]

    async def fetch_tasks(self, user_id: str) -> list[dict]:
        rows = (await self.session.execute(_FETCH_TASKS, {"user_id": user_id})).mappings().all()
        return [dict(r) for r in rows]

    async def insert_sprint(
        self, user_id: str, title: str, goal: str | None,
        start_date: date, end_date: date, state: str,
    ) -> dict:
        row = (
            await self.session.execute(
                _INSERT_SPRINT,
                {"user_id": user_id, "title": title, "goal": goal,
                 "start_date": start_date, "end_date": end_date, "state": state},
            )
        ).mappings().one()
        await self.session.commit()
        return dict(row)

    async def update_sprint(self, user_id: str, sprint_id: int, fields: dict) -> bool:
        return await self._update("planner_sprints", _SPRINT_FIELDS, user_id, sprint_id, fields)

    async def delete_sprint(self, user_id: str, sprint_id: int) -> bool:
        res = await self.session.execute(
            _DELETE_SPRINT, {"user_id": user_id, "sprint_id": sprint_id}
        )
        await self.session.commit()
        return res.rowcount > 0

    async def insert_task(self, user_id: str, fields: dict) -> dict:
        params = {
            "user_id": user_id,
            "sprint_id": fields.get("sprint_id"),
            "quest_key": fields.get("quest_key"),
            "title": fields["title"],
            "description": fields.get("description"),
            "status": fields.get("status") or "todo",
            "start_date": fields.get("start_date"),
            "due_date": fields.get("due_date"),
            "estimated_days": fields.get("estimated_days"),
            "source": fields.get("source") or "user",
        }
        row = (await self.session.execute(_INSERT_TASK, params)).mappings().one()
        await self.session.commit()
        return dict(row)

    async def update_task(self, user_id: str, task_id: int, fields: dict) -> bool:
        return await self._update("planner_tasks", _TASK_FIELDS, user_id, task_id, fields)

    async def delete_task(self, user_id: str, task_id: int) -> bool:
        res = await self.session.execute(_DELETE_TASK, {"user_id": user_id, "task_id": task_id})
        await self.session.commit()
        return res.rowcount > 0

    async def reorder_tasks(
        self, user_id: str, sprint_id: int | None, task_ids: list[int]
    ) -> int:
        """task_ids 순서대로 position 0..n 재부여 + 대상 컬럼(sprint_id)로 이동."""
        moved = 0
        for pos, tid in enumerate(task_ids):
            res = await self.session.execute(
                _REORDER_TASK,
                {"user_id": user_id, "sprint_id": sprint_id, "position": pos, "task_id": tid},
            )
            moved += res.rowcount
        await self.session.commit()
        return moved

    async def owns_sprint(self, user_id: str, sprint_id: int) -> bool:
        row = (
            await self.session.execute(
                _OWNS_SPRINT, {"user_id": user_id, "sprint_id": sprint_id}
            )
        ).first()
        return row is not None

    async def fetch_quest(self, user_id: str, quest_key: str) -> dict | None:
        row = (
            await self.session.execute(
                _FETCH_QUEST, {"user_id": user_id, "quest_key": quest_key}
            )
        ).mappings().first()
        return dict(row) if row else None

    async def fetch_sync_profile(self, user_id: str) -> dict:
        r = (await self.session.execute(_FETCH_SYNC_PROFILE, {"user_id": user_id})).first()
        if r is None:
            return {"target_job": None, "interest_keywords": []}
        return {"target_job": r.target_job, "interest_keywords": r.interest_keywords or []}

    async def _update(
        self, table: str, allowed: set[str], user_id: str, row_id: int, fields: dict
    ) -> bool:
        """화이트리스트 컬럼만 동적 SET. 값은 전부 바인드 파라미터."""
        sets = {k: v for k, v in fields.items() if k in allowed}
        if not sets:
            return False
        clause = ", ".join(f"{k} = :{k}" for k in sets)
        stmt = text(
            f"UPDATE {table} SET {clause}, updated_at = now() "
            "WHERE id = :row_id AND user_id = CAST(:user_id AS UUID)"
        )
        res = await self.session.execute(
            stmt, {**sets, "row_id": row_id, "user_id": user_id}
        )
        await self.session.commit()
        return res.rowcount > 0
