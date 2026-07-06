# 노트 리포지토리 — roadmap_notes CRUD·백링크 조회

from __future__ import annotations

import json

from sqlalchemy import text

from domain.auth.hub.repositories.base_repository import BaseRepository

_LIST_NOTES = text(
    """
    SELECT id, title, updated_at, LEFT(content, 80) AS preview
    FROM roadmap_notes
    WHERE user_id = CAST(:user_id AS UUID)
    ORDER BY updated_at DESC, id DESC
    """
)

_FETCH_NOTE = text(
    """
    SELECT id, title, content, linked_titles, task_id, quest_key, updated_at
    FROM roadmap_notes
    WHERE id = :note_id AND user_id = CAST(:user_id AS UUID)
    """
)

# 백링크 — linked_titles JSONB 배열이 :title_json(단일 원소 배열)을 포함하는 노트
_FETCH_BACKLINKS = text(
    """
    SELECT id, title
    FROM roadmap_notes
    WHERE user_id = CAST(:user_id AS UUID)
      AND linked_titles @> CAST(:title_json AS JSONB)
      AND id != :note_id
    ORDER BY updated_at DESC
    """
)

_INSERT_NOTE = text(
    """
    INSERT INTO roadmap_notes (user_id, title, content, linked_titles, task_id, quest_key)
    VALUES (CAST(:user_id AS UUID), :title, :content, CAST(:linked AS JSONB), :task_id, :quest_key)
    RETURNING id, title, content, linked_titles, task_id, quest_key, updated_at
    """
)

_UPDATE_NOTE = text(
    """
    UPDATE roadmap_notes
    SET title = :title, content = :content, linked_titles = CAST(:linked AS JSONB),
        task_id = :task_id, quest_key = :quest_key, updated_at = now()
    WHERE id = :note_id AND user_id = CAST(:user_id AS UUID)
    RETURNING id, title, content, linked_titles, task_id, quest_key, updated_at
    """
)

_DELETE_NOTE = text(
    "DELETE FROM roadmap_notes WHERE id = :note_id AND user_id = CAST(:user_id AS UUID)"
)

_OWNS_TASK = text(
    """
    SELECT 1 FROM planner_tasks
    WHERE id = :task_id AND user_id = CAST(:user_id AS UUID)
    """
)


class NoteRepository(BaseRepository):
    async def list_notes(self, user_id: str) -> list[dict]:
        rows = (await self.session.execute(_LIST_NOTES, {"user_id": user_id})).mappings().all()
        return [dict(r) for r in rows]

    async def fetch_note(self, user_id: str, note_id: int) -> dict | None:
        row = (
            await self.session.execute(_FETCH_NOTE, {"user_id": user_id, "note_id": note_id})
        ).mappings().first()
        return dict(row) if row else None

    async def fetch_backlinks(self, user_id: str, title: str, note_id: int) -> list[dict]:
        rows = (
            await self.session.execute(
                _FETCH_BACKLINKS,
                {"user_id": user_id, "title_json": json.dumps([title]), "note_id": note_id},
            )
        ).mappings().all()
        return [dict(r) for r in rows]

    async def insert_note(
        self, user_id: str, title: str, content: str, linked: list[str],
        task_id: int | None, quest_key: str | None,
    ) -> dict:
        row = (
            await self.session.execute(
                _INSERT_NOTE,
                {"user_id": user_id, "title": title, "content": content,
                 "linked": json.dumps(linked), "task_id": task_id, "quest_key": quest_key},
            )
        ).mappings().one()
        await self.session.commit()
        return dict(row)

    async def update_note(
        self, user_id: str, note_id: int, title: str, content: str, linked: list[str],
        task_id: int | None, quest_key: str | None,
    ) -> dict | None:
        row = (
            await self.session.execute(
                _UPDATE_NOTE,
                {"user_id": user_id, "note_id": note_id, "title": title, "content": content,
                 "linked": json.dumps(linked), "task_id": task_id, "quest_key": quest_key},
            )
        ).mappings().first()
        await self.session.commit()
        return dict(row) if row else None

    async def delete_note(self, user_id: str, note_id: int) -> bool:
        res = await self.session.execute(_DELETE_NOTE, {"user_id": user_id, "note_id": note_id})
        await self.session.commit()
        return res.rowcount > 0

    async def owns_task(self, user_id: str, task_id: int) -> bool:
        row = (
            await self.session.execute(_OWNS_TASK, {"user_id": user_id, "task_id": task_id})
        ).first()
        return row is not None
