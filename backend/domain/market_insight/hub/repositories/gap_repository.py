# Gap 리포지토리 — discourse 추출 Silver 적재, Gold(gap_issues·issue_evidences) 사영·서빙

from __future__ import annotations

import json

from sqlalchemy import text

from domain.auth.hub.repositories.base_repository import BaseRepository

# 이미 분류된 discourse 행 중 아직 gap 처리 안 된 행(refined_gap_insights 없음).
_FETCH_UNPROCESSED = text(
    """
    SELECT DISTINCT ON (c.raw_id)
           c.raw_id AS raw_id, c.sector_slug AS sector_slug,
           d.headline AS headline, d.source_url AS url,
           d.headline || E'\n' || COALESCE(d.content_body, '') AS body,
           COALESCE(d.published_at::date, d.collected_at::date) AS ref_date
    FROM refined_text_sector_class c
    JOIN raw_discourse_data d ON d.id = c.raw_id
    LEFT JOIN refined_gap_insights g
           ON g.raw_table_ref = 'raw_discourse_data' AND g.raw_id = c.raw_id AND g.prompt_version = :pv
    WHERE c.raw_table_ref = 'raw_discourse_data'
      AND c.sector_slug IS NOT NULL
      AND c.confidence >= :conf_min
      AND g.id IS NULL
      AND COALESCE(d.published_at::date, d.collected_at::date) >= CURRENT_DATE - CAST(:win AS INTEGER)
    ORDER BY c.raw_id, c.confidence DESC
    LIMIT :lim
    """
)

_UPSERT_SILVER = text(
    """
    INSERT INTO refined_gap_insights
        (sector_slug, data_role, extracted_problem, extracted_opportunity, detail_summary,
         stakeholders, next_actions, reference_date, raw_table_ref, raw_id,
         model_name, prompt_version, input_hash, youth_fit_score)
    VALUES
        (:sector_slug, :data_role, :problem, :opportunity, :detail,
         CAST(:stakeholders AS JSONB), CAST(:next_actions AS JSONB), :ref_date, :raw_table_ref, :raw_id,
         :model_name, :prompt_version, :input_hash, :youth_fit_score)
    ON CONFLICT (raw_table_ref, raw_id, prompt_version) DO NOTHING
    """
)

# 이미 분류된 KIAT/KISTEP 행 중 아직 tech_demand gap 처리 안 된 행(refined_gap_insights 없음).
_FETCH_UNPROCESSED_TECH_DEMAND = text(
    """
    SELECT c.raw_id AS raw_id, c.sector_slug AS sector_slug,
           i.title AS title, i.source_url AS url,
           i.title || E'\n' || COALESCE(i.abstract_text, '') || E'\n'
                  || COALESCE(i.raw_metadata->>'keyword', '') AS body,
           COALESCE(i.published_at::date, i.collected_at::date) AS ref_date
    FROM refined_text_sector_class c
    JOIN raw_innovation_data i ON i.id = c.raw_id
    LEFT JOIN refined_gap_insights g
           ON g.raw_table_ref = 'raw_innovation_data' AND g.raw_id = c.raw_id AND g.prompt_version = :pv
    WHERE c.raw_table_ref = 'raw_innovation_data'
      AND c.sector_slug IS NOT NULL
      AND c.confidence >= :conf_min
      AND i.source_type IN ('INNOVATION_KIAT_TECH_DEMAND', 'INNOVATION_KISTEP_REPORT')
      AND g.id IS NULL
      AND COALESCE(i.published_at::date, i.collected_at::date) >= CURRENT_DATE - CAST(:win AS INTEGER)
    ORDER BY c.confidence DESC
    LIMIT :lim
    """
)

# Gold 사영 — gap_issues 전체 삭제(issue_evidences CASCADE) 후 재생성.
_CLEAR_GOLD = text("DELETE FROM gap_issues")

# 유효 gap(문제 있음) Silver + 원천 메타(근거용). 소스(discourse/innovation)별 evidence COALESCE.
# innovation(tech_demand) 행은 youth_fit_score >= :fit_min 만 통과(discourse 는 NULL 이라 무조건 통과).
_FETCH_SILVER_FOR_GOLD = text(
    """
    SELECT g.sector_slug, g.extracted_problem, g.extracted_opportunity, g.detail_summary,
           g.stakeholders, g.next_actions, g.reference_date, g.raw_table_ref, g.raw_id,
           COALESCE(d.headline, i.title) AS ev_title,
           COALESCE(d.source_url, i.source_url) AS ev_url
    FROM refined_gap_insights g
    LEFT JOIN raw_discourse_data d
           ON d.id = g.raw_id AND g.raw_table_ref = 'raw_discourse_data'
    LEFT JOIN raw_innovation_data i
           ON i.id = g.raw_id AND g.raw_table_ref = 'raw_innovation_data'
    WHERE g.prompt_version = :pv
      AND g.extracted_problem IS NOT NULL
      AND (g.raw_table_ref <> 'raw_innovation_data' OR g.youth_fit_score >= :fit_min)
    ORDER BY g.reference_date DESC NULLS LAST, g.id DESC
    """
)

_INSERT_ISSUE = text(
    """
    INSERT INTO gap_issues
        (sector_slug, problem_summary, chance_summary, detail_summary, stakeholders, next_actions, published_date)
    VALUES
        (:sector_slug, :problem_summary, :chance_summary, :detail_summary,
         CAST(:stakeholders AS JSONB), CAST(:next_actions AS JSONB), :published_date)
    RETURNING id
    """
)

_INSERT_EVIDENCE = text(
    """
    INSERT INTO issue_evidences (issue_id, evidence_type, title, url, raw_table_ref, raw_id)
    VALUES (:issue_id, :evidence_type, :title, :url, :raw_table_ref, :raw_id)
    """
)

_FETCH_ISSUES = text(
    """
    SELECT id, sector_slug, problem_summary, chance_summary, published_date
    FROM gap_issues
    WHERE is_active = true
      AND (CAST(:sector AS TEXT) IS NULL OR sector_slug = CAST(:sector AS TEXT))
    ORDER BY published_date DESC NULLS LAST, id DESC
    LIMIT :lim
    """
)

_FETCH_ISSUE = text(
    """
    SELECT g.id, g.sector_slug, s.name_ko, s.accent_color, g.problem_summary, g.chance_summary,
           g.detail_summary, g.stakeholders, g.next_actions, g.published_date
    FROM gap_issues g
    JOIN sectors s ON s.slug = g.sector_slug
    WHERE g.id = :id
    """
)

_FETCH_EVIDENCES = text(
    "SELECT evidence_type, title, url FROM issue_evidences WHERE issue_id = :id ORDER BY id"
)


class GapRepository(BaseRepository):
    async def fetch_unprocessed(
        self, prompt_version: str, conf_min: float, window_days: int, limit: int
    ) -> list:
        rows = (
            await self.session.execute(
                _FETCH_UNPROCESSED,
                {"pv": prompt_version, "conf_min": conf_min, "win": window_days, "lim": limit},
            )
        ).all()
        return list(rows)

    async def upsert_silver(self, payload: dict) -> None:
        params = dict(payload)
        params.setdefault("data_role", "DISCOURSE_SIGNAL")
        params.setdefault("raw_table_ref", "raw_discourse_data")
        params.setdefault("youth_fit_score", None)
        params["stakeholders"] = json.dumps(payload.get("stakeholders") or [])
        params["next_actions"] = json.dumps(payload.get("next_actions") or [])
        await self.session.execute(_UPSERT_SILVER, params)

    async def fetch_unprocessed_tech_demand(
        self, prompt_version: str, conf_min: float, window_days: int, limit: int
    ) -> list:
        rows = (
            await self.session.execute(
                _FETCH_UNPROCESSED_TECH_DEMAND,
                {"pv": prompt_version, "conf_min": conf_min, "win": window_days, "lim": limit},
            )
        ).all()
        return list(rows)

    async def project_to_gold(self, prompt_version: str, fit_min: float = 0.0) -> int:
        """유효 gap Silver → gap_issues + issue_evidences 멱등 재생성. 적재 이슈 수 반환.

        discourse·innovation(tech_demand) 두 소스를 함께 재조립한다.
        innovation 행은 youth_fit_score >= fit_min 만 Gold 통과.
        """
        await self.session.execute(_CLEAR_GOLD)
        rows = (
            await self.session.execute(
                _FETCH_SILVER_FOR_GOLD, {"pv": prompt_version, "fit_min": fit_min}
            )
        ).all()
        n = 0
        for r in rows:
            issue_id = (
                await self.session.execute(
                    _INSERT_ISSUE,
                    {
                        "sector_slug": r.sector_slug,
                        "problem_summary": (r.extracted_problem or "")[:255],
                        "chance_summary": (r.extracted_opportunity or "")[:255],
                        "detail_summary": r.detail_summary,
                        "stakeholders": json.dumps(r.stakeholders or []),
                        "next_actions": json.dumps(r.next_actions or []),
                        "published_date": r.reference_date,
                    },
                )
            ).scalar_one()
            ev_type = "TECH_DEMAND" if r.raw_table_ref == "raw_innovation_data" else "NEWS"
            await self.session.execute(
                _INSERT_EVIDENCE,
                {
                    "issue_id": issue_id,
                    "evidence_type": ev_type,
                    "title": (r.ev_title or "근거 자료")[:255],
                    "url": r.ev_url,
                    "raw_table_ref": r.raw_table_ref,
                    "raw_id": r.raw_id,
                },
            )
            n += 1
        return n

    async def fetch_issues(self, sector: str | None, limit: int = 50) -> list[dict]:
        rows = (await self.session.execute(_FETCH_ISSUES, {"sector": sector, "lim": limit})).all()
        return [
            {
                "id": r.id,
                "sector_slug": r.sector_slug,
                "problem_summary": r.problem_summary,
                "chance_summary": r.chance_summary,
                "published_date": r.published_date.isoformat() if r.published_date else None,
            }
            for r in rows
        ]

    async def fetch_issue_detail(self, issue_id: int) -> dict | None:
        r = (await self.session.execute(_FETCH_ISSUE, {"id": issue_id})).first()
        if r is None:
            return None
        evs = (await self.session.execute(_FETCH_EVIDENCES, {"id": issue_id})).all()
        return {
            "id": r.id,
            "sector_slug": r.sector_slug,
            "sector_name": r.name_ko,
            "accent_color": r.accent_color,
            "problem_summary": r.problem_summary,
            "chance_summary": r.chance_summary,
            "detail_summary": r.detail_summary,
            "stakeholders": r.stakeholders or [],
            "next_actions": r.next_actions or [],
            "published_date": r.published_date.isoformat() if r.published_date else None,
            "evidences": [{"type": e.evidence_type, "title": e.title, "url": e.url} for e in evs],
        }
