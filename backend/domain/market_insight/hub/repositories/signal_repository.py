# 엔티티·키워드 추출 신호(refined_innovation_signal)와 N:M 리니지 적재 리포지토리

from __future__ import annotations

import json

from sqlalchemy import text

from domain.auth.hub.repositories.base_repository import BaseRepository

# 이미 섹터 분류된(refined_text_sector_class) economic 행 중 아직 추출 안 된 행.
# refined_signal_sources 에 (raw_table_ref, raw_id) 링크가 없으면 미추출.
_FETCH_UNEXTRACTED_ECONOMIC = text(
    """
    SELECT DISTINCT ON (c.raw_id)
           c.raw_id AS raw_id, c.sector_slug AS sector_slug,
           e.raw_title || E'\n' ||
           COALESCE(e.raw_metadata->>'content_text', e.raw_metadata->>'body_text',
                    e.raw_metadata->>'summary', '') AS body,
           COALESCE(e.published_at::date, e.collected_at::date) AS ref_date
    FROM refined_text_sector_class c
    JOIN raw_economic_data e ON e.id = c.raw_id
    LEFT JOIN refined_signal_sources ss
           ON ss.raw_table_ref = 'raw_economic_data' AND ss.raw_id = c.raw_id
    WHERE c.raw_table_ref = 'raw_economic_data'
      AND c.sector_slug IS NOT NULL
      AND c.confidence >= :conf_min
      AND ss.id IS NULL
      AND COALESCE(e.published_at::date, e.collected_at::date) >= CURRENT_DATE - CAST(:win AS INTEGER)
    ORDER BY c.raw_id, c.confidence DESC
    LIMIT :lim
    """
)

_FETCH_UNEXTRACTED_DISCOURSE = text(
    """
    SELECT DISTINCT ON (c.raw_id)
           c.raw_id AS raw_id, c.sector_slug AS sector_slug,
           d.headline || E'\n' || COALESCE(d.content_body, '') AS body,
           COALESCE(d.published_at::date, d.collected_at::date) AS ref_date
    FROM refined_text_sector_class c
    JOIN raw_discourse_data d ON d.id = c.raw_id
    LEFT JOIN refined_signal_sources ss
           ON ss.raw_table_ref = 'raw_discourse_data' AND ss.raw_id = c.raw_id
    WHERE c.raw_table_ref = 'raw_discourse_data'
      AND c.sector_slug IS NOT NULL
      AND c.confidence >= :conf_min
      AND ss.id IS NULL
      AND COALESCE(d.published_at::date, d.collected_at::date) >= CURRENT_DATE - CAST(:win AS INTEGER)
    ORDER BY c.raw_id, c.confidence DESC
    LIMIT :lim
    """
)

# 자연키 충돌 시 기존 신호에 합류(source_count 증가) 후 id 반환.
_UPSERT_SIGNAL = text(
    """
    INSERT INTO refined_innovation_signal
        (sector_slug, data_role, signal_topic, confidence, extracted_keywords,
         reference_period_start, reference_period_end, source_count,
         model_name, prompt_version, input_hash)
    VALUES
        (:sector_slug, :data_role, :signal_topic, :confidence, CAST(:extracted_keywords AS JSONB),
         :ref_date, :ref_date, 1, :model_name, :prompt_version, :input_hash)
    ON CONFLICT (sector_slug, data_role, signal_topic, reference_period_start, reference_period_end)
    DO UPDATE SET source_count = refined_innovation_signal.source_count + 1
    RETURNING id
    """
)

_INSERT_SOURCE_LINK = text(
    """
    INSERT INTO refined_signal_sources (signal_id, raw_table_ref, raw_id, contribution_weight)
    VALUES (:signal_id, :raw_table_ref, :raw_id, :weight)
    ON CONFLICT (signal_id, raw_table_ref, raw_id) DO NOTHING
    """
)

# 트렌딩 키워드 — extracted_keywords 를 unnest 해 키워드별 신호 수(df)를 윈도우별 집계.
_KEYWORD_FREQ_RECENT = text(
    """
    SELECT kw, count(DISTINCT s.id) AS df
    FROM refined_innovation_signal s,
         LATERAL jsonb_array_elements_text(s.extracted_keywords) AS kw
    WHERE jsonb_typeof(s.extracted_keywords) = 'array'
      AND s.reference_period_end >= CURRENT_DATE - CAST(:win AS INTEGER)
      AND (CAST(:sector AS TEXT) IS NULL OR s.sector_slug = :sector)
    GROUP BY kw
    """
)

_KEYWORD_FREQ_PRIOR = text(
    """
    SELECT kw, count(DISTINCT s.id) AS df
    FROM refined_innovation_signal s,
         LATERAL jsonb_array_elements_text(s.extracted_keywords) AS kw
    WHERE jsonb_typeof(s.extracted_keywords) = 'array'
      AND s.reference_period_end >= CURRENT_DATE - CAST(:win2 AS INTEGER)
      AND s.reference_period_end <  CURRENT_DATE - CAST(:win AS INTEGER)
      AND (CAST(:sector AS TEXT) IS NULL OR s.sector_slug = :sector)
    GROUP BY kw
    """
)


class SignalRepository(BaseRepository):
    async def fetch_unextracted_rows(
        self, table_ref: str, conf_min: float, window_days: int, limit: int
    ) -> list[tuple]:
        """분류됐으나 아직 추출 안 된 행을 (raw_id, sector_slug, body, ref_date)로 반환한다."""
        sql = (
            _FETCH_UNEXTRACTED_ECONOMIC
            if table_ref == "raw_economic_data"
            else _FETCH_UNEXTRACTED_DISCOURSE
        )
        rows = (
            await self.session.execute(
                sql, {"conf_min": conf_min, "win": window_days, "lim": limit}
            )
        ).all()
        return [(r.raw_id, r.sector_slug, r.body, r.ref_date) for r in rows]

    async def upsert_signal(self, payload: dict) -> int:
        """신호를 멱등 upsert 하고 signal id 를 반환한다. payload.extracted_keywords 는 list."""
        params = dict(payload)
        params["extracted_keywords"] = json.dumps(payload.get("extracted_keywords") or [])
        return int((await self.session.execute(_UPSERT_SIGNAL, params)).scalar_one())

    async def insert_source_link(
        self, signal_id: int, raw_table_ref: str, raw_id: int, weight: float
    ) -> None:
        """신호↔원천 N:M 링크를 멱등 적재한다(중복 무시)."""
        await self.session.execute(
            _INSERT_SOURCE_LINK,
            {"signal_id": signal_id, "raw_table_ref": raw_table_ref, "raw_id": raw_id, "weight": weight},
        )

    async def fetch_keyword_freqs(
        self, window_days: int, sector: str | None
    ) -> tuple[dict[str, int], dict[str, int]]:
        """recent/prior 윈도우의 키워드별 신호 수(df)를 (recent, prior) dict로 반환한다."""
        recent_rows = (
            await self.session.execute(
                _KEYWORD_FREQ_RECENT, {"win": window_days, "sector": sector}
            )
        ).all()
        prior_rows = (
            await self.session.execute(
                _KEYWORD_FREQ_PRIOR,
                {"win": window_days, "win2": window_days * 2, "sector": sector},
            )
        ).all()
        recent = {r.kw: int(r.df) for r in recent_rows}
        prior = {r.kw: int(r.df) for r in prior_rows}
        return recent, prior
