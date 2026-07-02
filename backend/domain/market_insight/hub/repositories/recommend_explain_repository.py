# 추천 설명 리포지토리 — 설명 없는 Sync/Chance 상위 행·사용자 컨텍스트 조회, 설명 기록.

from __future__ import annotations

from sqlalchemy import bindparam, text

from domain.auth.hub.repositories.base_repository import BaseRepository

# 오늘 설명 없는 Sync 상위 행 — 사용자별 점수순 상위 N, '데이터 부족' 배지는 설명할 신호가 없어 제외.
_FETCH_UNEXPLAINED_SYNC = text(
    """
    SELECT user_id, sector_slug, sector_name, score, badge, affinity_score, trend_score FROM (
        SELECT d.user_id, d.sector_slug, s.name_ko AS sector_name, d.score, d.badge,
               i.affinity_score, i.trend_score,
               ROW_NUMBER() OVER (
                   PARTITION BY d.user_id ORDER BY d.score DESC, d.sector_slug
               ) AS rn
        FROM sync_scores_daily d
        JOIN sectors s ON s.slug = d.sector_slug
        LEFT JOIN refined_sync_inputs i
               ON i.user_id = d.user_id AND i.sector_slug = d.sector_slug
              AND i.reference_date = d.recorded_date
        WHERE d.recorded_date = CURRENT_DATE
          AND d.explanation IS NULL
          AND d.badge IS DISTINCT FROM :insufficient
    ) t
    WHERE rn <= :per_user
    """
)

# 설명 없는 Chance 매치 — 사용자별 점수순 상위 N, 활성·미마감 공고만.
_FETCH_UNEXPLAINED_MATCHES = text(
    """
    SELECT user_id, opportunity_id, match_score, match_reason, title, opportunity_type FROM (
        SELECT m.user_id, m.opportunity_id, m.match_score, m.match_reason,
               o.title, o.opportunity_type,
               ROW_NUMBER() OVER (
                   PARTITION BY m.user_id ORDER BY m.match_score DESC NULLS LAST, m.opportunity_id
               ) AS rn
        FROM user_chance_matches m
        JOIN chance_opportunities o ON o.id = m.opportunity_id
        WHERE m.match_explanation IS NULL
          AND o.is_active = true
          AND (o.d_day_date IS NULL OR o.d_day_date >= CURRENT_DATE)
    ) t
    WHERE rn <= :per_user
    """
)

_FETCH_USER_CONTEXT = text(
    """
    SELECT u.id AS user_id, p.target_job, p.interest_keywords,
           sm.riasec, sm.narrative_summary
    FROM users u
    LEFT JOIN user_sync_profiles p ON p.user_id = u.id
    LEFT JOIN user_self_model sm ON sm.user_id = u.id
    WHERE u.id IN :uids
    """
).bindparams(bindparam("uids", expanding=True))

# 프롬프트용 비민감 근거 — 긍정/회피 분리는 서비스에서 수행(민감은 어떤 경우에도 미주입).
_FETCH_CONTEXT_EVIDENCE = text(
    """
    SELECT user_id, dimension, polarity, content
    FROM user_self_model_evidence
    WHERE user_id IN :uids
      AND is_sensitive = false
      AND dimension IN ('like', 'dislike', 'value', 'aspiration', 'skill_signal')
    ORDER BY user_id, confidence DESC NULLS LAST, created_at DESC, id DESC
    """
).bindparams(bindparam("uids", expanding=True))

_UPDATE_SYNC_EXPLANATION = text(
    """
    UPDATE sync_scores_daily SET explanation = :explanation
    WHERE user_id = CAST(:user_id AS UUID) AND sector_slug = :sector_slug
      AND recorded_date = CURRENT_DATE
    """
)

_UPDATE_MATCH_EXPLANATION = text(
    """
    UPDATE user_chance_matches SET match_explanation = :explanation
    WHERE user_id = CAST(:user_id AS UUID) AND opportunity_id = :opportunity_id
    """
)


class RecommendExplainRepository(BaseRepository):
    async def fetch_unexplained_sync(self, per_user: int, insufficient_badge: str) -> list:
        return list(
            (
                await self.session.execute(
                    _FETCH_UNEXPLAINED_SYNC,
                    {"per_user": per_user, "insufficient": insufficient_badge},
                )
            ).all()
        )

    async def fetch_unexplained_matches(self, per_user: int) -> list:
        return list(
            (await self.session.execute(_FETCH_UNEXPLAINED_MATCHES, {"per_user": per_user})).all()
        )

    async def fetch_user_context(self, user_ids: list[str]) -> dict[str, dict]:
        if not user_ids:
            return {}
        rows = (await self.session.execute(_FETCH_USER_CONTEXT, {"uids": user_ids})).all()
        return {
            str(r.user_id): {
                "target_job": r.target_job,
                "interest_keywords": r.interest_keywords if isinstance(r.interest_keywords, list) else [],
                "riasec": r.riasec,
                "narrative_summary": r.narrative_summary,
            }
            for r in rows
        }

    async def fetch_context_evidence(self, user_ids: list[str]) -> dict[str, list[dict]]:
        if not user_ids:
            return {}
        rows = (await self.session.execute(_FETCH_CONTEXT_EVIDENCE, {"uids": user_ids})).all()
        out: dict[str, list[dict]] = {}
        for r in rows:
            out.setdefault(str(r.user_id), []).append(
                {"dimension": r.dimension, "polarity": r.polarity, "content": r.content}
            )
        return out

    async def update_sync_explanation(self, user_id: str, sector_slug: str, explanation: str) -> None:
        await self.session.execute(
            _UPDATE_SYNC_EXPLANATION,
            {"user_id": user_id, "sector_slug": sector_slug, "explanation": explanation},
        )

    async def update_match_explanation(self, user_id: str, opportunity_id: int, explanation: str) -> None:
        await self.session.execute(
            _UPDATE_MATCH_EXPLANATION,
            {"user_id": user_id, "opportunity_id": opportunity_id, "explanation": explanation},
        )
