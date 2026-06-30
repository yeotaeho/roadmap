# 기본정보 서비스 — 데모그래픽 선택 입력을 user_profiles 에 저장·조회

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from domain.auth.hub.repositories.profile_repository import ProfileRepository

# 폼 입력 출처 — coach 추출(미래) 과 구분.
SOURCE_USER_FORM = "user_form"


class ProfileService:
    def __init__(self, db: AsyncSession):
        self.repo = ProfileRepository(db)

    async def get_profile(self, user_id: str) -> dict:
        """없으면 전부 null 기본값(폼 초기 렌더용)."""
        profile = await self.repo.fetch_profile(user_id)
        if profile is None:
            return {
                "birthYear": None,
                "gender": None,
                "region": None,
                "currentStatus": None,
                "educationLevel": None,
                "source": None,
            }
        return {
            "birthYear": profile["birth_year"],
            "gender": profile["gender"],
            "region": profile["region"],
            "currentStatus": profile["current_status"],
            "educationLevel": profile["education_level"],
            "source": profile["source"],
        }

    async def upsert_profile(
        self,
        user_id: str,
        birth_year: int | None,
        gender: str | None,
        region: str | None,
        current_status: str | None,
        education_level: str | None,
    ) -> dict:
        await self.repo.upsert_profile(
            user_id,
            birth_year=birth_year,
            gender=gender,
            region=region,
            current_status=current_status,
            education_level=education_level,
            source=SOURCE_USER_FORM,
        )
        return {
            "birthYear": birth_year,
            "gender": gender,
            "region": region,
            "currentStatus": current_status,
            "educationLevel": education_level,
            "source": SOURCE_USER_FORM,
        }
