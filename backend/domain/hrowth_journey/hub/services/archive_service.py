# 성장 아카이브 서비스 — 월별 일별 로그 조회·upsert

from __future__ import annotations

from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from domain.hrowth_journey.hub.repositories.roadmap_repository import RoadmapRepository


def _month_bounds(year: int, month: int) -> tuple[date, date]:
    """[해당 월 1일, 다음 달 1일) 반열린 구간."""
    start = date(year, month, 1)
    end = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    return start, end


class ArchiveService:
    def __init__(self, db: AsyncSession):
        self.repo = RoadmapRepository(db)

    async def get_month(self, user_id: str, year: int, month: int) -> dict:
        """달력 시드 — {"YYYY-MM-DD": {completedQuestIds, note}}."""
        start, end = _month_bounds(year, month)
        rows = await self.repo.fetch_logs_month(user_id, start, end)
        logs = {
            r["log_date"]: {
                "completedQuestIds": r["completed_quest_keys"],
                "note": r["note"],
            }
            for r in rows
        }
        return {"logs": logs}

    async def upsert_day(
        self, user_id: str, log_date: date, completed_quest_ids: list[str], note: str
    ) -> dict:
        await self.repo.upsert_log(user_id, log_date, note, completed_quest_ids)
        return {
            "date": log_date.isoformat(),
            "completedQuestIds": completed_quest_ids,
            "note": note,
        }
