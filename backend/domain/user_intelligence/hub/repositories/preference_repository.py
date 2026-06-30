# 성향·선호 리포지토리 — user_preferences 조회·upsert(disposition)

from __future__ import annotations

import json

from sqlalchemy import text

from domain.auth.hub.repositories.base_repository import BaseRepository

_FETCH = text(
    """
    SELECT work_style, company_size_pref, work_type_pref, work_values, source
    FROM user_preferences
    WHERE user_id = CAST(:uid AS UUID)
    """
)

_UPSERT = text(
    """
    INSERT INTO user_preferences
        (user_id, work_style, company_size_pref, work_type_pref, work_values, source, updated_at)
    VALUES (CAST(:uid AS UUID), :work_style, :company_size_pref, :work_type_pref,
            CAST(:work_values AS JSONB), :source, now())
    ON CONFLICT (user_id) DO UPDATE SET
        work_style = EXCLUDED.work_style,
        company_size_pref = EXCLUDED.company_size_pref,
        work_type_pref = EXCLUDED.work_type_pref,
        work_values = EXCLUDED.work_values,
        source = EXCLUDED.source,
        updated_at = now()
    """
)


class PreferenceRepository(BaseRepository):
    async def fetch_preferences(self, user_id: str) -> dict | None:
        r = (await self.session.execute(_FETCH, {"uid": user_id})).first()
        if r is None:
            return None
        return {
            "work_style": r.work_style,
            "company_size_pref": r.company_size_pref,
            "work_type_pref": r.work_type_pref,
            "work_values": r.work_values or [],
            "source": r.source,
        }

    async def upsert_preferences(
        self,
        user_id: str,
        work_style: str | None,
        company_size_pref: str | None,
        work_type_pref: str | None,
        work_values: list,
        source: str,
    ) -> None:
        await self.session.execute(
            _UPSERT,
            {
                "uid": user_id,
                "work_style": work_style,
                "company_size_pref": company_size_pref,
                "work_type_pref": work_type_pref,
                "work_values": json.dumps(work_values or []),
                "source": source,
            },
        )
        await self.session.commit()
