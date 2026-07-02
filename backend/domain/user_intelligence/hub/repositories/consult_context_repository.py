# 상담 맥락 리포지토리 — 페르소나·상위 Pulse 섹터 읽기(로드맵은 코치 위임이라 제외)

from __future__ import annotations

from sqlalchemy import text

from domain.auth.hub.repositories.base_repository import BaseRepository

_FETCH_PERSONA = text(
    "SELECT skills, summary FROM user_personas WHERE user_id = CAST(:uid AS UUID)"
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


class ConsultContextRepository(BaseRepository):
    async def fetch_context(self, user_id: str) -> dict:
        """상담 맥락 묶음 — 페르소나·상위 섹터(로드맵·퀘스트 제외)."""
        pr = (await self.session.execute(_FETCH_PERSONA, {"uid": user_id})).first()
        persona = {
            "skills": (pr.skills or []) if pr else [],
            "summary": (pr.summary or "") if pr else "",
        }
        mrows = (await self.session.execute(_FETCH_MOVERS)).all()
        movers = [{"sector_slug": m.sector_slug, "score": m.score} for m in mrows]
        return {"persona": persona, "movers": movers}
