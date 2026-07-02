# 추천 설명 리포지토리 — 설명 없는 Sync/Chance 상위 행·사용자 컨텍스트 조회, 설명 기록.

from __future__ import annotations

from sqlalchemy import bindparam, text
from sqlalchemy.dialects.postgresql import UUID

from domain.auth.hub.repositories.base_repository import BaseRepository

# 이번 실행이 처리할 사용자 집합 — 두 소스(Sync·Chance) 합집합을 SQL 에서 캡.
# 사용자 수가 커져도 후속 페치가 캡된 집합만 스캔하고, sync-먼저 그룹핑에 의한 chance-only 기아도 없다.
_FETCH_PENDING_USER_IDS = text(
    """
    SELECT DISTINCT user_id FROM (
        SELECT d.user_id
        FROM sync_scores_daily d
        WHERE d.recorded_date = CURRENT_DATE
          AND d.explanation IS NULL
          AND d.badge IS DISTINCT FROM :insufficient
        UNION
        SELECT m.user_id
        FROM user_chance_matches m
        JOIN chance_opportunities o ON o.id = m.opportunity_id
        WHERE m.match_explanation IS NULL
          AND o.is_active = true
          AND (o.d_day_date IS NULL OR o.d_day_date >= CURRENT_DATE)
    ) u
    ORDER BY user_id
    LIMIT :max_users
    """
)

# 오늘 설명 없는 Sync 상위 행 — 캡된 사용자 집합 한정, 사용자별 점수순 상위 N,
# '데이터 부족' 배지는 설명할 신호가 없어 제외.
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
          AND d.user_id IN :uids
    ) t
    WHERE rn <= :per_user
    """
).bindparams(bindparam("uids", expanding=True, type_=UUID(as_uuid=False)))

# 설명 없는 Chance 매치 — 캡된 사용자 집합 한정, 사용자별 점수순 상위 N, 활성·미마감 공고만.
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
          AND m.user_id IN :uids
    ) t
    WHERE rn <= :per_user
    """
).bindparams(bindparam("uids", expanding=True, type_=UUID(as_uuid=False)))

_FETCH_USER_CONTEXT = text(
    """
    SELECT u.id AS user_id, p.target_job, p.interest_keywords,
           sm.riasec, sm.narrative_summary
    FROM users u
    LEFT JOIN user_sync_profiles p ON p.user_id = u.id
    LEFT JOIN user_self_model sm ON sm.user_id = u.id
    WHERE u.id IN :uids
    """
).bindparams(bindparam("uids", expanding=True, type_=UUID(as_uuid=False)))

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
).bindparams(bindparam("uids", expanding=True, type_=UUID(as_uuid=False)))

# 설명 기록은 생성 근거가 된 결정론 입력이 그대로일 때만 — LLM 대기 중 동시 재점수(시간별 잡 중첩 등)로
# 무효화된 행에 낡은 설명이 되살아나는 것을 방지한다.
_UPDATE_SYNC_EXPLANATION = text(
    """
    UPDATE sync_scores_daily SET explanation = :explanation
    WHERE user_id = CAST(:user_id AS UUID) AND sector_slug = :sector_slug
      AND recorded_date = CURRENT_DATE
      AND explanation IS NULL
      AND score = :score
      AND badge IS NOT DISTINCT FROM :badge
    """
)

_UPDATE_MATCH_EXPLANATION = text(
    """
    UPDATE user_chance_matches SET match_explanation = :explanation
    WHERE user_id = CAST(:user_id AS UUID) AND opportunity_id = :opportunity_id
      AND match_explanation IS NULL
      AND match_score IS NOT DISTINCT FROM :match_score
      AND match_reason IS NOT DISTINCT FROM :match_reason
    """
)


class RecommendExplainRepository(BaseRepository):
    async def fetch_pending_user_ids(self, insufficient_badge: str, max_users: int) -> list[str]:
        """설명 대상(둘 중 한 소스라도 미설명) 사용자 id 를 SQL 캡으로 상위 max_users 만 반환한다."""
        rows = (
            await self.session.execute(
                _FETCH_PENDING_USER_IDS,
                {"insufficient": insufficient_badge, "max_users": max_users},
            )
        ).all()
        return [str(r.user_id) for r in rows]

    async def fetch_unexplained_sync(
        self, user_ids: list[str], per_user: int, insufficient_badge: str
    ) -> list:
        if not user_ids:
            return []
        return list(
            (
                await self.session.execute(
                    _FETCH_UNEXPLAINED_SYNC,
                    {"uids": user_ids, "per_user": per_user, "insufficient": insufficient_badge},
                )
            ).all()
        )

    async def fetch_unexplained_matches(self, user_ids: list[str], per_user: int) -> list:
        if not user_ids:
            return []
        return list(
            (
                await self.session.execute(
                    _FETCH_UNEXPLAINED_MATCHES, {"uids": user_ids, "per_user": per_user}
                )
            ).all()
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

    async def update_sync_explanation(
        self, user_id: str, sector_slug: str, explanation: str, score: int, badge: str | None
    ) -> int:
        """가드(입력 불변·미설명) 통과 시에만 기록. 실제 갱신된 행 수(0|1) 반환."""
        result = await self.session.execute(
            _UPDATE_SYNC_EXPLANATION,
            {
                "user_id": user_id,
                "sector_slug": sector_slug,
                "explanation": explanation,
                "score": score,
                "badge": badge,
            },
        )
        return result.rowcount or 0

    async def update_match_explanation(
        self,
        user_id: str,
        opportunity_id: int,
        explanation: str,
        match_score: int | None,
        match_reason: str | None,
    ) -> int:
        """가드(입력 불변·미설명) 통과 시에만 기록. 실제 갱신된 행 수(0|1) 반환."""
        result = await self.session.execute(
            _UPDATE_MATCH_EXPLANATION,
            {
                "user_id": user_id,
                "opportunity_id": opportunity_id,
                "explanation": explanation,
                "match_score": match_score,
                "match_reason": match_reason,
            },
        )
        return result.rowcount or 0
