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

# market 축: raw_market_timeseries.source_type → sectors.slug (실측 16티커 기준).
# 광범위 지수(SPY·QQQ·ARKK)는 단일섹터 무귀속이라 제외(섹터 강제 매핑 = 날조).
_MARKET_SOURCE_MAP: dict[str, str] = {
    "YAHOO_ETF_AI": "ai-data", "YAHOO_STOCK_KR_NAVER": "ai-data",
    "YAHOO_GLOBAL_SMH": "semiconductor", "YAHOO_STOCK_KR_HYNIX": "semiconductor",
    "YAHOO_STOCK_KR_SAMSUNG": "semiconductor",
    "YAHOO_ETF_BIO": "bio-health", "YAHOO_STOCK_KR_SBIO": "bio-health",
    "YAHOO_ETF_BATTERY": "energy-climate", "YAHOO_ETF_RENEWABLE": "energy-climate",
    "YAHOO_GLOBAL_LIT": "energy-climate", "YAHOO_GLOBAL_XLE": "energy-climate",
    "YAHOO_STOCK_KR_LGES": "energy-climate",
    "YAHOO_ETF_KFOOD": "food-agri",
}

# raw_innovation_data → sector_source_map 으로 섹터 매핑 후 (섹터×기준일) 신호 건수 집계.
# reference_date = COALESCE(published_at, collected_at)::date — 실제 발생일로 분산해
# 수집일(백필) 한 점에 신호가 몰려 모멘텀이 폭증하는 것을 방지. 분류 필드 없는 KIAT/KISTEP 제외.
_INNOVATION_SIGNAL_SQL = text(
    """
    WITH mapped AS (
        SELECT r.id AS rid, m.sector_slug, COALESCE(r.published_at::date, r.collected_at::date) AS ref_date
        FROM raw_innovation_data r
        JOIN sector_source_map m
          ON m.match_key = 'arxiv_category'
         AND m.match_value = r.raw_metadata->>'category'
        WHERE r.source_type = 'INNOVATION_ARXIV_KR'
        UNION ALL
        SELECT r.id, m.sector_slug, COALESCE(r.published_at::date, r.collected_at::date)
        FROM raw_innovation_data r
        JOIN sector_source_map m
          ON m.match_key = 'customs_group'
         AND m.match_value = r.raw_metadata->>'group_name'
        WHERE r.source_type = 'INNOVATION_CUSTOMS_EXPORT'
        UNION ALL
        SELECT r.id, m.sector_slug, COALESCE(r.published_at::date, r.collected_at::date)
        FROM raw_innovation_data r
        JOIN sector_source_map m
          ON m.match_key = 'tech_category'
         AND m.match_value = r.raw_metadata->>'tech_category'
        WHERE r.source_type = 'INNOVATION_TECHBLOG_KR'
        UNION ALL
        SELECT r.id, m.sector_slug, COALESCE(r.published_at::date, r.collected_at::date)
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
           COALESCE(published_at::date, collected_at::date) AS ref_date,
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

# market 축: 자본 흐름(거래대금). 혼합통화(USD ETF + KRW 주식) 합산 오류를 피하려
# 티커별 '상대 유량'(당일 거래대금 ÷ 그 티커의 기간 평균)으로 통화 중립화 후 source_type×거래일로 방출.
# 같은 섹터의 다중 티커는 호출측(_add)에서 합산된다.
_MARKET_AXIS_SQL = text(
    """
    WITH t AS (
        SELECT source_type,
               trade_date,
               COALESCE(turnover_amount, volume * close_price) AS tv,
               AVG(COALESCE(turnover_amount, volume * close_price))
                   OVER (PARTITION BY source_type) AS avg_tv
        FROM raw_market_timeseries
    )
    SELECT source_type,
           trade_date AS ref_date,
           AVG(tv / NULLIF(avg_tv, 0)) AS turnover
    FROM t
    GROUP BY source_type, trade_date
    """
)

# economic_text·discourse 축: raw 자유 텍스트의 LLM 섹터 분류(refined_text_sector_class)를
# (섹터×발생일) 건수로 집계. ref_date 는 원천 raw 테이블에서 가져온다(혁신축과 동일 분산).
# confidence/prompt_version 필터로 저신뢰·구버전 분류를 배제. sector_slug NULL(무귀속)은 제외.
_TEXT_SECTOR_AXIS_SQL = text(
    """
    SELECT 'economic_text' AS axis, c.sector_slug,
           COALESCE(e.published_at::date, e.collected_at::date) AS ref_date,
           COUNT(DISTINCT c.raw_id) AS c
    FROM refined_text_sector_class c
    JOIN raw_economic_data e ON e.id = c.raw_id
    WHERE c.raw_table_ref = 'raw_economic_data'
      AND c.prompt_version = :pv
      AND c.sector_slug IS NOT NULL
      AND c.confidence >= :conf_min
    GROUP BY c.sector_slug, ref_date
    UNION ALL
    SELECT 'discourse' AS axis, c.sector_slug,
           COALESCE(d.published_at::date, d.collected_at::date) AS ref_date,
           COUNT(DISTINCT c.raw_id) AS c
    FROM refined_text_sector_class c
    JOIN raw_discourse_data d ON d.id = c.raw_id
    WHERE c.raw_table_ref = 'raw_discourse_data'
      AND c.prompt_version = :pv
      AND c.sector_slug IS NOT NULL
      AND c.confidence >= :conf_min
    GROUP BY c.sector_slug, ref_date
    """
)

# 미분류 economic 행 조회. 이미 코드 매핑되는 행(industry_sector/group_name 보유)은 제외해
# 기존 economic 축과 행 단위 disjoint 를 보장(이중 집계 차단). 최근 window_days 일만 대상.
_FETCH_UNCLASSIFIED_ECONOMIC = text(
    """
    SELECT e.id AS raw_id,
           e.raw_title || E'\n' ||
           COALESCE(e.raw_metadata->>'content_text', e.raw_metadata->>'body_text',
                    e.raw_metadata->>'summary', '') AS body
    FROM raw_economic_data e
    LEFT JOIN refined_text_sector_class c
           ON c.raw_table_ref = 'raw_economic_data'
          AND c.raw_id = e.id
          AND c.prompt_version = :pv
    WHERE c.id IS NULL
      AND (e.raw_metadata ? 'industry_sector' OR e.raw_metadata ? 'group_name') IS NOT TRUE
      AND COALESCE(e.published_at::date, e.collected_at::date) >= CURRENT_DATE - CAST(:win AS INTEGER)
    ORDER BY e.id
    LIMIT :lim
    """
)

# 미분류 discourse 행 조회. discourse 는 현재 어느 축에도 없으므로 전 행이 대상.
_FETCH_UNCLASSIFIED_DISCOURSE = text(
    """
    SELECT d.id AS raw_id,
           d.headline || E'\n' || COALESCE(d.content_body, '') AS body
    FROM raw_discourse_data d
    LEFT JOIN refined_text_sector_class c
           ON c.raw_table_ref = 'raw_discourse_data'
          AND c.raw_id = d.id
          AND c.prompt_version = :pv
    WHERE c.id IS NULL
      AND COALESCE(d.published_at::date, d.collected_at::date) >= CURRENT_DATE - CAST(:win AS INTEGER)
    ORDER BY d.id
    LIMIT :lim
    """
)

_UPSERT_TEXT_SECTOR = text(
    """
    INSERT INTO refined_text_sector_class
        (raw_table_ref, raw_id, sector_slug, confidence, model_name, prompt_version, input_hash)
    VALUES
        (:raw_table_ref, :raw_id, :sector_slug, :confidence, :model_name, :prompt_version, :input_hash)
    ON CONFLICT (raw_table_ref, raw_id, prompt_version) DO NOTHING
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

# overview 월 버킷 평균 score 시계열.
_OVERVIEW_MONTHLY_SQL = text(
    """
    SELECT to_char(recorded_date, 'YYYY-MM') AS bucket, round(avg(score)) AS value
    FROM pulse_metrics_log
    WHERE recorded_date >= (CURRENT_DATE - make_interval(months => :months))
    GROUP BY 1
    ORDER BY 1
    """
)

# overview 섹터×ISO주 마지막 score(주별 최신 1행).
_OVERVIEW_WEEKLY_SQL = text(
    """
    SELECT DISTINCT ON (sector_slug, date_trunc('week', recorded_date))
        sector_slug,
        to_char(date_trunc('week', recorded_date), 'IYYY-"W"IW') AS bucket,
        score
    FROM pulse_metrics_log
    WHERE recorded_date >= (CURRENT_DATE - make_interval(weeks => :weeks))
    ORDER BY sector_slug, date_trunc('week', recorded_date), recorded_date DESC
    """
)

# overview 전 섹터 일평균 score 최근 2일(전일 대비 변동용).
_OVERVIEW_DAILY_AVG_SQL = text(
    """
    SELECT recorded_date, avg(score) AS avg_score
    FROM pulse_metrics_log
    GROUP BY recorded_date
    ORDER BY recorded_date DESC
    LIMIT 2
    """
)

# 단일 섹터 시계열(드릴다운).
_HISTORY_SQL = text(
    """
    SELECT recorded_date, score, status_badge, momentum_pct
    FROM pulse_metrics_log
    WHERE sector_slug = :slug
      AND recorded_date >= (CURRENT_DATE - make_interval(weeks => :weeks))
    ORDER BY recorded_date ASC
    """
)

# 섹터 메타(이름) 조회 — history 404 판별.
_SECTOR_NAME_SQL = text("SELECT name_ko FROM sectors WHERE slug = :slug")

# 크로스오버 — 전통/신흥 그룹별 월 평균 score 시계열(string_to_array로 asyncpg-safe).
_CROSSOVER_SQL = text(
    """
    SELECT to_char(recorded_date, 'YYYY-MM') AS bucket,
           round(avg(score) FILTER (WHERE sector_slug = ANY(string_to_array(:legacy_csv, ',')))) AS legacy_value,
           round(avg(score) FILTER (WHERE sector_slug = ANY(string_to_array(:emerging_csv, ',')))) AS emerging_value
    FROM pulse_metrics_log
    WHERE recorded_date >= (CURRENT_DATE - make_interval(months => :months))
      AND sector_slug = ANY(string_to_array(:legacy_csv || ',' || :emerging_csv, ','))
    GROUP BY 1
    ORDER BY 1
    """
)


def _normalize_axes(signals: list[AxisSignal]) -> list[AxisSignal]:
    """축별로 값을 0~100 양수 band로 min-max 정규화(이종 단위 통약).

    혁신 카운트(1~50)와 시장 거래대금(수십억)을 동등 비교 가능하게 만든다.
    모멘텀은 compute_silver의 윈도우 상대변화로 산출되므로, 정규화가 섹터의
    시간 변동(상대 추세)은 보존하면서 축간 스케일 격차만 제거한다. 단일/동일값
    축(span=0)은 50(중립)으로 둔다.
    """
    by_axis: dict[str, list[AxisSignal]] = {}
    for s in signals:
        by_axis.setdefault(s.axis, []).append(s)

    out: list[AxisSignal] = []
    for axis, items in by_axis.items():
        values = [s.value for s in items]
        lo, hi = min(values), max(values)
        span = hi - lo
        for s in items:
            norm = 50.0 if span == 0 else (s.value - lo) / span * 100.0
            out.append(AxisSignal(s.sector_slug, s.reference_date, axis, round(norm, 4)))
    return out


class PulseRepository(BaseRepository):
    async def fetch_axis_signals(
        self,
        text_confidence_min: float = 0.0,
        text_prompt_version: str | None = None,
    ) -> list[AxisSignal]:
        """축을 섹터×일자로 집계 후 축별 통약 정규화.

        기본 4축(innovation·economic·people·market)에 더해, text_prompt_version 이
        주어지면 LLM 분류 기반 economic_text·discourse 축을 합류시킨다.
        """
        # (sector, date, axis) → 합산값. 같은 섹터로 매핑되는 다중 코드/티커는 합산.
        agg: dict[tuple[str, object, str], float] = {}

        def _add(slug: str, ref_date: object, axis: str, value: float) -> None:
            agg[(slug, ref_date, axis)] = agg.get((slug, ref_date, axis), 0.0) + value

        for r in (await self.session.execute(_INNOVATION_SIGNAL_SQL)).all():
            _add(r.sector_slug, r.ref_date, "innovation", float(r.signal_count))

        for r in (await self.session.execute(_ECONOMIC_AXIS_SQL)).all():
            slug = _SECTOR_CODE_MAP.get((r.code or "").upper())
            if slug:
                _add(slug, r.ref_date, "economic", float(r.c))

        for r in (await self.session.execute(_PEOPLE_AXIS_SQL)).all():
            slug = _SECTOR_CODE_MAP.get((r.code or "").upper())
            if slug:
                _add(slug, r.ref_date, "people", float(r.c))

        for r in (await self.session.execute(_MARKET_AXIS_SQL)).all():
            slug = _MARKET_SOURCE_MAP.get(r.source_type)
            if slug and r.turnover is not None:
                _add(slug, r.ref_date, "market", float(r.turnover))

        # economic_text·discourse 축(LLM 분류) — prompt_version 지정 시에만 합류.
        if text_prompt_version is not None:
            for r in (
                await self.session.execute(
                    _TEXT_SECTOR_AXIS_SQL,
                    {"pv": text_prompt_version, "conf_min": text_confidence_min},
                )
            ).all():
                _add(r.sector_slug, r.ref_date, r.axis, float(r.c))

        raw = [AxisSignal(k[0], k[1], k[2], v) for k, v in agg.items()]
        return _normalize_axes(raw)

    async def fetch_unclassified_text_rows(
        self, table_ref: str, prompt_version: str, window_days: int, limit: int
    ) -> list[tuple[int, str]]:
        """최근 window_days 내 미분류 raw 행을 (raw_id, 입력 텍스트) 목록으로 반환한다."""
        sql = (
            _FETCH_UNCLASSIFIED_ECONOMIC
            if table_ref == "raw_economic_data"
            else _FETCH_UNCLASSIFIED_DISCOURSE
        )
        rows = (
            await self.session.execute(
                sql, {"pv": prompt_version, "win": window_days, "lim": limit}
            )
        ).all()
        return [(r.raw_id, r.body) for r in rows]

    async def upsert_text_sector_class(self, payload: list[dict]) -> int:
        """LLM 분류 결과를 멱등 적재(자연키 충돌 시 무시)한다. 적재 시도 건수를 반환한다."""
        if not payload:
            return 0
        await self.session.execute(_UPSERT_TEXT_SECTOR, payload)
        return len(payload)

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

    async def fetch_overview(self, heatmap_weeks: int = 8, momentum_months: int = 12) -> dict:
        """대시보드 overview 집계 — 최신/월/주/일평균 raw SQL → 순수 조립."""
        from domain.market_insight.hub.services.pulse_overview import assemble_overview

        latest_rows = (await self.session.execute(_LATEST_GOLD_SQL)).all()
        latest = [
            {
                "sector_slug": r.sector_slug,
                "sector_name": r.name_ko,
                "accent_color": r.accent_color,
                "score": r.score,
                "momentum_pct": float(r.momentum_pct) if r.momentum_pct is not None else None,
            }
            for r in latest_rows
        ]
        monthly = [
            {"bucket": r.bucket, "value": int(r.value)}
            for r in (await self.session.execute(_OVERVIEW_MONTHLY_SQL, {"months": momentum_months})).all()
        ]
        weekly = [
            {"sector_slug": r.sector_slug, "bucket": r.bucket, "score": r.score}
            for r in (await self.session.execute(_OVERVIEW_WEEKLY_SQL, {"weeks": heatmap_weeks})).all()
        ]
        daily_avgs = [
            {
                "recorded_date": r.recorded_date.isoformat(),
                "avg_score": float(r.avg_score) if r.avg_score is not None else None,
            }
            for r in (await self.session.execute(_OVERVIEW_DAILY_AVG_SQL)).all()
        ]
        return assemble_overview(latest, monthly, weekly, daily_avgs)

    async def fetch_history(self, sector_slug: str, weeks: int = 26) -> dict | None:
        """단일 섹터 Pulse 시계열(날짜 오름차순). 섹터 미존재 시 None."""
        name_row = (await self.session.execute(_SECTOR_NAME_SQL, {"slug": sector_slug})).first()
        if name_row is None:
            return None
        rows = (
            await self.session.execute(_HISTORY_SQL, {"slug": sector_slug, "weeks": weeks})
        ).all()
        points = [
            {
                "recorded_date": r.recorded_date.isoformat(),
                "score": r.score,
                "status_badge": r.status_badge,
                "momentum_pct": float(r.momentum_pct) if r.momentum_pct is not None else None,
            }
            for r in rows
        ]
        return {"sector_slug": sector_slug, "sector_name": name_row.name_ko, "points": points}

    async def fetch_crossover(self, months: int = 12) -> dict:
        """전통 vs 신흥 섹터 월 평균 score 시계열·교차점 즉석 집계."""
        from domain.market_insight.hub.services.crossover_metrics import (
            EMERGING_LABEL,
            EMERGING_SECTORS,
            LEGACY_LABEL,
            LEGACY_SECTORS,
            assemble_crossover,
        )

        rows = (
            await self.session.execute(
                _CROSSOVER_SQL,
                {
                    "legacy_csv": ",".join(LEGACY_SECTORS),
                    "emerging_csv": ",".join(EMERGING_SECTORS),
                    "months": months,
                },
            )
        ).all()
        data = [
            {
                "bucket": r.bucket,
                "legacy_value": int(r.legacy_value) if r.legacy_value is not None else None,
                "emerging_value": int(r.emerging_value) if r.emerging_value is not None else None,
            }
            for r in rows
        ]
        return assemble_crossover(data, LEGACY_LABEL, EMERGING_LABEL)
