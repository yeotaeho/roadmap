"""Pulse 리포지토리 — raw 혁신신호 섹터 집계, Silver/Gold 멱등 재기록, Gold 서빙 조회."""

from __future__ import annotations

from datetime import date

from sqlalchemy import text

from domain.auth.hub.repositories.base_repository import BaseRepository
from domain.market_insight.hub.services.pulse_pipeline import (
    AxisSignal,
    PulseGoldRow,
    PulseSilverRow,
    center_text_sentiment,
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

# market 축: raw_market_timeseries.source_type → sectors.slug.
# 광범위 지수(SPY·QQQ·ARKK)는 단일섹터 무귀속이라 제외(섹터 강제 매핑 = 날조).
# 2026-06-28: 미달 6섹터(핀테크·모빌리티·콘텐츠·에듀테크·물류·뷰티패션) 시장축 티커 추가
# (yahoo_finance_collector._UNDERCOVERED_TARGETS 의 source_type 과 1:1 대응).
_MARKET_SOURCE_MAP: dict[str, str] = {
    "YAHOO_ETF_AI": "ai-data", "YAHOO_STOCK_KR_NAVER": "ai-data",
    "YAHOO_GLOBAL_SMH": "semiconductor", "YAHOO_STOCK_KR_HYNIX": "semiconductor",
    "YAHOO_STOCK_KR_SAMSUNG": "semiconductor",
    "YAHOO_ETF_BIO": "bio-health", "YAHOO_STOCK_KR_SBIO": "bio-health",
    "YAHOO_ETF_BATTERY": "energy-climate", "YAHOO_ETF_RENEWABLE": "energy-climate",
    "YAHOO_GLOBAL_LIT": "energy-climate", "YAHOO_GLOBAL_XLE": "energy-climate",
    "YAHOO_STOCK_KR_LGES": "energy-climate",
    "YAHOO_ETF_KFOOD": "food-agri",
    # 핀테크·금융
    "YAHOO_STOCK_KR_KAKAOPAY": "fintech", "YAHOO_STOCK_KR_KAKAOBANK": "fintech",
    "YAHOO_GLOBAL_FINX": "fintech",
    # 모빌리티·자동차
    "YAHOO_STOCK_KR_HYUNDAIMOTOR": "mobility", "YAHOO_STOCK_KR_KIA": "mobility",
    "YAHOO_GLOBAL_KARS": "mobility",
    # 콘텐츠·크리에이터
    "YAHOO_ETF_WEBTOON": "content-creator", "YAHOO_ETF_KPOP": "content-creator",
    "YAHOO_GLOBAL_XLC": "content-creator",
    # 교육·에듀테크
    "YAHOO_STOCK_KR_MEGASTUDY": "edutech", "YAHOO_STOCK_KR_DIGITALDAESUNG": "edutech",
    # 물류·유통
    "YAHOO_ETF_TRANSPORT": "logistics", "YAHOO_STOCK_KR_CJLOGISTICS": "logistics",
    # 뷰티·패션
    "YAHOO_ETF_COSMETIC": "beauty-fashion", "YAHOO_ETF_KBEAUTY": "beauty-fashion",
    "YAHOO_STOCK_KR_FNF": "beauty-fashion",
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
    UNION ALL
    SELECT 'tech_demand' AS axis, c.sector_slug,
           COALESCE(r.published_at::date, r.collected_at::date) AS ref_date,
           COUNT(DISTINCT c.raw_id) AS c
    FROM refined_text_sector_class c
    JOIN raw_innovation_data r ON r.id = c.raw_id
    WHERE c.raw_table_ref = 'raw_innovation_data'
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

# 미분류 innovation 행(KIAT·KISTEP만). 나머지 innovation 소스는 sector_source_map 으로
# 이미 innovation 축에 있으므로 제외(이중집계 방지). KIAT 는 published_at 없어 collected_at 기준.
_FETCH_UNCLASSIFIED_INNOVATION = text(
    """
    SELECT r.id AS raw_id,
           r.title || E'\n' ||
           COALESCE(r.abstract_text, '') || E'\n' ||
           COALESCE(r.raw_metadata->>'keyword', '') AS body
    FROM raw_innovation_data r
    LEFT JOIN refined_text_sector_class c
           ON c.raw_table_ref = 'raw_innovation_data'
          AND c.raw_id = r.id
          AND c.prompt_version = :pv
    WHERE c.id IS NULL
      AND r.source_type IN ('INNOVATION_KIAT_TECH_DEMAND', 'INNOVATION_KISTEP_REPORT')
      AND COALESCE(r.published_at::date, r.collected_at::date) >= CURRENT_DATE - CAST(:win AS INTEGER)
    ORDER BY r.id
    LIMIT :lim
    """
)

# table_ref → 미분류 조회 SQL 매핑.
_FETCH_UNCLASSIFIED_BY_TABLE = {
    "raw_economic_data": _FETCH_UNCLASSIFIED_ECONOMIC,
    "raw_discourse_data": _FETCH_UNCLASSIFIED_DISCOURSE,
    "raw_innovation_data": _FETCH_UNCLASSIFIED_INNOVATION,
}

_UPSERT_TEXT_SECTOR = text(
    """
    INSERT INTO refined_text_sector_class
        (raw_table_ref, raw_id, sector_slug, confidence, sentiment, sentiment_score,
         model_name, prompt_version, input_hash)
    VALUES
        (:raw_table_ref, :raw_id, :sector_slug, :confidence, :sentiment, :sentiment_score,
         :model_name, :prompt_version, :input_hash)
    ON CONFLICT (raw_table_ref, raw_id, prompt_version) DO NOTHING
    """
)

# 방향성 modifier(텍스트 감성) — refined_text_sector_class 의 LLM 감성을 (섹터×발생일) 평균으로 집계.
# _TEXT_SECTOR_AXIS_SQL 과 동일 조인(economic·discourse·innovation)·필터를 쓰되 sentiment_score 평균을 낸다.
# sentiment_score NULL(구버전 분류분)은 제외 — 감성 없는 행은 tilt 에 기여하지 않는다.
_TEXT_SENTIMENT_SQL = text(
    """
    SELECT sector_slug, ref_date, AVG(sentiment_score) AS avg_sent, COUNT(*) AS n
    FROM (
        SELECT c.sector_slug AS sector_slug,
               COALESCE(e.published_at::date, e.collected_at::date) AS ref_date,
               c.sentiment_score AS sentiment_score
        FROM refined_text_sector_class c
        JOIN raw_economic_data e ON e.id = c.raw_id
        WHERE c.raw_table_ref = 'raw_economic_data'
          AND c.prompt_version = :pv
          AND c.sector_slug IS NOT NULL
          AND c.confidence >= :conf_min
          AND c.sentiment_score IS NOT NULL
        UNION ALL
        SELECT c.sector_slug,
               COALESCE(d.published_at::date, d.collected_at::date),
               c.sentiment_score
        FROM refined_text_sector_class c
        JOIN raw_discourse_data d ON d.id = c.raw_id
        WHERE c.raw_table_ref = 'raw_discourse_data'
          AND c.prompt_version = :pv
          AND c.sector_slug IS NOT NULL
          AND c.confidence >= :conf_min
          AND c.sentiment_score IS NOT NULL
        UNION ALL
        SELECT c.sector_slug,
               COALESCE(r.published_at::date, r.collected_at::date),
               c.sentiment_score
        FROM refined_text_sector_class c
        JOIN raw_innovation_data r ON r.id = c.raw_id
        WHERE c.raw_table_ref = 'raw_innovation_data'
          AND c.prompt_version = :pv
          AND c.sector_slug IS NOT NULL
          AND c.confidence >= :conf_min
          AND c.sentiment_score IS NOT NULL
    ) s
    GROUP BY sector_slug, ref_date
    """
)

# 방향성 modifier(시장 방향) — 전일 종가 대비 등락 부호. LAG 로 직전 거래일 종가를 끌어온다.
# 0.2% 데드밴드(보합)로 미세 변동 노이즈를 제거. source_type→섹터 매핑·turnover 가중은 호출측에서.
_MARKET_DIRECTION_SQL = text(
    """
    WITH d AS (
        SELECT source_type,
               trade_date,
               close_price,
               LAG(close_price) OVER (PARTITION BY source_type ORDER BY trade_date) AS prev_close,
               COALESCE(turnover_amount, volume * close_price) AS tv
        FROM raw_market_timeseries
    )
    SELECT source_type,
           trade_date AS ref_date,
           CASE WHEN close_price > prev_close * 1.002 THEN 1
                WHEN close_price < prev_close * 0.998 THEN -1
                ELSE 0 END AS dir,
           tv
    FROM d
    WHERE prev_close IS NOT NULL AND prev_close > 0
    """
)

# 감성 백필 — 이미 분류됐으나 sentiment NULL 인 행(구버전 분류분)을 (class_id, 입력 텍스트)로 조회.
# 분류는 보존하고 감성만 LLM 재추출해 채운다. 입력 텍스트 구성은 _FETCH_UNCLASSIFIED_* 와 동일.
_FETCH_SENTIMENT_BACKFILL_ECONOMIC = text(
    """
    SELECT c.id AS class_id,
           e.raw_title || E'\n' ||
           COALESCE(e.raw_metadata->>'content_text', e.raw_metadata->>'body_text',
                    e.raw_metadata->>'summary', '') AS body
    FROM refined_text_sector_class c
    JOIN raw_economic_data e ON e.id = c.raw_id
    WHERE c.raw_table_ref = 'raw_economic_data'
      AND c.prompt_version = :pv
      AND c.sentiment IS NULL
      AND COALESCE(e.published_at::date, e.collected_at::date) >= CURRENT_DATE - CAST(:win AS INTEGER)
    ORDER BY c.id
    LIMIT :lim
    """
)
_FETCH_SENTIMENT_BACKFILL_DISCOURSE = text(
    """
    SELECT c.id AS class_id,
           d.headline || E'\n' || COALESCE(d.content_body, '') AS body
    FROM refined_text_sector_class c
    JOIN raw_discourse_data d ON d.id = c.raw_id
    WHERE c.raw_table_ref = 'raw_discourse_data'
      AND c.prompt_version = :pv
      AND c.sentiment IS NULL
      AND COALESCE(d.published_at::date, d.collected_at::date) >= CURRENT_DATE - CAST(:win AS INTEGER)
    ORDER BY c.id
    LIMIT :lim
    """
)
_FETCH_SENTIMENT_BACKFILL_INNOVATION = text(
    """
    SELECT c.id AS class_id,
           r.title || E'\n' ||
           COALESCE(r.abstract_text, '') || E'\n' ||
           COALESCE(r.raw_metadata->>'keyword', '') AS body
    FROM refined_text_sector_class c
    JOIN raw_innovation_data r ON r.id = c.raw_id
    WHERE c.raw_table_ref = 'raw_innovation_data'
      AND c.prompt_version = :pv
      AND c.sentiment IS NULL
      AND COALESCE(r.published_at::date, r.collected_at::date) >= CURRENT_DATE - CAST(:win AS INTEGER)
    ORDER BY c.id
    LIMIT :lim
    """
)
_FETCH_SENTIMENT_BACKFILL_BY_TABLE = {
    "raw_economic_data": _FETCH_SENTIMENT_BACKFILL_ECONOMIC,
    "raw_discourse_data": _FETCH_SENTIMENT_BACKFILL_DISCOURSE,
    "raw_innovation_data": _FETCH_SENTIMENT_BACKFILL_INNOVATION,
}

_UPDATE_SENTIMENT = text(
    """
    UPDATE refined_text_sector_class
    SET sentiment = :sentiment, sentiment_score = :sentiment_score
    WHERE id = :class_id
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

# 섹터 투자·자금 흐름(드릴다운) — 두 경로의 UNION(소스타입 disjoint 라 이중집계 없음).
#   ① 투자 뉴스 LLM 추출분(:invest_pv) — 텍스트 섹터 분류(c)로 귀속.
#   ② DART CB·M&A 보강분(:dart_pv) — 기업개황 KSIC 매핑으로 f.sector_slug 직접 귀속.
# 보조금·사업보고서·박스오피스 등 비투자성 금액은 원천에서 제외됨.
_INVESTMENTS_LIST_SQL = text(
    """
    SELECT company, amount_krw, flow_label, ref_date, investor_name, raw_title, source_url
    FROM (
        SELECT COALESCE(f.company, e.target_company_or_fund) AS company,
               f.amount_krw AS amount_krw,
               COALESCE(f.series, '투자유치') AS flow_label,
               COALESCE(f.reference_date, e.published_at::date, e.collected_at::date) AS ref_date,
               -- 뉴스류 investor_name 은 수집기가 제목 조각을 넣어 신뢰 불가 → 비움.
               NULL AS investor_name, e.raw_title, e.source_url
        FROM refined_investment_flows f
        JOIN refined_text_sector_class c
          ON c.raw_table_ref = f.raw_table_ref AND c.raw_id = f.raw_id
         AND c.prompt_version = :text_pv AND c.confidence >= :conf_min
        JOIN raw_economic_data e ON e.id = f.raw_id
        WHERE f.amount_krw IS NOT NULL
          AND f.prompt_version = :invest_pv
          AND c.sector_slug = :slug
        UNION ALL
        SELECT f.company,
               f.amount_krw,
               COALESCE(f.series, '자금조달'),
               COALESCE(f.reference_date, e.published_at::date, e.collected_at::date),
               -- M&A 는 공시 제출인(인수 주체)이 투자자 성격, CB 는 발행사 자신이라 비움.
               CASE WHEN e.target_company_or_fund IS NOT NULL THEN e.investor_name END,
               e.raw_title, e.source_url
        FROM refined_investment_flows f
        JOIN raw_economic_data e ON e.id = f.raw_id
        WHERE f.amount_krw IS NOT NULL
          AND f.prompt_version = :dart_pv
          AND f.sector_slug = :slug
    ) t
    ORDER BY ref_date DESC NULLS LAST
    LIMIT :limit
    """
)

# 요약 집계는 목록 LIMIT 과 분리 — 윈도우 전체를 SQL 에서 합산해 행 수와 무관하게 정확.
_INVESTMENTS_SUMMARY_SQL = text(
    """
    SELECT COUNT(*) FILTER (WHERE ref_date >= :recent_from) AS recent_count,
           COALESCE(SUM(amount_krw) FILTER (WHERE ref_date >= :recent_from), 0) AS recent_total,
           COUNT(*) FILTER (WHERE ref_date >= :prev_from AND ref_date < :recent_from) AS prev_count,
           COALESCE(SUM(amount_krw) FILTER (WHERE ref_date >= :prev_from AND ref_date < :recent_from), 0) AS prev_total
    FROM (
        SELECT f.amount_krw AS amount_krw,
               COALESCE(f.reference_date, e.published_at::date, e.collected_at::date) AS ref_date
        FROM refined_investment_flows f
        JOIN refined_text_sector_class c
          ON c.raw_table_ref = f.raw_table_ref AND c.raw_id = f.raw_id
         AND c.prompt_version = :text_pv AND c.confidence >= :conf_min
        JOIN raw_economic_data e ON e.id = f.raw_id
        WHERE f.amount_krw IS NOT NULL
          AND f.prompt_version = :invest_pv
          AND c.sector_slug = :slug
        UNION ALL
        SELECT f.amount_krw,
               COALESCE(f.reference_date, e.published_at::date, e.collected_at::date)
        FROM refined_investment_flows f
        JOIN raw_economic_data e ON e.id = f.raw_id
        WHERE f.amount_krw IS NOT NULL
          AND f.prompt_version = :dart_pv
          AND f.sector_slug = :slug
    ) t
    WHERE ref_date IS NOT NULL
    """
)

# 섹터 관련 문서(드릴다운) — 텍스트 섹터 분류 리니지로 raw 3테이블 역참조.
# news = 공시·기사·담론(economic+discourse) / tech = 기술·R&D(innovation). 그룹별 최신 :limit 건.
# prompt_version/confidence 필터로 구버전·저신뢰 분류 배제(타 소비 쿼리와 동일 관례) — 버전 누적 시 중복·stale 방지.
_DOCUMENTS_SQL = text(
    """
    SELECT doc_group, title, url, source_type, published_at, sentiment
    FROM (
        SELECT
            CASE WHEN c.raw_table_ref = 'raw_innovation_data' THEN 'tech' ELSE 'news' END AS doc_group,
            COALESCE(e.raw_title, i.title, d.headline) AS title,
            COALESCE(e.source_url, i.source_url, d.source_url) AS url,
            COALESCE(e.source_type, i.source_type, d.source_type) AS source_type,
            COALESCE(e.published_at, i.published_at, d.published_at) AS published_at,
            c.sentiment,
            ROW_NUMBER() OVER (
                PARTITION BY CASE WHEN c.raw_table_ref = 'raw_innovation_data' THEN 'tech' ELSE 'news' END
                ORDER BY COALESCE(e.published_at, i.published_at, d.published_at) DESC NULLS LAST, c.id DESC
            ) AS rn
        FROM refined_text_sector_class c
        LEFT JOIN raw_economic_data e
               ON c.raw_table_ref = 'raw_economic_data' AND e.id = c.raw_id
        LEFT JOIN raw_innovation_data i
               ON c.raw_table_ref = 'raw_innovation_data' AND i.id = c.raw_id
        LEFT JOIN raw_discourse_data d
               ON c.raw_table_ref = 'raw_discourse_data' AND d.id = c.raw_id
        WHERE c.sector_slug = :slug
          AND c.raw_table_ref IN ('raw_economic_data', 'raw_innovation_data', 'raw_discourse_data')
          AND c.prompt_version = :pv
          AND c.confidence >= :conf_min
          AND COALESCE(e.raw_title, i.title, d.headline) IS NOT NULL
    ) t
    WHERE rn <= :limit
    ORDER BY doc_group, rn
    """
)

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


# 정규화 윈저화 분위수 — min/max 대신 5/95 퍼센타일을 band 경계로 써,
# 한 섹터의 단발 스파이크가 스케일을 장악해 타 섹터를 0 근처로 압축(노이즈 전이)하는 것을 막는다.
NORM_CLIP_Q = 0.05


def _percentile(sorted_vals: list[float], q: float) -> float:
    """정렬된 값 목록의 분위수(선형 보간). q in [0,1]. 순수 함수."""
    n = len(sorted_vals)
    if n == 0:
        return 0.0
    if n == 1:
        return sorted_vals[0]
    pos = q * (n - 1)
    lo_i = int(pos)
    if lo_i + 1 >= n:
        return sorted_vals[-1]
    return sorted_vals[lo_i] + (sorted_vals[lo_i + 1] - sorted_vals[lo_i]) * (pos - lo_i)


def _normalize_axes(signals: list[AxisSignal]) -> list[AxisSignal]:
    """축별로 값을 0~100 양수 band로 정규화(이종 단위 통약).

    혁신 카운트(1~50)와 시장 거래대금(수십억)을 동등 비교 가능하게 만든다.
    band 경계를 min/max가 아니라 5/95 퍼센타일로 잡아(윈저화) 단발 스파이크가
    스케일을 장악하지 못하게 하고, 경계 밖 값은 0/100 으로 클립한다. 모멘텀은
    compute_silver의 윈도우 상대변화로 산출되므로 시간 변동은 보존된다. 단일/동일값
    축(span=0)은 50(중립)으로 둔다.
    """
    by_axis: dict[str, list[AxisSignal]] = {}
    for s in signals:
        by_axis.setdefault(s.axis, []).append(s)

    out: list[AxisSignal] = []
    for axis, items in by_axis.items():
        values = sorted(s.value for s in items)
        lo = _percentile(values, NORM_CLIP_Q)
        hi = _percentile(values, 1.0 - NORM_CLIP_Q)
        span = hi - lo
        for s in items:
            if span == 0:
                norm = 50.0
            else:
                norm = max(0.0, min(100.0, (s.value - lo) / span * 100.0))
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

    async def fetch_directional_modifiers(
        self,
        text_confidence_min: float = 0.0,
        text_prompt_version: str | None = None,
        min_text_rows: int = 1,
        center_text: bool = True,
    ) -> dict[tuple[str, object], tuple[float, float, float, float]]:
        """(섹터, 발생일) → (감성 value, 감성 관측수, 시장 value, 시장 관측수) 를 반환한다.

        텍스트 감성과 시장 방향을 **축별로 분리**해 내보낸다. 결합·트레일링·shrinkage 는
        compute_silver 에서 축별로 따로 수행한 뒤 고정 축 가중으로 합쳐, 텍스트 행수가
        시장 티커수를 압도해도 시장 방향이 묻히지 않게 한다('둘 다 의미 있게'). 관측수는
        축별 shrinkage 입력 — 관측이 적은 축은 그 축 자체가 0 으로 수축한다. 한 축이 없으면
        그 축 관측수 0. text_prompt_version 이 None 이면 감성 축 제외. center_text 면 텍스트
        감성을 전체 평균 대비로 중심화해 LLM 양수 편향을 제거한다(상대 변별).
        """
        # 텍스트 감성 — (평균 감성, 행수).
        text_mod: dict[tuple[str, object], tuple[float, float]] = {}
        if text_prompt_version is not None:
            for r in (
                await self.session.execute(
                    _TEXT_SENTIMENT_SQL,
                    {"pv": text_prompt_version, "conf_min": text_confidence_min},
                )
            ).all():
                if r.avg_sent is not None and r.n >= min_text_rows:
                    text_mod[(r.sector_slug, r.ref_date)] = (float(r.avg_sent), float(r.n))
        if center_text:
            text_mod = center_text_sentiment(text_mod)

        # 시장 방향 — turnover 가중 등락 부호(value) + 티커 수(관측수).
        mkt_num: dict[tuple[str, object], float] = {}
        mkt_den: dict[tuple[str, object], float] = {}
        mkt_cnt: dict[tuple[str, object], float] = {}
        for r in (await self.session.execute(_MARKET_DIRECTION_SQL)).all():
            slug = _MARKET_SOURCE_MAP.get(r.source_type)
            if not slug or r.tv is None:
                continue
            key = (slug, r.ref_date)
            w = float(r.tv)
            mkt_num[key] = mkt_num.get(key, 0.0) + w * float(r.dir)
            mkt_den[key] = mkt_den.get(key, 0.0) + w
            mkt_cnt[key] = mkt_cnt.get(key, 0.0) + 1.0
        mkt_mod = {k: (mkt_num[k] / mkt_den[k], mkt_cnt[k]) for k in mkt_num if mkt_den[k] > 0}

        # 축별 값을 (감성 value, 감성 관측수, 시장 value, 시장 관측수) 로 병합(결합은 호출측).
        out: dict[tuple[str, object], tuple[float, float, float, float]] = {}
        for key in set(text_mod) | set(mkt_mod):
            tv, tw = text_mod.get(key, (0.0, 0.0))
            mv, mw = mkt_mod.get(key, (0.0, 0.0))
            out[key] = (tv, tw, mv, mw)
        return out

    async def fetch_rows_needing_sentiment(
        self, table_ref: str, prompt_version: str, window_days: int, limit: int
    ) -> list[tuple[int, str]]:
        """sentiment NULL 인 기존 분류행을 (class_id, 입력 텍스트) 목록으로 반환한다(감성 백필용)."""
        sql = _FETCH_SENTIMENT_BACKFILL_BY_TABLE.get(table_ref)
        if sql is None:
            return []
        rows = (
            await self.session.execute(
                sql, {"pv": prompt_version, "win": window_days, "lim": limit}
            )
        ).all()
        return [(r.class_id, r.body) for r in rows]

    async def update_sentiment(self, payload: list[dict]) -> int:
        """class_id 별 sentiment·sentiment_score 만 UPDATE 한다(섹터 분류 보존). 건수를 반환한다."""
        if not payload:
            return 0
        await self.session.execute(_UPDATE_SENTIMENT, payload)
        return len(payload)

    async def fetch_unclassified_text_rows(
        self, table_ref: str, prompt_version: str, window_days: int, limit: int
    ) -> list[tuple[int, str]]:
        """최근 window_days 내 미분류 raw 행을 (raw_id, 입력 텍스트) 목록으로 반환한다."""
        sql = _FETCH_UNCLASSIFIED_BY_TABLE.get(table_ref, _FETCH_UNCLASSIFIED_DISCOURSE)
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

    async def fetch_documents(
        self,
        sector_slug: str,
        limit: int = 8,
        *,
        prompt_version: str,
        confidence_min: float,
    ) -> dict | None:
        """단일 섹터 관련 문서(공시·기사 news / 기술·R&D tech) 그룹별 최신 limit건. 섹터 미존재 시 None."""
        name_row = (await self.session.execute(_SECTOR_NAME_SQL, {"slug": sector_slug})).first()
        if name_row is None:
            return None
        rows = (
            await self.session.execute(
                _DOCUMENTS_SQL,
                {
                    "slug": sector_slug,
                    "limit": limit,
                    "pv": prompt_version,
                    "conf_min": confidence_min,
                },
            )
        ).all()
        groups: dict[str, list[dict]] = {"news": [], "tech": []}
        for r in rows:
            groups[r.doc_group].append(
                {
                    "title": r.title,
                    "url": r.url,
                    "source_type": r.source_type,
                    "published_at": r.published_at.isoformat() if r.published_at else None,
                    "sentiment": r.sentiment,
                }
            )
        return {
            "sector_slug": sector_slug,
            "sector_name": name_row.name_ko,
            "news": groups["news"],
            "tech": groups["tech"],
        }

    async def fetch_investments(
        self,
        sector_slug: str,
        limit: int = 8,
        *,
        invest_prompt_version: str,
        dart_prompt_version: str,
        text_prompt_version: str,
        confidence_min: float,
        window_days: int = 30,
    ) -> dict | None:
        """단일 섹터 투자·자금 흐름 — 최근 목록 + 직전 기간 대비 총액 비교. 섹터 미존재 시 None."""
        from datetime import datetime, timedelta, timezone

        name_row = (await self.session.execute(_SECTOR_NAME_SQL, {"slug": sector_slug})).first()
        if name_row is None:
            return None
        base_params = {
            "slug": sector_slug,
            "invest_pv": invest_prompt_version,
            "dart_pv": dart_prompt_version,
            "text_pv": text_prompt_version,
            "conf_min": confidence_min,
        }
        # 윈도우 경계는 KST 기준 — 서버 TZ(UTC)면 자정 부근 최대 9시간 경계 오차가 나는 것을 방지.
        today = datetime.now(timezone(timedelta(hours=9))).date()
        recent_from = today - timedelta(days=window_days)
        prev_from = today - timedelta(days=window_days * 2)
        rows = (
            await self.session.execute(
                _INVESTMENTS_LIST_SQL, {**base_params, "limit": limit}
            )
        ).all()
        agg = (
            await self.session.execute(
                _INVESTMENTS_SUMMARY_SQL,
                {**base_params, "recent_from": recent_from, "prev_from": prev_from},
            )
        ).first()
        recent_total = int(agg.recent_total)
        recent_count = int(agg.recent_count)
        prev_total = int(agg.prev_total)
        prev_count = int(agg.prev_count)
        delta_pct = (
            round((recent_total - prev_total) / prev_total * 100, 1) if prev_total > 0 else None
        )
        items = [
            {
                "company": r.company,
                "amount_krw": int(r.amount_krw),
                "flow_label": r.flow_label,
                "investor": r.investor_name,
                "date": r.ref_date.isoformat() if r.ref_date else None,
                "title": r.raw_title,
                "url": r.source_url,
            }
            for r in rows
        ]
        return {
            "sector_slug": sector_slug,
            "sector_name": name_row.name_ko,
            "summary": {
                "window_days": window_days,
                "recent_total_krw": recent_total,
                "recent_count": recent_count,
                "prev_total_krw": prev_total,
                "prev_count": prev_count,
                "delta_pct": delta_pct,
            },
            "items": items,
        }

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
