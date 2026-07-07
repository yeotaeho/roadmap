# 시장 자금 기준선 리포지토리 — vcs 업종별 총액 멱등 적재 + 섹터 커버리지·자금 축 조회

from __future__ import annotations

from sqlalchemy import text

from domain.auth.hub.repositories.base_repository import BaseRepository

# 멱등 적재 — vcs_category×period_year 자연키. 재수집 시 최신 수치·매핑으로 갱신.
_UPSERT = text(
    """
    INSERT INTO market_sector_capital_flow
        (vcs_category, sector_slug, period_year, period_label, amount_krw,
         is_total, is_partial, source_type)
    VALUES
        (:vcs_category, :sector_slug, :period_year, :period_label, :amount_krw,
         :is_total, :is_partial, :source_type)
    ON CONFLICT (vcs_category, period_year) DO UPDATE SET
        sector_slug = EXCLUDED.sector_slug,
        period_label = EXCLUDED.period_label,
        amount_krw = EXCLUDED.amount_krw,
        is_total = EXCLUDED.is_total,
        is_partial = EXCLUDED.is_partial,
        collected_at = now()
    """
)

class CapitalFlowRepository(BaseRepository):
    async def upsert_many(self, rows: list[dict]) -> int:
        for r in rows:
            await self.session.execute(_UPSERT, r)
        await self.session.commit()
        return len(rows)
