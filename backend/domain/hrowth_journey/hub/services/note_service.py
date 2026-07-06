# 노트 서비스 — 마크다운 노트 CRUD·[[링크]] 파싱·백링크

from __future__ import annotations

import re
from datetime import datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from domain.hrowth_journey.hub.repositories.note_repository import NoteRepository

_LINK_RE = re.compile(r"\[\[([^\[\]]+?)\]\]")


def parse_note_links(content: str) -> list[str]:
    """본문에서 [[제목]] 링크를 추출한다. 트림·중복 제거(순서 보존)·빈/120자 초과 제외."""
    if not content:
        return []
    seen: set[str] = set()
    out: list[str] = []
    for m in _LINK_RE.finditer(content):
        title = m.group(1).strip()
        if not title or len(title) > 120 or title in seen:
            continue
        seen.add(title)
        out.append(title)
    return out


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def _serialize_list_item(row: dict) -> dict:
    return {
        "id": row["id"],
        "title": row["title"],
        "updatedAt": _iso(row["updated_at"]),
        "preview": (row["preview"] or "").replace("\n", " ").strip(),
    }


def _serialize_detail(row: dict, backlinks: list[dict]) -> dict:
    return {
        "id": row["id"],
        "title": row["title"],
        "content": row["content"],
        "linkedTitles": row["linked_titles"] or [],
        "taskId": row["task_id"],
        "questKey": row["quest_key"],
        "updatedAt": _iso(row["updated_at"]),
        "backlinks": [{"id": b["id"], "title": b["title"]} for b in backlinks],
    }


class NoteService:
    def __init__(self, db: AsyncSession):
        self.repo = NoteRepository(db)

    async def list_notes(self, user_id: str) -> list[dict]:
        return [_serialize_list_item(r) for r in await self.repo.list_notes(user_id)]

    async def get_note(self, user_id: str, note_id: int) -> dict | None:
        row = await self.repo.fetch_note(user_id, note_id)
        if row is None:
            return None
        backlinks = await self.repo.fetch_backlinks(user_id, row["title"], note_id)
        return _serialize_detail(row, backlinks)

    async def create_note(
        self, user_id: str, title: str, content: str = "",
        task_id: int | None = None, quest_key: str | None = None,
    ) -> dict:
        try:
            row = await self.repo.insert_note(
                user_id, title.strip(), content, parse_note_links(content), task_id, quest_key
            )
        except IntegrityError:
            await self.repo.session.rollback()
            raise ValueError("duplicate-title")
        return _serialize_detail(row, [])

    async def update_note(self, user_id: str, note_id: int, fields: dict) -> dict | None:
        current = await self.repo.fetch_note(user_id, note_id)
        if current is None:
            return None
        title = (fields.get("title") or current["title"]).strip()
        content = fields.get("content") if fields.get("content") is not None else current["content"]
        task_id = fields.get("task_id") if "task_id" in fields else current["task_id"]
        quest_key = fields.get("quest_key") if "quest_key" in fields else current["quest_key"]
        try:
            row = await self.repo.update_note(
                user_id, note_id, title, content, parse_note_links(content), task_id, quest_key
            )
        except IntegrityError:
            await self.repo.session.rollback()
            raise ValueError("duplicate-title")
        if row is None:
            return None
        backlinks = await self.repo.fetch_backlinks(user_id, row["title"], note_id)
        return _serialize_detail(row, backlinks)

    async def delete_note(self, user_id: str, note_id: int) -> bool:
        return await self.repo.delete_note(user_id, note_id)
