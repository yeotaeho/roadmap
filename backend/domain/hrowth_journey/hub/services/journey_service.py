# 여정 개요 서비스 — 로드맵 헤더 + 퀘스트 트리 조립 서빙

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from domain.hrowth_journey.hub.repositories.roadmap_repository import RoadmapRepository
from domain.hrowth_journey.hub.services.journey_assembler import assemble_quest_tree


class JourneyService:
    def __init__(self, db: AsyncSession):
        self.repo = RoadmapRepository(db)

    async def get_journey(self, user_id: str) -> dict:
        """JourneyMapTab 서빙 — 로드맵 없으면 roadmap/questTree 모두 None."""
        roadmap = await self.repo.fetch_roadmap(user_id)
        if roadmap is None:
            return {"roadmap": None, "questTree": None}

        quests = await self.repo.fetch_quests(roadmap["id"])
        tree = assemble_quest_tree(quests)
        return {
            "roadmap": {
                "title": roadmap["title"],
                "summary": roadmap["summary"],
                "skillPillars": roadmap["skill_pillars"],
                "bridgeKeywords": roadmap["bridge_keywords"],
            },
            "questTree": tree,
        }
