# 페르소나(스킬·경험·학력) HTTP 라우터 — user_intelligence 구조화 폼 수집

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from core.api_guards import get_authenticated_user_id
from core.database import get_db
from domain.user_intelligence.hub.services.persona_service import PersonaService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/persona", tags=["persona"])


class SkillItem(BaseModel):
    name: str
    level: str = "입문"  # 입문|중급|심화


class ExperienceItem(BaseModel):
    title: str
    description: str = ""
    period: str = ""


class EducationItem(BaseModel):
    school: str
    major: str = ""
    degree: str = ""
    status: str = ""


class CertificationItem(BaseModel):
    name: str
    issuer: str = ""
    year: str = ""


class LanguageItem(BaseModel):
    language: str
    test: str = ""
    score: str = ""


class LinkItem(BaseModel):
    type: str = ""  # github|portfolio|blog
    url: str = ""


class ProjectItem(BaseModel):
    title: str
    description: str = ""
    role: str = ""
    period: str = ""
    tech_stack: list[str] = Field(default_factory=list)


class PersonaUpsertRequest(BaseModel):
    skills: list[SkillItem] = Field(default_factory=list)
    experiences: list[ExperienceItem] = Field(default_factory=list)
    education: list[EducationItem] = Field(default_factory=list)
    summary: str = ""
    certifications: list[CertificationItem] = Field(default_factory=list)
    languages: list[LanguageItem] = Field(default_factory=list)
    links: list[LinkItem] = Field(default_factory=list)
    projects: list[ProjectItem] = Field(default_factory=list)


@router.get("")
async def get_persona(
    user_id: str = Depends(get_authenticated_user_id),
    db: AsyncSession = Depends(get_db),
):
    """현재 사용자 페르소나 — 없으면 빈 기본값."""
    try:
        persona = await PersonaService(db).get_persona(user_id)
        return {"success": True, "persona": persona}
    except Exception as e:
        logger.error(f"페르소나 조회 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"페르소나 조회 실패: {str(e)}")


@router.put("")
async def upsert_persona(
    request: PersonaUpsertRequest,
    user_id: str = Depends(get_authenticated_user_id),
    db: AsyncSession = Depends(get_db),
):
    """페르소나 upsert — 폼 저장."""
    try:
        persona = await PersonaService(db).upsert_persona(
            user_id,
            skills=[s.model_dump() for s in request.skills],
            experiences=[e.model_dump() for e in request.experiences],
            education=[ed.model_dump() for ed in request.education],
            summary=request.summary,
            certifications=[c.model_dump() for c in request.certifications],
            languages=[lg.model_dump() for lg in request.languages],
            links=[lk.model_dump() for lk in request.links],
            projects=[pj.model_dump() for pj in request.projects],
        )
        return {"success": True, "persona": persona}
    except Exception as e:
        logger.error(f"페르소나 저장 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"페르소나 저장 실패: {str(e)}")
