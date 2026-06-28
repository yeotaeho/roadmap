# 페르소나 리포지토리 — user_personas 조회·upsert(스킬·경험·학력)

from __future__ import annotations

import json

from sqlalchemy import text

from domain.auth.hub.repositories.base_repository import BaseRepository

_FETCH = text(
    """
    SELECT education, experiences, skills, summary, source
    FROM user_personas
    WHERE user_id = CAST(:uid AS UUID)
    """
)

_UPSERT = text(
    """
    INSERT INTO user_personas (user_id, education, experiences, skills, summary, source, updated_at)
    VALUES (CAST(:uid AS UUID), CAST(:edu AS JSONB), CAST(:exp AS JSONB),
            CAST(:skl AS JSONB), :summary, :source, now())
    ON CONFLICT (user_id) DO UPDATE SET
        education = EXCLUDED.education,
        experiences = EXCLUDED.experiences,
        skills = EXCLUDED.skills,
        summary = EXCLUDED.summary,
        source = EXCLUDED.source,
        updated_at = now()
    """
)


class PersonaRepository(BaseRepository):
    async def fetch_persona(self, user_id: str) -> dict | None:
        r = (await self.session.execute(_FETCH, {"uid": user_id})).first()
        if r is None:
            return None
        return {
            "education": r.education or [],
            "experiences": r.experiences or [],
            "skills": r.skills or [],
            "summary": r.summary or "",
            "source": r.source,
        }

    async def upsert_persona(
        self,
        user_id: str,
        education: list,
        experiences: list,
        skills: list,
        summary: str,
        source: str,
    ) -> None:
        await self.session.execute(
            _UPSERT,
            {
                "uid": user_id,
                "edu": json.dumps(education or []),
                "exp": json.dumps(experiences or []),
                "skl": json.dumps(skills or []),
                "summary": summary or "",
                "source": source,
            },
        )
        await self.session.commit()
