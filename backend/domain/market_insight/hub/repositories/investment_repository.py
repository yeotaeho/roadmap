# 투자 금액 추출 Silver 리포지토리 — 미처리 투자뉴스 조회·refined_investment_flows 적재

from __future__ import annotations

from sqlalchemy import text

from domain.auth.hub.repositories.base_repository import BaseRepository

# 미처리 투자/펀딩/M&A/IPO 성격의 economic 행(refined_investment_flows 없음).
#   토픽 태그(POLICY·CONTEST 등)는 제외해 LLM 호출을 아끼고, 나머지는 LLM abstain 으로 추가 필터.
_FETCH_UNPROCESSED = text(
    """
    SELECT o.id AS raw_id, o.raw_title AS title,
           o.target_company_or_fund AS company_hint,
           COALESCE(o.published_at::date, o.collected_at::date) AS ref_date
    FROM raw_economic_data o
    LEFT JOIN refined_investment_flows f
           ON f.raw_table_ref = 'raw_economic_data' AND f.raw_id = o.id
          AND f.prompt_version = :pv
    WHERE f.id IS NULL
      AND o.source_type ~ 'INVEST|FUND|_MA|_VC|IPO'
      AND COALESCE(o.published_at::date, o.collected_at::date) >= CURRENT_DATE - CAST(:win AS INTEGER)
    ORDER BY o.id
    LIMIT :lim
    """
)

# 멱등 적재 — 추출 실패(amount null)도 저장해 재호출을 막는다(raw_id/prompt_version 자연키).
_UPSERT_SILVER = text(
    """
    INSERT INTO refined_investment_flows
        (sector_slug, amount_krw, currency, series, company, reference_date,
         raw_table_ref, raw_id, model_name, prompt_version, input_hash)
    VALUES
        (NULL, :amount_krw, :currency, :series, :company, :ref_date,
         'raw_economic_data', :raw_id, :model_name, :prompt_version, :input_hash)
    ON CONFLICT (raw_table_ref, raw_id, prompt_version) DO NOTHING
    """
)


class InvestmentRepository(BaseRepository):
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
        await self.session.execute(_UPSERT_SILVER, payload)
