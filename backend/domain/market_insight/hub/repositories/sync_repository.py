# Sync 리포지토리 — 사용자×섹터 임베딩 코사인 적합도·Pulse 트렌드 조회, Silver/Gold 적재·서빙

from __future__ import annotations

import json

from sqlalchemy import text

from domain.auth.hub.repositories.base_repository import BaseRepository

# 섹터 센트로이드(문서 임베딩 평균) × 사용자 임베딩 코사인 적합도.
_FETCH_AFFINITY = text(
    """
    WITH sector_centroid AS (
        SELECT sector_slug, avg(embedding) AS centroid
        FROM document_embeddings WHERE sector_slug IS NOT NULL
        GROUP BY sector_slug
    )
    SELECT u.user_id, sc.sector_slug, (1 - (sc.centroid <=> u.embedding)) AS affinity
    FROM user_embeddings u CROSS JOIN sector_centroid sc
    """
)

# 섹터별 최신 Pulse 점수(트렌드 입력).
_FETCH_TREND = text(
    """
    SELECT DISTINCT ON (sector_slug) sector_slug, score
    FROM pulse_metrics_log
    ORDER BY sector_slug, recorded_date DESC
    """
)

_FETCH_USER_KEYWORDS = text("SELECT user_id, interest_keywords FROM user_sync_profiles")

_UPSERT_SYNC_INPUT = text(
    """
    INSERT INTO refined_sync_inputs
        (user_id, sector_slug, reference_date, affinity_score, trend_score,
         contributing_keywords, model_name, prompt_version)
    VALUES
        (:user_id, :sector_slug, (now() AT TIME ZONE 'Asia/Seoul')::date, :affinity_score, :trend_score,
         CAST(:keywords AS JSONB), :model_name, :prompt_version)
    ON CONFLICT (user_id, sector_slug, reference_date) DO UPDATE SET
        affinity_score = EXCLUDED.affinity_score,
        trend_score = EXCLUDED.trend_score,
        contributing_keywords = EXCLUDED.contributing_keywords,
        processed_at = now()
    """
)

_UPSERT_SYNC_GOLD = text(
    """
    INSERT INTO sync_scores_daily (user_id, sector_slug, recorded_date, score, badge)
    VALUES (:user_id, :sector_slug, (now() AT TIME ZONE 'Asia/Seoul')::date, :score, :badge)
    ON CONFLICT (user_id, sector_slug, recorded_date) DO UPDATE SET
        score = EXCLUDED.score,
        badge = EXCLUDED.badge,
        explanation = CASE
            WHEN sync_scores_daily.score = EXCLUDED.score
             AND sync_scores_daily.badge IS NOT DISTINCT FROM EXCLUDED.badge
            THEN sync_scores_daily.explanation ELSE NULL END
    """
)

_FETCH_SCORES = text(
    """
    SELECT DISTINCT ON (d.sector_slug)
        d.sector_slug, s.name_ko, s.accent_color, d.score, d.badge, d.explanation, d.recorded_date
    FROM sync_scores_daily d
    JOIN sectors s ON s.slug = d.sector_slug
    WHERE d.user_id = CAST(:user_id AS UUID)
    ORDER BY d.sector_slug, d.recorded_date DESC
    """
)

# 사용자 전체 싱크 추이 — 일자별 섹터 평균(스파크라인 입력). 최근 N일.
_FETCH_SCORE_HISTORY = text(
    """
    SELECT recorded_date, ROUND(AVG(score))::int AS score
    FROM sync_scores_daily
    WHERE user_id = CAST(:user_id AS UUID)
    GROUP BY recorded_date
    ORDER BY recorded_date ASC
    """
)


class SyncRepository(BaseRepository):
    async def fetch_affinity(self) -> list:
        return list((await self.session.execute(_FETCH_AFFINITY)).all())

    async def fetch_trend(self) -> dict[str, int]:
        rows = (await self.session.execute(_FETCH_TREND)).all()
        return {r.sector_slug: int(r.score) for r in rows}

    async def fetch_user_keywords(self) -> dict:
        rows = (await self.session.execute(_FETCH_USER_KEYWORDS)).all()
        return {
            r.user_id: (r.interest_keywords if isinstance(r.interest_keywords, list) else [])
            for r in rows
        }

    async def upsert_sync_input(self, payload: dict) -> None:
        params = dict(payload)
        params["keywords"] = json.dumps(payload.get("keywords") or [])
        await self.session.execute(_UPSERT_SYNC_INPUT, params)

    async def upsert_sync_gold(self, user_id, sector_slug: str, score: int, badge: str) -> None:
        await self.session.execute(
            _UPSERT_SYNC_GOLD,
            {"user_id": user_id, "sector_slug": sector_slug, "score": score, "badge": badge},
        )

    async def fetch_scores(self, user_id: str) -> list[dict]:
        rows = (await self.session.execute(_FETCH_SCORES, {"user_id": user_id})).all()
        result = [
            {
                "sector_slug": r.sector_slug,
                "sector_name": r.name_ko,
                "accent_color": r.accent_color,
                "score": r.score,
                "badge": r.badge,
                "explanation": r.explanation,
                "recorded_date": r.recorded_date.isoformat() if r.recorded_date else None,
            }
            for r in rows
        ]
        result.sort(key=lambda x: x["score"], reverse=True)
        return result

    async def fetch_score_history(self, user_id: str) -> list[dict]:
        rows = (await self.session.execute(_FETCH_SCORE_HISTORY, {"user_id": user_id})).all()
        return [
            {"date": r.recorded_date.isoformat() if r.recorded_date else None, "score": int(r.score)}
            for r in rows
        ]
