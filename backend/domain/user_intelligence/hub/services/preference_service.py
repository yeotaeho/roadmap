# 성향·선호 서비스 — disposition 선택 입력을 user_preferences 에 저장·조회

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from domain.user_intelligence.hub.repositories.preference_repository import PreferenceRepository

SOURCE_USER_FORM = "user_form"


class PreferenceService:
    def __init__(self, db: AsyncSession):
        self.repo = PreferenceRepository(db)

    async def get_preferences(self, user_id: str) -> dict:
        """없으면 전부 null/빈 기본값."""
        pref = await self.repo.fetch_preferences(user_id)
        if pref is None:
            return {
                "workStyle": None,
                "companySizePref": None,
                "workTypePref": None,
                "workValues": [],
                "source": None,
            }
        return {
            "workStyle": pref["work_style"],
            "companySizePref": pref["company_size_pref"],
            "workTypePref": pref["work_type_pref"],
            "workValues": pref["work_values"],
            "source": pref["source"],
        }

    async def upsert_preferences(
        self,
        user_id: str,
        work_style: str | None,
        company_size_pref: str | None,
        work_type_pref: str | None,
        work_values: list,
    ) -> dict:
        await self.repo.upsert_preferences(
            user_id,
            work_style=work_style,
            company_size_pref=company_size_pref,
            work_type_pref=work_type_pref,
            work_values=work_values,
            source=SOURCE_USER_FORM,
        )
        return {
            "workStyle": work_style,
            "companySizePref": company_size_pref,
            "workTypePref": work_type_pref,
            "workValues": work_values,
            "source": SOURCE_USER_FORM,
        }
