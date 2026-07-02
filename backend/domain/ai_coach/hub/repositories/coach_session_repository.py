# 코치 세션 리포지토리 — 세션·메시지 CRUD·롤링 요약·종료

from __future__ import annotations

import uuid

from sqlalchemy import text

from domain.auth.hub.repositories.base_repository import BaseRepository

_CREATE = text(
    "INSERT INTO coach_sessions (id, user_id, status, started_at, created_at) "
    "VALUES (CAST(:id AS UUID), CAST(:uid AS UUID), 'active', now(), now())"
)
_GET = text(
    "SELECT user_id, status, context_summary, summarized_until, extracted_until FROM coach_sessions "
    "WHERE id = CAST(:id AS UUID)"
)
_ADD_MSG = text(
    "INSERT INTO coach_messages (session_id, role, content, created_at) "
    "VALUES (CAST(:sid AS UUID), :role, :content, now())"
)
_FETCH_MSGS = text(
    "SELECT role, content FROM coach_messages WHERE session_id = CAST(:sid AS UUID) "
    "ORDER BY created_at ASC, id ASC"
)
_COUNT = text("SELECT count(*) AS c FROM coach_messages WHERE session_id = CAST(:sid AS UUID)")
_END = text(
    "UPDATE coach_sessions SET status='ended', ended_at = COALESCE(ended_at, now()) "
    "WHERE id = CAST(:id AS UUID)"
)
_UPDATE_SUMMARY = text(
    "UPDATE coach_sessions SET context_summary = :s, summarized_until = :su WHERE id = CAST(:id AS UUID)"
)
_LATEST_ACTIVE = text(
    "SELECT id FROM coach_sessions WHERE user_id = CAST(:uid AS UUID) AND status = 'active' "
    "ORDER BY created_at DESC LIMIT 1"
)
_UPDATE_EXTRACTED = text(
    "UPDATE coach_sessions SET extracted_until = :eu, extracted_at = now() WHERE id = CAST(:id AS UUID)"
)
_FETCH_EXTRACTABLE = text(
    """
    SELECT s.id, s.user_id
    FROM coach_sessions s
    WHERE (SELECT count(*) FROM coach_messages m WHERE m.session_id = s.id)
          >= s.extracted_until + :min_new
    ORDER BY s.started_at ASC
    LIMIT :limit
    """
)


class CoachSessionRepository(BaseRepository):
    async def create_session(self, user_id: str) -> str:
        sid = str(uuid.uuid4())
        await self.session.execute(_CREATE, {"id": sid, "uid": user_id})
        await self.session.commit()
        return sid

    async def get_session(self, session_id: str) -> dict | None:
        r = (await self.session.execute(_GET, {"id": session_id})).first()
        if r is None:
            return None
        return {
            "user_id": str(r.user_id),
            "status": r.status,
            "context_summary": r.context_summary,
            "summarized_until": r.summarized_until,
            "extracted_until": r.extracted_until,
        }

    async def add_message(self, session_id: str, role: str, content: str) -> None:
        await self.session.execute(_ADD_MSG, {"sid": session_id, "role": role, "content": content})
        await self.session.commit()

    async def fetch_messages(self, session_id: str) -> list[dict]:
        rows = (await self.session.execute(_FETCH_MSGS, {"sid": session_id})).all()
        return [{"role": r.role, "content": r.content} for r in rows]

    async def count_messages(self, session_id: str) -> int:
        return int((await self.session.execute(_COUNT, {"sid": session_id})).first().c)

    async def end_session(self, session_id: str) -> None:
        await self.session.execute(_END, {"id": session_id})
        await self.session.commit()

    async def update_summary(self, session_id: str, summary: str, summarized_until: int) -> None:
        await self.session.execute(_UPDATE_SUMMARY, {"id": session_id, "s": summary, "su": summarized_until})
        await self.session.commit()

    async def get_latest_active_session(self, user_id: str) -> str | None:
        r = (await self.session.execute(_LATEST_ACTIVE, {"uid": user_id})).first()
        return str(r.id) if r else None

    async def update_extracted(self, session_id: str, extracted_until: int) -> None:
        await self.session.execute(
            _UPDATE_EXTRACTED, {"id": session_id, "eu": extracted_until}
        )
        await self.session.commit()

    async def fetch_extractable_sessions(self, min_new: int, limit: int) -> list[dict]:
        rows = (
            await self.session.execute(
                _FETCH_EXTRACTABLE, {"min_new": min_new, "limit": limit}
            )
        ).all()
        return [{"id": str(r.id), "user_id": str(r.user_id)} for r in rows]
