# Roadmap 리포지토리 — user_roadmaps·roadmap_quests·growth_logs 조회·upsert

from __future__ import annotations

import json
from datetime import date

from sqlalchemy import text

from domain.auth.hub.repositories.base_repository import BaseRepository

_FETCH_ROADMAP = text(
    """
    SELECT id, title, summary, skill_pillars, bridge_keywords, status
    FROM user_roadmaps
    WHERE user_id = CAST(:user_id AS UUID)
    LIMIT 1
    """
)

_FETCH_QUESTS = text(
    """
    SELECT quest_key, parent_key, title, purpose, difficulty, keywords, state, sort_order
    FROM roadmap_quests
    WHERE roadmap_id = :roadmap_id
    ORDER BY sort_order, quest_key
    """
)

_FETCH_LOGS_MONTH = text(
    """
    SELECT log_date, note, completed_quest_keys
    FROM growth_logs
    WHERE user_id = CAST(:user_id AS UUID)
      AND log_date >= :start_date AND log_date < :end_date
    ORDER BY log_date
    """
)

_UPSERT_LOG = text(
    """
    INSERT INTO growth_logs (user_id, log_date, note, completed_quest_keys, created_at, updated_at)
    VALUES (CAST(:user_id AS UUID), :log_date, :note, CAST(:completed AS JSONB), now(), now())
    ON CONFLICT (user_id, log_date) DO UPDATE SET
        note = EXCLUDED.note,
        completed_quest_keys = EXCLUDED.completed_quest_keys,
        updated_at = now()
    """
)

# ── RoadmapPlanner 입력(공유 DB read — 교차 도메인 직접 import 회피) ──
_FETCH_PERSONA = text(
    """
    SELECT skills, experiences, education, summary
    FROM user_personas WHERE user_id = CAST(:user_id AS UUID)
    """
)

_FETCH_SYNC_PROFILE = text(
    """
    SELECT target_job, interest_keywords
    FROM user_sync_profiles WHERE user_id = CAST(:user_id AS UUID)
    """
)

_UPSERT_ROADMAP = text(
    """
    INSERT INTO user_roadmaps (user_id, title, summary, skill_pillars, bridge_keywords, status, generated_at, updated_at)
    VALUES (CAST(:user_id AS UUID), :title, :summary, CAST(:pillars AS JSONB),
            CAST(:bridge AS JSONB), 'active', now(), now())
    ON CONFLICT (user_id) DO UPDATE SET
        title = EXCLUDED.title, summary = EXCLUDED.summary,
        skill_pillars = EXCLUDED.skill_pillars, bridge_keywords = EXCLUDED.bridge_keywords,
        generated_at = now(), updated_at = now()
    RETURNING id
    """
)

_FETCH_TOP_MOVERS = text(
    """
    SELECT sector_slug, score, momentum_pct
    FROM pulse_metrics_log
    WHERE recorded_date = (SELECT MAX(recorded_date) FROM pulse_metrics_log)
    ORDER BY momentum_pct DESC NULLS LAST, score DESC
    LIMIT :lim
    """
)

_FETCH_RECENT_GAPS = text(
    """
    SELECT problem_summary, chance_summary
    FROM gap_issues
    WHERE is_active = true
    ORDER BY published_date DESC, id DESC
    LIMIT :lim
    """
)

_DELETE_QUESTS = text("DELETE FROM roadmap_quests WHERE roadmap_id = :roadmap_id")

_INSERT_QUEST = text(
    """
    INSERT INTO roadmap_quests
        (roadmap_id, quest_key, parent_key, title, purpose, difficulty, keywords, state, sort_order)
    VALUES (:roadmap_id, :quest_key, :parent_key, :title, :purpose, :difficulty,
            CAST(:keywords AS JSONB), :state, :sort_order)
    """
)


class RoadmapRepository(BaseRepository):
    async def fetch_roadmap(self, user_id: str) -> dict | None:
        r = (await self.session.execute(_FETCH_ROADMAP, {"user_id": user_id})).first()
        if r is None:
            return None
        return {
            "id": r.id,
            "title": r.title,
            "summary": r.summary,
            "skill_pillars": r.skill_pillars or [],
            "bridge_keywords": r.bridge_keywords or [],
            "status": r.status,
        }

    async def fetch_quests(self, roadmap_id: int) -> list[dict]:
        rows = (await self.session.execute(_FETCH_QUESTS, {"roadmap_id": roadmap_id})).all()
        return [
            {
                "quest_key": r.quest_key,
                "parent_key": r.parent_key,
                "title": r.title,
                "purpose": r.purpose,
                "difficulty": r.difficulty,
                "keywords": r.keywords or [],
                "state": r.state,
                "sort_order": r.sort_order,
            }
            for r in rows
        ]

    async def fetch_logs_month(self, user_id: str, start: date, end: date) -> list[dict]:
        rows = (
            await self.session.execute(
                _FETCH_LOGS_MONTH, {"user_id": user_id, "start_date": start, "end_date": end}
            )
        ).all()
        return [
            {
                "log_date": r.log_date.isoformat(),
                "note": r.note or "",
                "completed_quest_keys": r.completed_quest_keys or [],
            }
            for r in rows
        ]

    async def upsert_log(
        self, user_id: str, log_date: date, note: str, completed: list[str]
    ) -> None:
        await self.session.execute(
            _UPSERT_LOG,
            {
                "user_id": user_id,
                "log_date": log_date,
                "note": note,
                "completed": json.dumps(completed or []),
            },
        )
        await self.session.commit()

    async def fetch_persona(self, user_id: str) -> dict:
        r = (await self.session.execute(_FETCH_PERSONA, {"user_id": user_id})).first()
        if r is None:
            return {"skills": [], "experiences": [], "education": [], "summary": ""}
        return {
            "skills": r.skills or [],
            "experiences": r.experiences or [],
            "education": r.education or [],
            "summary": r.summary or "",
        }

    async def fetch_sync_profile(self, user_id: str) -> dict:
        r = (await self.session.execute(_FETCH_SYNC_PROFILE, {"user_id": user_id})).first()
        if r is None:
            return {"target_job": None, "interest_keywords": []}
        return {"target_job": r.target_job, "interest_keywords": r.interest_keywords or []}

    async def fetch_top_movers(self, limit: int = 5) -> list[dict]:
        """최신 일자 Pulse 상위 모멘텀 섹터(시장 트렌드 맥락)."""
        rows = (await self.session.execute(_FETCH_TOP_MOVERS, {"lim": limit})).all()
        return [
            {
                "sector_slug": r.sector_slug,
                "score": r.score,
                "momentum_pct": float(r.momentum_pct) if r.momentum_pct is not None else None,
            }
            for r in rows
        ]

    async def fetch_recent_gaps(self, limit: int = 5) -> list[dict]:
        """최근 활성 Gap 미해결 기회 신호."""
        rows = (await self.session.execute(_FETCH_RECENT_GAPS, {"lim": limit})).all()
        return [{"problem": r.problem_summary, "chance": r.chance_summary} for r in rows]

    async def save_roadmap(self, user_id: str, roadmap: dict) -> int:
        """로드맵 헤더 upsert + 퀘스트 전체 교체. roadmap_id 반환."""
        rid = (
            await self.session.execute(
                _UPSERT_ROADMAP,
                {
                    "user_id": user_id,
                    "title": roadmap["title"],
                    "summary": roadmap.get("summary") or "",
                    "pillars": json.dumps(roadmap.get("skill_pillars") or []),
                    "bridge": json.dumps(roadmap.get("bridge_keywords") or []),
                },
            )
        ).scalar_one()
        await self.session.execute(_DELETE_QUESTS, {"roadmap_id": rid})
        for q in roadmap.get("quests") or []:
            await self.session.execute(
                _INSERT_QUEST,
                {
                    "roadmap_id": rid,
                    "quest_key": q["quest_key"],
                    "parent_key": q.get("parent_key"),
                    "title": q["title"],
                    "purpose": q.get("purpose") or "",
                    "difficulty": q["difficulty"],
                    "keywords": json.dumps(q.get("keywords") or []),
                    "state": q["state"],
                    "sort_order": q.get("sort_order") or 0,
                },
            )
        await self.session.commit()
        return rid
