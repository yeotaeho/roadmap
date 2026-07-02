# Chance 리포지토리 — opportunity 추출 Silver, Gold(chance_opportunities·user_chance_matches) 사영·매칭·서빙

from __future__ import annotations

import json

from sqlalchemy import text

from domain.auth.hub.repositories.base_repository import BaseRepository

# 아직 추출 안 된 opportunity 행(refined_chance_insights 없음).
_FETCH_UNPROCESSED = text(
    """
    SELECT o.id AS raw_id, o.raw_title AS title, o.host_name AS host_name,
           o.deadline_at::date AS deadline, o.source_url AS url,
           o.raw_title || E'\n' || COALESCE(o.raw_content, '') || E'\n'
               || COALESCE(o.raw_metadata::text, '') AS body,
           COALESCE(o.published_at::date, o.collected_at::date) AS ref_date
    FROM raw_opportunity_data o
    LEFT JOIN refined_chance_insights c
           ON c.raw_table_ref = 'raw_opportunity_data' AND c.raw_id = o.id AND c.prompt_version = :pv
    WHERE c.id IS NULL
      AND (o.deadline_at IS NULL OR o.deadline_at::date >= CURRENT_DATE)
      AND COALESCE(o.published_at::date, o.collected_at::date) >= CURRENT_DATE - CAST(:win AS INTEGER)
    ORDER BY o.deadline_at ASC NULLS LAST, o.id
    LIMIT :lim
    """
)

_UPSERT_SILVER = text(
    """
    INSERT INTO refined_chance_insights
        (sector_slug, data_role, extracted_type, extracted_target, extracted_benefits,
         extracted_deadline, extracted_qualifications, reference_date, raw_table_ref, raw_id,
         model_name, prompt_version, input_hash)
    VALUES
        (:sector_slug, 'OPPORTUNITY_SIGNAL', :extracted_type, CAST(:target AS JSONB),
         CAST(:benefits AS JSONB), :deadline, CAST(:qualifications AS JSONB), :ref_date,
         'raw_opportunity_data', :raw_id, :model_name, :prompt_version, :input_hash)
    ON CONFLICT (raw_table_ref, raw_id, prompt_version) DO NOTHING
    """
)

# Gold 사영 — 안정 id 유지 위해 raw 리니지 자연키로 upsert(전체 재생성 아님).
_FETCH_SILVER_FOR_GOLD = text(
    """
    SELECT c.sector_slug, c.extracted_type, c.extracted_target, c.extracted_benefits,
           c.extracted_qualifications, c.extracted_deadline, c.raw_id,
           o.raw_title AS title, o.host_name AS host_name, o.deadline_at::date AS deadline,
           o.source_url AS url
    FROM refined_chance_insights c
    JOIN raw_opportunity_data o ON o.id = c.raw_id
    WHERE c.prompt_version = :pv AND c.extracted_type IS NOT NULL
    """
)

_UPSERT_OPPORTUNITY = text(
    """
    INSERT INTO chance_opportunities
        (sector_slug, title, opportunity_type, host_name, benefit_summary, target_audience,
         d_day_date, brief_description, eligibility_checks, actionable_preps, reference_links,
         raw_table_ref, raw_id, is_active)
    VALUES
        (:sector_slug, :title, :opportunity_type, :host_name, :benefit_summary, :target_audience,
         :d_day_date, :brief_description, CAST(:eligibility_checks AS JSONB),
         CAST(:actionable_preps AS JSONB), CAST(:reference_links AS JSONB),
         'raw_opportunity_data', :raw_id, true)
    ON CONFLICT (raw_table_ref, raw_id) DO UPDATE SET
        sector_slug = EXCLUDED.sector_slug,
        title = EXCLUDED.title,
        opportunity_type = EXCLUDED.opportunity_type,
        host_name = EXCLUDED.host_name,
        benefit_summary = EXCLUDED.benefit_summary,
        target_audience = EXCLUDED.target_audience,
        d_day_date = EXCLUDED.d_day_date,
        brief_description = EXCLUDED.brief_description,
        eligibility_checks = EXCLUDED.eligibility_checks,
        reference_links = EXCLUDED.reference_links,
        is_active = true
    """
)

_FETCH_OPPORTUNITIES = text(
    """
    SELECT id, sector_slug, title, opportunity_type, host_name, benefit_summary, d_day_date
    FROM chance_opportunities
    WHERE is_active = true
      AND (d_day_date IS NULL OR d_day_date >= CURRENT_DATE)
      AND (CAST(:sector AS TEXT) IS NULL OR sector_slug = CAST(:sector AS TEXT))
    ORDER BY d_day_date ASC NULLS LAST, id DESC
    LIMIT :lim
    """
)

_FETCH_OPPORTUNITY = text(
    """
    SELECT id, sector_slug, title, opportunity_type, host_name, benefit_summary, target_audience,
           d_day_date, brief_description, eligibility_checks, actionable_preps, reference_links
    FROM chance_opportunities WHERE id = :id
    """
)

# 매칭용 — 활성 공고 텍스트, 프로필 보유 사용자.
_FETCH_ACTIVE_OPPS = text(
    """
    SELECT id, sector_slug, title, opportunity_type, benefit_summary, target_audience
    FROM chance_opportunities
    WHERE is_active = true AND (d_day_date IS NULL OR d_day_date >= CURRENT_DATE)
    """
)

# 매칭용 사용자 — users 기준. 프로필이 없어도 자기모델·비민감 근거가 있으면 포함(코치-only).
_FETCH_USERS = text(
    """
    SELECT u.id AS user_id, p.target_job, p.interest_keywords,
           pref.work_style, pref.company_size_pref, pref.work_type_pref, pref.work_values,
           per.skills, per.certifications, per.languages, per.projects
    FROM users u
    LEFT JOIN user_sync_profiles p ON p.user_id = u.id
    LEFT JOIN user_preferences pref ON pref.user_id = u.id
    LEFT JOIN user_personas per ON per.user_id = u.id
    LEFT JOIN user_self_model sm ON sm.user_id = u.id
    WHERE p.user_id IS NOT NULL OR sm.user_id IS NOT NULL
       OR EXISTS (
            SELECT 1 FROM user_self_model_evidence ev
            WHERE ev.user_id = u.id AND ev.is_sensitive = false
          )
    """
)

# 의미 매칭 — (사용자 임베딩 × 활성 공고 임베딩) 코사인 적합도. 동일 모델끼리만 비교.
_FETCH_MATCH_AFFINITIES = text(
    """
    SELECT u.user_id, de.source_id AS opportunity_id,
           (1 - (de.embedding <=> u.embedding)) AS cosine
    FROM user_embeddings u
    JOIN document_embeddings de
      ON de.source_table = 'chance_opportunities'
     AND de.embedding_model = u.embedding_model
    JOIN chance_opportunities o ON o.id = de.source_id
    WHERE o.is_active = true AND (o.d_day_date IS NULL OR o.d_day_date >= CURRENT_DATE)
    """
)

_UPSERT_MATCH = text(
    """
    INSERT INTO user_chance_matches (user_id, opportunity_id, match_score, match_reason, updated_at)
    VALUES (:user_id, :opportunity_id, :match_score, :match_reason, now())
    ON CONFLICT (user_id, opportunity_id) DO UPDATE SET
        match_score = EXCLUDED.match_score,
        match_reason = EXCLUDED.match_reason,
        updated_at = now()
    """
)

_FETCH_MATCHES = text(
    """
    SELECT m.opportunity_id, m.match_score, m.match_reason, m.is_saved, m.is_applied,
           o.title, o.opportunity_type, o.host_name, o.d_day_date, o.sector_slug
    FROM user_chance_matches m
    JOIN chance_opportunities o ON o.id = m.opportunity_id
    WHERE m.user_id = CAST(:user_id AS UUID) AND o.is_active = true
    ORDER BY m.match_score DESC NULLS LAST, o.d_day_date ASC NULLS LAST
    LIMIT :lim
    """
)


class ChanceRepository(BaseRepository):
    async def fetch_unprocessed(
        self, prompt_version: str, window_days: int, limit: int
    ) -> list:
        rows = (
            await self.session.execute(
                _FETCH_UNPROCESSED, {"pv": prompt_version, "win": window_days, "lim": limit}
            )
        ).all()
        return list(rows)

    async def upsert_silver(self, payload: dict) -> None:
        params = dict(payload)
        for k in ("target", "benefits", "qualifications"):
            params[k] = json.dumps(payload.get(k) or [])
        await self.session.execute(_UPSERT_SILVER, params)

    async def project_to_gold(self, prompt_version: str) -> int:
        """유효 Silver → chance_opportunities 멱등 upsert(안정 id). 적재 공고 수 반환."""
        rows = (await self.session.execute(_FETCH_SILVER_FOR_GOLD, {"pv": prompt_version})).all()
        n = 0
        for r in rows:
            benefits = r.extracted_benefits or []
            target = r.extracted_target or []
            await self.session.execute(
                _UPSERT_OPPORTUNITY,
                {
                    "sector_slug": r.sector_slug,
                    "title": (r.title or "공고")[:255],
                    "opportunity_type": r.extracted_type,
                    "host_name": (r.host_name or None) and r.host_name[:150],
                    "benefit_summary": ("; ".join(benefits))[:255] or None,
                    "target_audience": ("; ".join(target))[:255] or None,
                    "d_day_date": r.deadline or r.extracted_deadline,
                    "brief_description": "; ".join(benefits) or (r.title or None),
                    "eligibility_checks": json.dumps(r.extracted_qualifications or []),
                    "actionable_preps": json.dumps([]),
                    "reference_links": json.dumps([r.url] if r.url else []),
                    "raw_id": r.raw_id,
                },
            )
            n += 1
        return n

    async def fetch_opportunities(self, sector: str | None, limit: int = 50) -> list[dict]:
        rows = (
            await self.session.execute(_FETCH_OPPORTUNITIES, {"sector": sector, "lim": limit})
        ).all()
        return [
            {
                "id": r.id,
                "sector_slug": r.sector_slug,
                "title": r.title,
                "opportunity_type": r.opportunity_type,
                "host_name": r.host_name,
                "benefit_summary": r.benefit_summary,
                "d_day_date": r.d_day_date.isoformat() if r.d_day_date else None,
            }
            for r in rows
        ]

    async def fetch_opportunity_detail(self, opp_id: int) -> dict | None:
        r = (await self.session.execute(_FETCH_OPPORTUNITY, {"id": opp_id})).first()
        if r is None:
            return None
        return {
            "id": r.id,
            "sector_slug": r.sector_slug,
            "title": r.title,
            "opportunity_type": r.opportunity_type,
            "host_name": r.host_name,
            "benefit_summary": r.benefit_summary,
            "target_audience": r.target_audience,
            "d_day_date": r.d_day_date.isoformat() if r.d_day_date else None,
            "brief_description": r.brief_description,
            "eligibility_checks": r.eligibility_checks or [],
            "actionable_preps": r.actionable_preps or [],
            "reference_links": r.reference_links or [],
        }

    async def fetch_active_opps(self) -> list:
        return list((await self.session.execute(_FETCH_ACTIVE_OPPS)).all())

    async def fetch_match_affinities(self) -> list:
        """(user_id, opportunity_id, cosine) — 임베딩 보유 사용자×활성 공고만."""
        return list((await self.session.execute(_FETCH_MATCH_AFFINITIES)).all())

    async def fetch_users(self) -> list:
        return list((await self.session.execute(_FETCH_USERS)).all())

    async def upsert_match(
        self, user_id, opportunity_id: int, score: int, reason: str
    ) -> None:
        await self.session.execute(
            _UPSERT_MATCH,
            {
                "user_id": user_id,
                "opportunity_id": opportunity_id,
                "match_score": score,
                "match_reason": reason,
            },
        )

    async def fetch_matches(self, user_id: str, limit: int = 50) -> list[dict]:
        rows = (
            await self.session.execute(_FETCH_MATCHES, {"user_id": user_id, "lim": limit})
        ).all()
        return [
            {
                "opportunity_id": r.opportunity_id,
                "match_score": r.match_score,
                "match_reason": r.match_reason,
                "is_saved": r.is_saved,
                "is_applied": r.is_applied,
                "title": r.title,
                "opportunity_type": r.opportunity_type,
                "host_name": r.host_name,
                "sector_slug": r.sector_slug,
                "d_day_date": r.d_day_date.isoformat() if r.d_day_date else None,
            }
            for r in rows
        ]
