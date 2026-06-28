# Roadmap 리포지토리 — user_roadmaps·roadmap_quests·growth_logs 조회·upsert

from __future__ import annotations

import json
from datetime import date

from sqlalchemy import text

from domain.auth.hub.repositories.base_repository import BaseRepository

_FETCH_ROADMAP = text(
    """
    SELECT id, title, summary, skill_pillars, bridge_keywords, status
    FROM user_roadmaps
    WHERE user_id = CAST(:user_id AS UUID)
    LIMIT 1
    """
)

_FETCH_QUESTS = text(
    """
    SELECT quest_key, parent_key, title, purpose, difficulty, keywords, state, sort_order
    FROM roadmap_quests
    WHERE roadmap_id = :roadmap_id
    ORDER BY sort_order, quest_key
    """
)

_FETCH_LOGS_MONTH = text(
    """
    SELECT log_date, note, completed_quest_keys
    FROM growth_logs
    WHERE user_id = CAST(:user_id AS UUID)
      AND log_date >= :start_date AND log_date < :end_date
    ORDER BY log_date
    """
)

_UPSERT_LOG = text(
    """
    INSERT INTO growth_logs (user_id, log_date, note, completed_quest_keys, created_at, updated_at)
    VALUES (CAST(:user_id AS UUID), :log_date, :note, CAST(:completed AS JSONB), now(), now())
    ON CONFLICT (user_id, log_date) DO UPDATE SET
        note = EXCLUDED.note,
        completed_quest_keys = EXCLUDED.completed_quest_keys,
        updated_at = now()
    """
)


class RoadmapRepository(BaseRepository):
    async def fetch_roadmap(self, user_id: str) -> dict | None:
        r = (await self.session.execute(_FETCH_ROADMAP, {"user_id": user_id})).first()
        if r is None:
            return None
        return {
            "id": r.id,
            "title": r.title,
            "summary": r.summary,
            "skill_pillars": r.skill_pillars or [],
            "bridge_keywords": r.bridge_keywords or [],
            "status": r.status,
        }

    async def fetch_quests(self, roadmap_id: int) -> list[dict]:
        rows = (await self.session.execute(_FETCH_QUESTS, {"roadmap_id": roadmap_id})).all()
        return [
            {
                "quest_key": r.quest_key,
                "parent_key": r.parent_key,
                "title": r.title,
                "purpose": r.purpose,
                "difficulty": r.difficulty,
                "keywords": r.keywords or [],
                "state": r.state,
                "sort_order": r.sort_order,
            }
            for r in rows
        ]

    async def fetch_logs_month(self, user_id: str, start: date, end: date) -> list[dict]:
        rows = (
            await self.session.execute(
                _FETCH_LOGS_MONTH, {"user_id": user_id, "start_date": start, "end_date": end}
            )
        ).all()
        return [
            {
                "log_date": r.log_date.isoformat(),
                "note": r.note or "",
                "completed_quest_keys": r.completed_quest_keys or [],
            }
            for r in rows
        ]

    async def upsert_log(
        self, user_id: str, log_date: date, note: str, completed: list[str]
    ) -> None:
        await self.session.execute(
            _UPSERT_LOG,
            {
                "user_id": user_id,
                "log_date": log_date,
                "note": note,
                "completed": json.dumps(completed or []),
            },
        )
        await self.session.commit()
