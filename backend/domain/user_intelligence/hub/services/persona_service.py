# 페르소나 서비스 — 구조화 폼 입력을 user_personas 에 저장·조회

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from domain.user_intelligence.hub.repositories.persona_repository import PersonaRepository

# 폼 입력 출처 — mock(시드) 와 구분.
SOURCE_USER_FORM = "user_form"


class PersonaService:
    def __init__(self, db: AsyncSession):
        self.repo = PersonaRepository(db)

    async def get_persona(self, user_id: str) -> dict:
        """없으면 빈 기본값(폼 초기 렌더용)."""
        persona = await self.repo.fetch_persona(user_id)
        if persona is None:
            return {"skills": [], "experiences": [], "education": [], "summary": "", "source": None}
        return {
            "skills": persona["skills"],
            "experiences": persona["experiences"],
            "education": persona["education"],
            "summary": persona["summary"],
            "source": persona["source"],
        }

    async def upsert_persona(
        self,
        user_id: str,
        skills: list,
        experiences: list,
        education: list,
        summary: str,
    ) -> dict:
        await self.repo.upsert_persona(
            user_id,
            education=education,
            experiences=experiences,
            skills=skills,
            summary=summary,
            source=SOURCE_USER_FORM,
        )
        return {
            "skills": skills,
            "experiences": experiences,
            "education": education,
            "summary": summary,
            "source": SOURCE_USER_FORM,
        }
