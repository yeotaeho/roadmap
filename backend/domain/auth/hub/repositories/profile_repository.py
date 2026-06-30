# 기본정보 리포지토리 — user_profiles 조회·upsert(데모그래픽, 선택 입력)

from __future__ import annotations

from sqlalchemy import text

from domain.auth.hub.repositories.base_repository import BaseRepository

_FETCH = text(
    """
    SELECT birth_year, gender, region, current_status, education_level, source
    FROM user_profiles
    WHERE user_id = CAST(:uid AS UUID)
    """
)

_UPSERT = text(
    """
    INSERT INTO user_profiles
        (user_id, birth_year, gender, region, current_status, education_level, source, updated_at)
    VALUES (CAST(:uid AS UUID), :birth_year, :gender, :region, :current_status, :education_level, :source, now())
    ON CONFLICT (user_id) DO UPDATE SET
        birth_year = EXCLUDED.birth_year,
        gender = EXCLUDED.gender,
        region = EXCLUDED.region,
        current_status = EXCLUDED.current_status,
        education_level = EXCLUDED.education_level,
        source = EXCLUDED.source,
        updated_at = now()
    """
)


class ProfileRepository(BaseRepository):
    async def fetch_profile(self, user_id: str) -> dict | None:
        r = (await self.session.execute(_FETCH, {"uid": user_id})).first()
        if r is None:
            return None
        return {
            "birth_year": r.birth_year,
            "gender": r.gender,
            "region": r.region,
            "current_status": r.current_status,
            "education_level": r.education_level,
            "source": r.source,
        }

    async def upsert_profile(
        self,
        user_id: str,
        birth_year: int | None,
        gender: str | None,
        region: str | None,
        current_status: str | None,
        education_level: str | None,
        source: str,
    ) -> None:
        await self.session.execute(
            _UPSERT,
            {
                "uid": user_id,
                "birth_year": birth_year,
                "gender": gender,
                "region": region,
                "current_status": current_status,
                "education_level": education_level,
                "source": source,
            },
        )
        await self.session.commit()
