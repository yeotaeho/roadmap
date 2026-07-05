# 코치 tool 전용 Gold 조회 — 토큰 절약형 축약 반환(read-only)

from __future__ import annotations

from sqlalchemy import text

from domain.auth.hub.repositories.base_repository import BaseRepository

_PULSE_LATEST = text(
    "SELECT DISTINCT ON (sector_slug) sector_slug, score, momentum_pct, status_badge, recorded_date "
    "FROM pulse_metrics_log "
    "WHERE (CAST(:sector AS varchar) IS NULL OR sector_slug = :sector) "
    "ORDER BY sector_slug, recorded_date DESC"
)
_GAP_LIST = text(
    "SELECT id, sector_slug, problem_summary, chance_summary, published_date "
    "FROM gap_issues "
    "WHERE is_active = true AND (CAST(:sector AS varchar) IS NULL OR sector_slug = :sector) "
    "ORDER BY published_date DESC LIMIT 8"
)
_GAP_DETAIL = text(
    "SELECT id, sector_slug, problem_summary, chance_summary, detail_summary, next_actions "
    "FROM gap_issues WHERE id = :iid"
)
_CHANCE_LIST = text(
    "SELECT o.id, o.sector_slug, o.title, o.opportunity_type, o.host_name, o.benefit_summary, "
    "       o.d_day_date, m.match_score, m.match_reason "
    "FROM chance_opportunities o "
    "LEFT JOIN user_chance_matches m ON m.opportunity_id = o.id AND m.user_id = CAST(:uid AS UUID) "
    "WHERE o.is_active = true AND (CAST(:otype AS varchar) IS NULL OR o.opportunity_type = :otype) "
    "ORDER BY m.match_score DESC NULLS LAST, o.d_day_date ASC NULLS LAST LIMIT 8"
)
_SYNC_LATEST = text(
    "SELECT DISTINCT ON (sector_slug) sector_slug, score, badge, explanation, recorded_date "
    "FROM sync_scores_daily WHERE user_id = CAST(:uid AS UUID) "
    "ORDER BY sector_slug, recorded_date DESC"
)
_DOC_SEARCH = text(
    "SELECT source_table, source_id, content_text, sector_slug, "
    "       (embedding <=> CAST(:vec AS halfvec(3072))) AS distance "
    "FROM document_embeddings "
    "WHERE (CAST(:sector AS varchar) IS NULL OR sector_slug = :sector) "
    "  AND created_at >= now() - interval '90 days' "
    "ORDER BY embedding <=> CAST(:vec AS halfvec(3072)) LIMIT 24"
)

_MAX_DISTANCE = 0.75  # cosine distance 컷 — 초과분은 잡음으로 간주.


class CoachInsightRepository(BaseRepository):
    async def pulse_trends(self, sector_slug: str | None) -> dict:
        rows = (await self.session.execute(_PULSE_LATEST, {"sector": sector_slug})).mappings().all()
        items = sorted(rows, key=lambda r: r["score"] or 0, reverse=True)
        return {
            "sectors": [
                {
                    "sector": r["sector_slug"],
                    "score": r["score"],
                    "momentumPct": float(r["momentum_pct"]) if r["momentum_pct"] is not None else None,
                    "badge": r["status_badge"],
                    "date": str(r["recorded_date"]),
                }
                for r in items
            ]
        }

    async def gap_issues(self, sector_slug: str | None, issue_id: int | None) -> dict:
        if issue_id is not None:
            row = (await self.session.execute(_GAP_DETAIL, {"iid": issue_id})).mappings().first()
            if row is None:
                return {"issue": None}
            return {
                "issue": {
                    "id": row["id"],
                    "sector": row["sector_slug"],
                    "problem": row["problem_summary"],
                    "chance": row["chance_summary"],
                    "detail": row["detail_summary"],
                    "nextActions": row["next_actions"],
                }
            }
        rows = (await self.session.execute(_GAP_LIST, {"sector": sector_slug})).mappings().all()
        return {
            "issues": [
                {
                    "id": r["id"],
                    "sector": r["sector_slug"],
                    "problem": r["problem_summary"],
                    "chance": r["chance_summary"],
                    "date": str(r["published_date"]),
                }
                for r in rows
            ]
        }

    async def chance_matches(self, user_id: str, opportunity_type: str | None) -> dict:
        rows = (
            await self.session.execute(_CHANCE_LIST, {"uid": user_id, "otype": opportunity_type})
        ).mappings().all()
        return {
            "opportunities": [
                {
                    "id": r["id"],
                    "sector": r["sector_slug"],
                    "title": r["title"],
                    "type": r["opportunity_type"],
                    "host": r["host_name"],
                    "benefit": r["benefit_summary"],
                    "dDay": str(r["d_day_date"]) if r["d_day_date"] else None,
                    "matchScore": r["match_score"],
                    "matchReason": r["match_reason"],
                }
                for r in rows
            ]
        }

    async def sync_snapshot(self, user_id: str) -> dict:
        rows = (await self.session.execute(_SYNC_LATEST, {"uid": user_id})).mappings().all()
        items = sorted(rows, key=lambda r: r["score"] or 0, reverse=True)
        return {
            "scores": [
                {"sector": r["sector_slug"], "score": r["score"], "badge": r["badge"], "why": r["explanation"]}
                for r in items
            ]
        }

    async def search_documents(self, query_vec: list[float], sector_slug: str | None) -> list[dict]:
        vec = "[" + ",".join(f"{v:.6f}" for v in query_vec) + "]"
        rows = (
            await self.session.execute(_DOC_SEARCH, {"vec": vec, "sector": sector_slug})
        ).mappings().all()
        seen: set[tuple] = set()
        out: list[dict] = []
        for r in rows:
            key = (r["source_table"], r["source_id"])
            if key in seen or (r["distance"] is not None and float(r["distance"]) > _MAX_DISTANCE):
                continue
            seen.add(key)
            out.append(
                {
                    "sourceTable": r["source_table"],
                    "sourceId": r["source_id"],
                    "sector": r["sector_slug"],
                    "text": (r["content_text"] or "")[:400],
                }
            )
            if len(out) >= 8:
                break
        return out
