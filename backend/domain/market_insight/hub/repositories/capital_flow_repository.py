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

# 섹터별 최신 완전연도 시장 총액(자금 기준선) — 커버리지 분모·자금 축 입력.
# 매핑된 여러 vcs_category 는 섹터 단위로 합산. 부분연도(집계 진행 중)는 제외.
_LATEST_BY_SECTOR = text(
    """
    WITH latest AS (
        SELECT MAX(period_year) AS y
        FROM market_sector_capital_flow
        WHERE is_partial = false AND sector_slug IS NOT NULL
    )
    SELECT f.sector_slug, SUM(f.amount_krw) AS market_total, (SELECT y FROM latest) AS period_year
    FROM market_sector_capital_flow f, latest
    WHERE f.sector_slug IS NOT NULL
      AND f.is_partial = false
      AND f.period_year = latest.y
    GROUP BY f.sector_slug
    """
)

# 단일 섹터 최신 완전연도 시장 총액.
_SECTOR_MARKET_TOTAL = text(
    """
    SELECT SUM(f.amount_krw) AS market_total, MAX(f.period_year) AS period_year
    FROM market_sector_capital_flow f
    WHERE f.sector_slug = :slug
      AND f.is_partial = false
      AND f.period_year = (
          SELECT MAX(period_year) FROM market_sector_capital_flow
          WHERE is_partial = false AND sector_slug IS NOT NULL
      )
    """
)


class CapitalFlowRepository(BaseRepository):
    async def upsert_many(self, rows: list[dict]) -> int:
        for r in rows:
            await self.session.execute(_UPSERT, r)
        await self.session.commit()
        return len(rows)

    async def fetch_latest_by_sector(self) -> dict[str, tuple[int, int]]:
        """{sector_slug: (market_total_krw, period_year)} — 자금 축 편입용."""
        result = (await self.session.execute(_LATEST_BY_SECTOR)).all()
        return {r.sector_slug: (int(r.market_total or 0), r.period_year) for r in result}

    async def fetch_sector_market_total(self, sector_slug: str) -> tuple[int, int] | None:
        """단일 섹터 (시장총액, 연도). 데이터 없으면 None."""
        row = (
            await self.session.execute(_SECTOR_MARKET_TOTAL, {"slug": sector_slug})
        ).first()
        if row is None or row.market_total is None:
            return None
        return int(row.market_total), row.period_year
