# 코치 맥락 리포지토리 — 페르소나·활성 로드맵·상위 Pulse 섹터 읽기(공유 DB read)

from __future__ import annotations

from sqlalchemy import text

from domain.auth.hub.repositories.base_repository import BaseRepository

_FETCH_PERSONA = text(
    "SELECT skills, summary FROM user_personas WHERE user_id = CAST(:uid AS UUID)"
)

_FETCH_ROADMAP = text(
    "SELECT id, title, summary FROM user_roadmaps WHERE user_id = CAST(:uid AS UUID) LIMIT 1"
)

_FETCH_ACTIVE_QUESTS = text(
    """
    SELECT title, state FROM roadmap_quests
    WHERE roadmap_id = :rid AND state IN ('start', 'active', 'available')
    ORDER BY sort_order, quest_key
    LIMIT 6
    """
)

_FETCH_MOVERS = text(
    """
    SELECT sector_slug, score
    FROM pulse_metrics_log
    WHERE recorded_date = (SELECT MAX(recorded_date) FROM pulse_metrics_log)
    ORDER BY momentum_pct DESC NULLS LAST, score DESC
    LIMIT 3
    """
)


class CoachRepository(BaseRepository):
    async def fetch_context(self, user_id: str) -> dict:
        """코치 맥락 묶음 — 페르소나·로드맵·활성 퀘스트·상위 섹터."""
        pr = (await self.session.execute(_FETCH_PERSONA, {"uid": user_id})).first()
        persona = {
            "skills": (pr.skills or []) if pr else [],
            "summary": (pr.summary or "") if pr else "",
        }
        rm = (await self.session.execute(_FETCH_ROADMAP, {"uid": user_id})).first()
        roadmap = {"title": rm.title, "summary": rm.summary} if rm else None
        quests: list[dict] = []
        if rm:
            qrows = (await self.session.execute(_FETCH_ACTIVE_QUESTS, {"rid": rm.id})).all()
            quests = [{"title": q.title, "state": q.state} for q in qrows]
        mrows = (await self.session.execute(_FETCH_MOVERS)).all()
        movers = [{"sector_slug": m.sector_slug, "score": m.score} for m in mrows]
        return {"persona": persona, "roadmap": roadmap, "quests": quests, "movers": movers}
