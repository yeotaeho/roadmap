"""Pulse 리포지토리 — raw 혁신신호 섹터 집계, Silver/Gold 멱등 재기록, Gold 서빙 조회."""

from __future__ import annotations

from datetime import date

from sqlalchemy import text

from domain.auth.hub.repositories.base_repository import BaseRepository
from domain.market_insight.hub.services.pulse_pipeline import (
    AxisSignal,
    PulseGoldRow,
    PulseSilverRow,
)

# economic industry_sector/group_name·people HRDNET sector_name 코드 → sectors.slug.
# 산업 섹터가 아닌 신호유형 코드(CAPITAL_MARKET·SME_STARTUP·GOV_SUPPORT·STARTUP_VC·
# CAREER_SWITCH·CAPITAL_FLOW)는 의도적으로 제외한다(섹터 강제 매핑 = 날조).
_SECTOR_CODE_MAP: dict[str, str] = {
    "AI_ML": "ai-data", "AI_TECH": "ai-data", "ICT_SW": "ai-data", "DATA": "ai-data",
    "SEMICONDUCTOR": "semiconductor", "ICT_HW": "semiconductor",
    "BIOHEALTH": "bio-health", "BIO": "bio-health", "HEALTH": "bio-health",
    "ENERGY_CLIMATE": "energy-climate", "CLIMATE_ENERGY": "energy-climate", "BATTERY": "energy-climate",
    "MOBILITY": "mobility",
    "FINTECH": "fintech",
    "CONTENT_MEDIA": "content-creator", "CULTURE_ARTS": "content-creator", "DESIGN": "content-creator",
    "EDUTECH": "edutech", "EDUCATION": "edutech",
    "FOODTECH": "food-agri", "FOOD": "food-agri",
    "SOCIAL_WELFARE": "social-service",
    "LOGISTICS": "logistics",
    "BEAUTY": "beauty-fashion",
}

# raw_innovation_data → sector_source_map 으로 섹터 매핑 후 (섹터×수집일) 신호 건수 집계.
# reference_date 는 collected_at::date (Pulse = 관측된 신호 흐름; 논문 발행일 노이즈 회피).
# 섹터 분류 필드가 없는 KIAT_TECH_DEMAND·KISTEP 은 제외된다.
_INNOVATION_SIGNAL_SQL = text(
    """
    WITH mapped AS (
        SELECT r.id AS rid, m.sector_slug, r.collected_at::date AS ref_date
        FROM raw_innovation_data r
        JOIN sector_source_map m
          ON m.match_key = 'arxiv_category'
         AND m.match_value = r.raw_metadata->>'category'
        WHERE r.source_type = 'INNOVATION_ARXIV_KR'
        UNION ALL
        SELECT r.id, m.sector_slug, r.collected_at::date
        FROM raw_innovation_data r
        JOIN sector_source_map m
          ON m.match_key = 'customs_group'
         AND m.match_value = r.raw_metadata->>'group_name'
        WHERE r.source_type = 'INNOVATION_CUSTOMS_EXPORT'
        UNION ALL
        SELECT r.id, m.sector_slug, r.collected_at::date
        FROM raw_innovation_data r
        JOIN sector_source_map m
          ON m.match_key = 'tech_category'
         AND m.match_value = r.raw_metadata->>'tech_category'
        WHERE r.source_type = 'INNOVATION_TECHBLOG_KR'
        UNION ALL
        SELECT r.id, m.sector_slug, r.collected_at::date
        FROM raw_innovation_data r
        JOIN LATERAL jsonb_array_elements_text(r.raw_metadata->'topics') AS t(topic) ON true
        JOIN sector_source_map m
          ON m.match_key = 'github_topic'
         AND m.match_value = t.topic
        WHERE r.source_type = 'INNOVATION_GITHUB_TRENDING'
          AND jsonb_typeof(r.raw_metadata->'topics') = 'array'
    )
    SELECT sector_slug, ref_date, COUNT(DISTINCT rid) AS signal_count
    FROM mapped
    GROUP BY sector_slug, ref_date
    ORDER BY sector_slug, ref_date
    """
)

# economic 축: industry_sector(우선)·group_name 코드별 (코드×수집일) 건수. 코드→슬러그는 파이썬에서.
_ECONOMIC_AXIS_SQL = text(
    """
    SELECT COALESCE(raw_metadata->>'industry_sector', raw_metadata->>'group_name') AS code,
           collected_at::date AS ref_date,
           COUNT(*) AS c
    FROM raw_economic_data
    WHERE (raw_metadata ? 'industry_sector' OR raw_metadata ? 'group_name')
    GROUP BY 1, 2
    """
)

# people 축: HRDNET 훈련수요의 sector_name(산업 분류) 코드별 (코드×기준월) 건수.
_PEOPLE_AXIS_SQL = text(
    """
    SELECT raw_metadata->>'sector_name' AS code,
           reference_date AS ref_date,
           COUNT(*) AS c
    FROM raw_people_data
    WHERE source_type = 'PEOPLE_HRDNET_TRAINING'
      AND raw_metadata ? 'sector_name'
      AND reference_date IS NOT NULL
    GROUP BY 1, 2
    """
)

_INSERT_SILVER = text(
    """
    INSERT INTO refined_pulse_metric_silver
        (sector_slug, sub_sector_id, reference_date, raw_signal_value,
         normalized_score, momentum_pct, status_badge, window_days, baseline_method)
    VALUES
        (:sector_slug, :sub_sector_id, :reference_date, :raw_signal_value,
         :normalized_score, :momentum_pct, :status_badge, :window_days, :baseline_method)
    """
)

_INSERT_GOLD = text(
    """
    INSERT INTO pulse_metrics_log
        (sector_slug, sub_sector_id, recorded_date, score, status_badge, momentum_pct)
    VALUES
        (:sector_slug, :sub_sector_id, :recorded_date, :score, :status_badge, :momentum_pct)
    """
)

# 섹터별 최신 일자 1행 + 섹터 메타. Pulse 탭 서빙 쿼리.
_LATEST_GOLD_SQL = text(
    """
    SELECT DISTINCT ON (g.sector_slug)
        g.sector_slug, s.name_ko, s.accent_color,
        g.recorded_date, g.score, g.status_badge, g.momentum_pct
    FROM pulse_metrics_log g
    JOIN sectors s ON s.slug = g.sector_slug
    ORDER BY g.sector_slug, g.recorded_date DESC
    """
)


class PulseRepository(BaseRepository):
    async def fetch_axis_signals(self) -> list[AxisSignal]:
        """innovation·economic·people 3축을 섹터×일자 신호로 집계한다(가중 융합 입력)."""
        out: list[AxisSignal] = []

        for r in (await self.session.execute(_INNOVATION_SIGNAL_SQL)).all():
            out.append(AxisSignal(r.sector_slug, r.ref_date, "innovation", float(r.signal_count)))

        for r in (await self.session.execute(_ECONOMIC_AXIS_SQL)).all():
            slug = _SECTOR_CODE_MAP.get((r.code or "").upper())
            if slug:
                out.append(AxisSignal(slug, r.ref_date, "economic", float(r.c)))

        for r in (await self.session.execute(_PEOPLE_AXIS_SQL)).all():
            slug = _SECTOR_CODE_MAP.get((r.code or "").upper())
            if slug:
                out.append(AxisSignal(slug, r.ref_date, "people", float(r.c)))

        return out

    async def replace_silver(self, rows: list[PulseSilverRow], baseline_method: str) -> int:
        """해당 baseline_method 의 Silver 를 통째로 재기록한다(멱등)."""
        await self.session.execute(
            text("DELETE FROM refined_pulse_metric_silver WHERE baseline_method = :m"),
            {"m": baseline_method},
        )
        if not rows:
            return 0
        payload = [
            {
                "sector_slug": r.sector_slug,
                "sub_sector_id": None,
                "reference_date": r.reference_date,
                "raw_signal_value": r.raw_signal_value,
                "normalized_score": r.normalized_score,
                "momentum_pct": r.momentum_pct,
                "status_badge": r.status_badge,
                "window_days": r.window_days,
                "baseline_method": r.baseline_method,
            }
            for r in rows
        ]
        await self.session.execute(_INSERT_SILVER, payload)
        return len(payload)

    async def replace_gold(self, rows: list[PulseGoldRow]) -> int:
        """Pulse Gold 를 통째로 재생성한다(읽기 전용 서빙 테이블, 멱등)."""
        await self.session.execute(text("DELETE FROM pulse_metrics_log"))
        if not rows:
            return 0
        payload = [
            {
                "sector_slug": r.sector_slug,
                "sub_sector_id": None,
                "recorded_date": r.recorded_date,
                "score": r.score,
                "status_badge": r.status_badge,
                "momentum_pct": r.momentum_pct,
            }
            for r in rows
        ]
        await self.session.execute(_INSERT_GOLD, payload)
        return len(payload)

    async def fetch_latest_gold(self) -> list[dict]:
        """섹터별 최신 Pulse 점수 1행씩 (점수 내림차순)."""
        rows = (await self.session.execute(_LATEST_GOLD_SQL)).all()
        result = [
            {
                "sector_slug": r.sector_slug,
                "sector_name": r.name_ko,
                "accent_color": r.accent_color,
                "recorded_date": r.recorded_date.isoformat() if isinstance(r.recorded_date, date) else r.recorded_date,
                "score": r.score,
                "status_badge": r.status_badge,
                "momentum_pct": float(r.momentum_pct) if r.momentum_pct is not None else None,
            }
            for r in rows
        ]
        result.sort(key=lambda x: x["score"], reverse=True)
        return result
