# economic_briefings 리포지토리 — 당일 맥락 수집, Gold 멱등 적재·서빙

from __future__ import annotations

from sqlalchemy import text

from domain.auth.hub.repositories.base_repository import BaseRepository

# 당일/최근 경제 헤드라인(LLM 입력).
_FETCH_ECON = text(
    """
    SELECT raw_title AS title
    FROM raw_economic_data
    WHERE COALESCE((published_at AT TIME ZONE 'Asia/Seoul')::date, (collected_at AT TIME ZONE 'Asia/Seoul')::date) >= (now() AT TIME ZONE 'Asia/Seoul')::date - 3
    ORDER BY COALESCE(published_at, collected_at) DESC NULLS LAST
    LIMIT :lim
    """
)

# 섹터별 최신 Pulse 모멘텀(top movers 후보) — |모멘텀| 정렬은 파이썬에서.
_FETCH_MOVERS = text(
    """
    SELECT DISTINCT ON (g.sector_slug) g.sector_slug, s.name_ko, g.momentum_pct
    FROM pulse_metrics_log g
    JOIN sectors s ON s.slug = g.sector_slug
    ORDER BY g.sector_slug, g.recorded_date DESC
    """
)

# 최근 기회 신호(LLM 입력 보강).
_FETCH_GAPS = text(
    """
    SELECT chance_summary
    FROM gap_issues
    WHERE is_active = true
    ORDER BY published_date DESC NULLS LAST, id DESC
    LIMIT :lim
    """
)

_TODAY_EXISTS = text(
    "SELECT 1 FROM economic_briefings WHERE published_date = (now() AT TIME ZONE 'Asia/Seoul')::date LIMIT 1"
)
_DELETE_TODAY = text("DELETE FROM economic_briefings WHERE published_date = (now() AT TIME ZONE 'Asia/Seoul')::date")
_INSERT_LINE = text(
    """
    INSERT INTO economic_briefings (published_date, line_number, content, trend_icon)
    VALUES ((now() AT TIME ZONE 'Asia/Seoul')::date, :ln, :content, :icon)
    """
)

# 서빙 — 최신일 3줄.
_FETCH_LATEST = text(
    """
    SELECT published_date, line_number, content, trend_icon
    FROM economic_briefings
    WHERE published_date = (SELECT max(published_date) FROM economic_briefings)
    ORDER BY line_number
    """
)


class BriefingRepository(BaseRepository):
    async def fetch_context(self, econ_limit: int, gap_limit: int) -> dict:
        """LLM/템플릿 입력 — 당일 경제 헤드라인·섹터 top movers·최근 기회."""
        econ = [
            {"title": r.title}
            for r in (await self.session.execute(_FETCH_ECON, {"lim": econ_limit})).all()
        ]
        mrows = (await self.session.execute(_FETCH_MOVERS)).all()
        movers = sorted(
            (
                {
                    "sector_slug": r.sector_slug,
                    "sector_name": r.name_ko,
                    "momentum_pct": float(r.momentum_pct) if r.momentum_pct is not None else None,
                }
                for r in mrows
            ),
            key=lambda m: abs(m["momentum_pct"]) if m["momentum_pct"] is not None else 0.0,
            reverse=True,
        )
        gaps = [
            {"chance_summary": r.chance_summary}
            for r in (await self.session.execute(_FETCH_GAPS, {"lim": gap_limit})).all()
        ]
        return {"econ": econ, "movers": movers, "gaps": gaps}

    async def today_exists(self) -> bool:
        return (await self.session.execute(_TODAY_EXISTS)).first() is not None

    async def upsert_gold(self, lines: list[dict]) -> None:
        """당일 브리핑을 멱등 재적재(당일 삭제 후 1~3줄 삽입)."""
        await self.session.execute(_DELETE_TODAY)
        for i, ln in enumerate(lines[:3], start=1):
            await self.session.execute(
                _INSERT_LINE,
                {"ln": i, "content": (ln["content"] or "")[:255], "icon": ln["trend_icon"]},
            )

    async def fetch_latest(self) -> dict:
        rows = (await self.session.execute(_FETCH_LATEST)).all()
        return {
            "published_date": rows[0].published_date.isoformat() if rows else None,
            "briefings": [
                {"line_number": r.line_number, "content": r.content, "trend_icon": r.trend_icon}
                for r in rows
            ],
        }
