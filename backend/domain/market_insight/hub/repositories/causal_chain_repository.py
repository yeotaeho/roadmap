# 인과사슬 리포지토리 — economic 추출 Silver 적재, Gold(causal_chains) 사영·서빙

from __future__ import annotations

from sqlalchemy import text

from domain.auth.hub.repositories.base_repository import BaseRepository

# 분류된 economic 행 중 아직 causal 처리 안 된 행(refined_causal_chain_insights 없음).
_FETCH_UNPROCESSED = text(
    """
    SELECT DISTINCT ON (c.raw_id)
           c.raw_id AS raw_id, c.sector_slug AS sector_slug,
           e.raw_title || E'\n' ||
           COALESCE(e.raw_metadata->>'content_text', e.raw_metadata->>'body_text',
                    e.raw_metadata->>'summary', '') AS body,
           COALESCE((e.published_at AT TIME ZONE 'Asia/Seoul')::date, (e.collected_at AT TIME ZONE 'Asia/Seoul')::date) AS ref_date
    FROM refined_text_sector_class c
    JOIN raw_economic_data e ON e.id = c.raw_id
    LEFT JOIN refined_causal_chain_insights cc
           ON cc.raw_table_ref = 'raw_economic_data' AND cc.raw_id = c.raw_id AND cc.prompt_version = :pv
    WHERE c.raw_table_ref = 'raw_economic_data'
      AND c.sector_slug IS NOT NULL
      AND c.confidence >= :conf_min
      AND cc.id IS NULL
      AND COALESCE((e.published_at AT TIME ZONE 'Asia/Seoul')::date, (e.collected_at AT TIME ZONE 'Asia/Seoul')::date) >= (now() AT TIME ZONE 'Asia/Seoul')::date - CAST(:win AS INTEGER)
    ORDER BY c.raw_id, c.confidence DESC
    LIMIT :lim
    """
)

_UPSERT_SILVER = text(
    """
    INSERT INTO refined_causal_chain_insights
        (sector_slug, macro_event, industry_impact, youth_chance, reference_date,
         raw_table_ref, raw_id, model_name, prompt_version, input_hash)
    VALUES
        (:sector_slug, :macro_event, :industry_impact, :youth_chance, :ref_date,
         'raw_economic_data', :raw_id, :model_name, :prompt_version, :input_hash)
    ON CONFLICT (raw_table_ref, raw_id, prompt_version) DO NOTHING
    """
)

_CLEAR_GOLD = text("DELETE FROM causal_chains")

# 섹터별 최신 유효(macro 있음) 인과사슬 1개.
_FETCH_SILVER_FOR_GOLD = text(
    """
    SELECT DISTINCT ON (sector_slug)
           sector_slug, macro_event, industry_impact, youth_chance, reference_date
    FROM refined_causal_chain_insights
    WHERE prompt_version = :pv AND macro_event IS NOT NULL
    ORDER BY sector_slug, reference_date DESC NULLS LAST, id DESC
    """
)

_INSERT_GOLD = text(
    """
    INSERT INTO causal_chains
        (sector_slug, macro_event, industry_impact, youth_chance, published_date)
    VALUES (:sector_slug, :macro_event, :industry_impact, :youth_chance, :published_date)
    """
)

_FETCH_CHAINS = text(
    """
    SELECT c.sector_slug, s.name_ko, s.accent_color,
           c.macro_event, c.industry_impact, c.youth_chance, c.published_date
    FROM causal_chains c
    JOIN sectors s ON s.slug = c.sector_slug
    WHERE c.is_active = true
    ORDER BY c.published_date DESC NULLS LAST, c.id DESC
    """
)


class CausalChainRepository(BaseRepository):
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
        await self.session.execute(_UPSERT_SILVER, payload)

    async def project_to_gold(self, prompt_version: str) -> int:
        """유효 인과사슬 Silver → causal_chains 멱등 재생성(섹터×최신 1개). 적재 수 반환."""
        await self.session.execute(_CLEAR_GOLD)
        rows = (await self.session.execute(_FETCH_SILVER_FOR_GOLD, {"pv": prompt_version})).all()
        n = 0
        for r in rows:
            await self.session.execute(
                _INSERT_GOLD,
                {
                    "sector_slug": r.sector_slug,
                    "macro_event": r.macro_event,
                    "industry_impact": r.industry_impact,
                    "youth_chance": r.youth_chance,
                    "published_date": r.reference_date,
                },
            )
            n += 1
        return n

    async def fetch_chains(self) -> list[dict]:
        rows = (await self.session.execute(_FETCH_CHAINS)).all()
        return [
            {
                "sector_slug": r.sector_slug,
                "sector_name": r.name_ko,
                "accent_color": r.accent_color,
                "macro_event": r.macro_event,
                "industry_impact": r.industry_impact,
                "youth_chance": r.youth_chance,
                "published_date": r.published_date.isoformat() if r.published_date else None,
            }
            for r in rows
        ]
