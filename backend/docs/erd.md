# Unified ERD (Medallion + App Domains)

이 문서는 기존 `erd.md`의 중복/충돌(`domains` vs `sectors`, 구버전 Pulse 테이블 중복, FK 방향 불일치, `users` DDL 누락)을 정리한 **최종 통합본**입니다.

- 기준 마스터는 `sectors(slug)`로 단일화
- Pulse/Gap은 메달리온 아키텍처(Bronze/Silver/Gold) 기준
- Consult/Coach/Sync도 동일 기준(`user_id`, `sector_slug`)으로 연결

---

## 0) 구현 상태 & 마이그레이션 정합 (먼저 읽기)

> **이 문서는 목표 논리 모델과 실제 물리 스키마가 섞여 있다.** DDL이 적혀 있다고 물리 테이블이 존재한다는 뜻이 아니다. 코드를 작성하기 전 반드시 이 절을 먼저 읽는다.

**상태 범례**
- ✅ **물리 구현** — 마이그레이션으로 실제 테이블 존재.
- 🟡 **스키마만** — 테이블 DDL은 존재하나 이를 채우는 정제/서비스 로직이 없음.
- 🔴 **목표 모델** — DDL은 설계일 뿐 물리 테이블 미존재. 그대로 쓰면 `relation does not exist`로 깨진다.

**마이그레이션 정합 (2026-06-24 기준)**
- 실제 마이그레이션 head = **`e2c5a7b9d3f4`** (down=`d7f3a9c1e5b2`). 이 문서가 가정하는 적용 head도 동일.
- `e2c5a7b9d3f4`(raw_discourse_data·verified_company_master)는 Neon **미적용 가능성**이 있다. 배포 전 `alembic current` 확인이 필수다.
- `9f2a6d4e1b0c`(2026-05-06, reset)가 `alembic_version`을 제외한 **public 전 테이블을 DROP CASCADE** 후 `users`·`user_sync_profiles`만 재생성했다. 그 이전 마이그레이션이 만든 `user_competency`·`user_roadmap_status`·`refresh_tokens`·`playing_with_neon`은 **현재 존재하지 않는다**. 이후 마이그레이션이 raw_*·sectors계열·refined_innovation 계열을 추가했다.

> **⚠️ 2026-06-26 갱신 — 아래 §0 목록(2026-06-24 기준)은 마이그레이션 파일이 그 이후 크게 진척돼 일부 stale 하다.**
> - **마이그레이션 파일 head = `b8e4c2a6f1d9`** (체인: `e2c5a7b9d3f4` → … → `f1a2b3c4d5e6`(Pulse) → `b2d4f6a8c0e1`(text_sector) → `c3e7f1a9b5d2` → `d4f8a2c6e0b3`(Gap) → `e5a9c3f7b1d4`(Chance) → `f6b1d4e8a2c5`(pgvector) → `f8c2e6a0d3b7`(Sync) → `a7d3f1b9c2e4`(Briefing) → `b8e4c2a6f1d9`(Causal)). **파일 존재 ≠ Neon 적용** — 배포 전 `alembic current` 로 실제 적용 head 확인 필수.
> - 위 마이그레이션으로 **Silver §5.1~5.3 + Gold §6 의 인사이트 6수직 테이블이 파일상 정의됨**: `refined_gap_insights`·`refined_chance_insights`·`refined_pulse_metric_silver`·`refined_sync_inputs`·`document_embeddings`·`user_embeddings`·`pulse_metrics_log`·`gap_issues`·`issue_evidences`·`chance_opportunities`·`user_chance_matches`·`sync_scores_daily`·`economic_briefings`·`causal_chains`. 따라서 이들은 더 이상 🔴(목표 모델)이 아니라 **마이그레이션 정의됨**(Neon 적용은 별도 확인).
> - **미문서 실재 테이블 2종(ORM+마이그레이션 존재, 본 카탈로그 누락)**: `refined_text_sector_class`(`b2d4f6a8c0e1` — economic_text·discourse 섹터 분류 Silver, raw_table_ref VARCHAR(40)) · `refined_causal_chain_insights`(`b8e4c2a6f1d9` — Causal Silver, causal_chains 의 정제원). 추후 정식 절로 편입 필요.
> - **`trending_keywords`·`crossover_metrics` 는 ORM/마이그레이션이 없다.** 본 절 §6 DDL 은 미실현 설계이며, 실제로는 런타임 즉석 산출(`domain/market_insight/hub/services/keyword_trends.py`·`crossover_metrics.py`)로 대체됐다. 물리 테이블을 만들지 않는다.
> - 여전히 🔴 미실현: Roadmap/Coach §6·Consult/Profile §7 (해당 도메인 스캐폴딩 단계).
> - 아키텍처 메모: 인사이트 수직의 실제 구현은 LangGraph/MCP 가 아니라 "얇은 라우터 → RefineService → raw SQL repository → DB" 의 직선 파이프라인이다.

**현재 물리 존재 테이블 (✅, 총 14)**
`users` · `user_sync_profiles` · `sectors` · `sub_sectors` · `sector_source_map` · `raw_economic_data` · `raw_market_timeseries` · `raw_innovation_data` · `raw_people_data` · `raw_opportunity_data` · `raw_discourse_data`\* · `verified_company_master`\* · `refined_innovation_signal`🟡 · `refined_signal_sources`🟡
(\* = `e2c5a7b9d3f4` 적용 시 존재. refined_* 2종은 DDL만 있고 정제 로직이 없어 🟡)

**미존재 (🔴 목표 모델)** — 본 문서에 DDL이 있어도 물리 테이블이 없다
- Silver §5.1: `refined_trend_insights` · `refined_gap_insights` · `refined_chance_insights`.
- AI/RAG §5.2(신설): `document_embeddings`. Sync·Pulse §5.3(신설): `user_embeddings` · `refined_pulse_metric_silver` · `refined_sync_inputs`.
- Gold §6 전체: `pulse_metrics_log` · `trending_keywords` · `economic_briefings` · `causal_chains` · `crossover_metrics` · `gap_issues` · `issue_evidences` · `sync_scores_daily` · `chance_opportunities` · `user_chance_matches` · `user_roadmaps` · `roadmap_quests` · `growth_daily_logs` · `coach_sessions` · `coach_messages` · `insight_wallets`. (예외: `user_sync_profiles`는 §6.3에 있으나 ✅ 물리 존재)
- Consult/Profile §7 전체: `consultation_sessions` · `consultation_turns` · `user_personas` · `user_competencies`.

**인증 영속 경계** — 리프레시 토큰·OAuth state·PKCE는 **Redis(Upstash)** 에만 저장하며 DB 테이블을 두지 않는다(`refresh_tokens`는 reset에서 제거됨). ERD에 인증 토큰 테이블이 없는 것은 정상이다.

---

## 1) 핵심 설계 원칙

1. **마스터 단일화**: 산업 기준은 `sectors.slug` 하나만 사용  
2. **Bronze 불변**: 원천 수집 테이블은 가급적 변경하지 않음  
3. **Silver 확장**: AI 추론/정제 결과는 도메인별 Silver 테이블로 분리  
4. **Gold 서빙 전용**: 앱/웹 UI는 Gold 테이블만 조회  
5. **데이터 리니지 보존**: Silver/Gold에서 `raw_table_ref`, `raw_id`로 역추적 가능

> **현재 구현 차이:** ERD는 목표 논리 모델이다. 2026-06-07 기준 master 수집기는
> KIPRIS와 Naver DataLab도 `raw_economic_data`에 적재한다.
> 현재 물리 구현은
> [`MASTER_BRONZE_IMPLEMENTATION_STATUS.md`](../domain/master/docs/economic/core/MASTER_BRONZE_IMPLEMENTATION_STATUS.md)를 따른다.
>
> **2026-06-12 결함 수정 (마이그레이션 `d7f3a9c1e5b2`):** 아래 4개 구조 결함을 수정했다.
> - **A.** `sectors`/`sub_sectors` 마스터 생성·시드(12개) + `sector_source_map`으로
>   5개 Innovation 소스 분류값(arXiv 카테고리·GitHub 토픽·관세청 HS그룹·tech_category)을
>   섹터 slug로 통합 — Silver 융합의 공통 축 확보.
> - **B.** Silver 리니지를 1:1에서 N:M으로 전환(`refined_signal_sources`). 한 신호가
>   여러 Bronze 원천을 가리켜 "다수 소스 동시 출현 = 강신호"를 표현.
> - **C.** Silver에 `reference_period_start/end`(데이터 기준 기간)와 증거별
>   `contribution_weight`(lead-lag 가중) 추가 — 선행(arXiv)·후행(관세청) 시차 모델링 가능.
> - **D.** `data_role`을 JSONB에서 1급 컬럼으로 승격(`refined_innovation_signal.data_role`).
>
> 기존 `refined_trend/gap/chance_insights`(미구현)의 1:1 `raw_table_ref`/`raw_id`는
> 위 N:M 패턴으로 대체되며, Silver 본격 구현 시 동일 패턴을 따른다.

---

## 2) 통합 ERD 개요

```text
users (1) ───< consultation_sessions (N) ───< consultation_turns (N)
   │                       │
   │                       └──── updates ──> user_personas (1:1 by user_id)
   │
   ├────< user_competencies (N) ───> sectors (slug PK)
   │
   └────< sync_scores_daily (N) ───> sectors (slug PK)
   │
   ├────< user_roadmaps (N) ───< roadmap_quests (N, self-parent tree)
   │
   └────< growth_daily_logs (N)

sectors (1) ───< sub_sectors (N)
   │
   ├────< refined_trend_insights (Silver)
   ├────< refined_gap_insights (Silver)
   │
   ├────< pulse_metrics_log (Gold)
   ├────< causal_chains (Gold)
   ├────< gap_issues (Gold) ───< issue_evidences (Gold)
   └────< trending_keywords / economic_briefings / crossover_metrics (Gold)

raw_* (Bronze) ───> refined_* (Silver) ───> *_log/*_issues (Gold)

raw_economic_data     — 이벤트·신호 (뉴스, 거래량 급증, 공시)
raw_market_timeseries — 티커×거래일 OHLCV 연속 시계열 (Yahoo 16종 등)

document_embeddings   — RAG/유사도 검색 벡터 저장소 (§5.2, halfvec 3072)
user_embeddings / refined_pulse_metric_silver / refined_sync_inputs — Sync·Pulse 산출 입력 (§5.3)
```

---

## 3) 마스터/공통 테이블

```sql
-- 3.1 사용자 (누락되었던 기준 테이블 보강)
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),     -- 사용자 고유 식별자(UUID)
    email VARCHAR(255) UNIQUE NOT NULL,                -- 로그인 이메일(유니크, 필수)
    nickname VARCHAR(80) NOT NULL,                     -- 서비스 표시 닉네임
    auth_provider VARCHAR(20) NOT NULL DEFAULT 'LOCAL', -- LOCAL / GOOGLE / KAKAO
    provider_id VARCHAR(255),                          -- OAuth 제공자 내부 사용자 ID
    profile_image_url VARCHAR(500),                   -- 프로필 이미지 URL
    is_active BOOLEAN DEFAULT TRUE,                    -- 활성/휴면 상태
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),     -- 생성 시각
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()      -- 수정 시각
);
CREATE INDEX idx_users_oauth ON users(auth_provider, provider_id);

-- 3.2 산업 마스터 (단일 기준: sectors.slug)
CREATE TABLE sectors (
    slug VARCHAR(50) PRIMARY KEY,            -- 예: 'ai-data'
    name_ko VARCHAR(100) NOT NULL,           -- 예: 'AI·데이터'
    accent_color VARCHAR(20),                -- 예: '#6366F1'
    display_order INT NOT NULL,              -- 화면 노출 정렬 순서
    is_active BOOLEAN DEFAULT TRUE           -- 활성 섹터 여부
);

CREATE TABLE sub_sectors (
    id BIGSERIAL PRIMARY KEY,                               -- 세부 섹터 PK
    sector_slug VARCHAR(50) NOT NULL REFERENCES sectors(slug), -- 상위 섹터 FK
    name VARCHAR(100) NOT NULL,                            -- 세부 분야명
    description TEXT                                       -- 세부 설명
);

CREATE INDEX idx_sub_sectors_sector ON sub_sectors(sector_slug);
```

> **구현 상태(2026-06-12):** `sectors`·`sub_sectors`는 마이그레이션 `d7f3a9c1e5b2`로
> 물리 생성되었고 `sectors`는 12개 섹터로 시드되었다. (실제 제약명: `pk_sectors`,
> `pk_sub_sectors`, `fk_sub_sectors_sector`, `ix_sub_sectors_sector`.)

```sql
-- 3.3 소스 분류값 → 섹터 통합 매핑 (결함 A 수정)
--     5개 Innovation 소스의 이질적 분류값을 단일 sectors.slug 축으로 정규화한다.
--     Silver는 이 테이블을 조회해 arXiv/GitHub/관세청/TechBlog 신호를 같은 섹터로 묶는다.
CREATE TABLE sector_source_map (
    id BIGSERIAL PRIMARY KEY,                            -- 매핑 PK
    sector_slug VARCHAR(50) NOT NULL REFERENCES sectors(slug), -- 귀속 섹터
    match_key VARCHAR(50) NOT NULL,                      -- 분류 차원: arxiv_category / github_topic / customs_group / tech_category
    match_value VARCHAR(120) NOT NULL,                   -- 원천 분류값: 'cs.AI', 'machine-learning', 'SEMICONDUCTOR', 'AI_ML' 등
    note VARCHAR(255),                                   -- 매핑 근거 메모(옵션)
    created_at TIMESTAMPTZ DEFAULT now(),                -- 생성 시각
    UNIQUE (match_key, match_value)                      -- 동일 분류값은 1개 섹터로만
);
CREATE INDEX ix_sector_source_map_sector ON sector_source_map(sector_slug);
-- 시드 예: ('arxiv_category','cs.AI','ai-data'), ('customs_group','COSMETICS','beauty-fashion'),
--          ('github_topic','robotics','mobility'), ('tech_category','FINTECH','fintech') ...
```

---

## 4) Bronze Layer (원천 수집)

```sql
CREATE TABLE raw_economic_data (
    id BIGSERIAL PRIMARY KEY,                 -- 원천 데이터 PK
    source_type VARCHAR(50) NOT NULL,         -- DART_API, VC_NEWS, GOVT_BUDGET 등
    source_url TEXT,                          -- 원문/출처 URL (길이 제한 해제)
    
    -- 핵심 엔티티 정보
    raw_title VARCHAR(500) NOT NULL,          -- 공시 제목, 뉴스 헤드라인 (필수)
    investor_name VARCHAR(255),               -- 투자 주체 (예: 삼성전자, 소프트뱅크벤처스)
    target_company_or_fund VARCHAR(255),      -- 투자 대상 (예: 레인보우로보틱스, TIGER AI반도체)
    
    -- 수치 정보
    investment_amount BIGINT,                 -- 투자/유입 금액 (원 단위 통일 권장)
    currency VARCHAR(10) DEFAULT 'KRW',       -- 통화 (USD 뉴스 등이 섞일 경우를 대비)
    
    -- 확장 정보 (Silver 계층의 LLM이 파싱할 먹잇감)
    raw_metadata JSONB,                       -- 기타 추출된 원천 데이터 (투자 목적, 요약문, RSS 본문 등)
    
    -- 시간 정보
    published_at TIMESTAMPTZ,                 -- 실제 공시일 / 기사 발행일 (시계열 분석의 핵심)
    collected_at TIMESTAMPTZ DEFAULT now()    -- 시스템 수집 시각
);
-- 설명: 경제·자본 **이벤트** 단위 (VC 뉴스, DART, Yahoo 거래량 **급증** 신호 등).
--       일별 OHLCV 전량은 `raw_market_timeseries` 에 적재 (의미·grain 분리).

-- 상장·ETF 일별 시계열 (Yahoo Finance / yfinance)
CREATE TABLE raw_market_timeseries (
    id BIGSERIAL PRIMARY KEY,
    ticker VARCHAR(32) NOT NULL,              -- yfinance 심볼 (예: 091220.KS, SPY)
    trade_date DATE NOT NULL,                 -- 거래일 (시장 기준일, KST 변환 후 date)

    -- 자산 메타 (Yahoo 16종 모니터링 대상과 동일 네임스페이스)
    source_type VARCHAR(50) NOT NULL,         -- YAHOO_ETF_AI, YAHOO_STOCK_KR_SAMSUNG, YAHOO_GLOBAL_SPY …
    asset_name VARCHAR(255) NOT NULL,         -- 표시명 (예: TIGER 글로벌AI액티브)
    theme VARCHAR(100),                       -- 테마 라벨 (예: AI/반도체)
    currency VARCHAR(10) NOT NULL DEFAULT 'KRW', -- KRW | USD

    -- OHLCV (Bronze 원본 — Silver에서 급증·Z-score·모멘텀 산출)
    open_price NUMERIC(18, 6),
    high_price NUMERIC(18, 6),
    low_price NUMERIC(18, 6),
    close_price NUMERIC(18, 6) NOT NULL,
    volume BIGINT NOT NULL,                   -- 거래량(주)
    turnover_amount BIGINT,                   -- 추정 거래대금 = volume × (H+L+C)/3

    raw_metadata JSONB,                       -- data_provider, vwap_approx, turnover_calc 등
    collected_at TIMESTAMPTZ DEFAULT now(),   -- 최초 적재·upsert 갱신 시각

    CONSTRAINT uq_raw_market_timeseries_ticker_date UNIQUE (ticker, trade_date)
);
CREATE INDEX ix_raw_market_ts_ticker_date ON raw_market_timeseries(ticker, trade_date);
CREATE INDEX ix_raw_market_ts_trade_date ON raw_market_timeseries(trade_date);
CREATE INDEX ix_raw_market_ts_source_type ON raw_market_timeseries(source_type);
-- 설명:
--   - `raw_economic_data` 와 분리: 이벤트(URL unique) vs 시계열(ticker+date unique)
--   - 수집: POST /api/master/bronze/market-timeseries/yahoo
--   - 일일 스케줄: incremental period=1mo upsert / 초기 backfill: incremental=false (1y)
--   - 규모 참고: 16 ticker × ~252 거래일/년 ≈ 4,000 rows/년 (티커 확장 시 선형 증가)
--   - Silver 후보: 20일 평균 거래대금, 누적 추세, VC 뉴스 대비 2주 lag 상관

CREATE TABLE raw_innovation_data (
    id BIGSERIAL PRIMARY KEY,                 -- 원천 데이터 PK
    source_type VARCHAR(50) NOT NULL,         -- PATENT, ARXIV, GITHUB 등
    source_url TEXT,                          -- 원문/저장소 URL

    -- 핵심 엔티티 정보
    title VARCHAR(500) NOT NULL,              -- 논문/특허/리포지토리 제목
    author_or_assignee VARCHAR(255),          -- 저자 또는 특허 출원인
    abstract_text TEXT,                       -- 초록 또는 Readme 요약

    -- 확장 정보 (Silver 계층 LLM 파싱용)
    raw_metadata JSONB,                       -- 인용 수(Citations), Star 수, 언어, 키워드 등 부가정보

    -- 시간 정보
    published_at TIMESTAMPTZ,                 -- 출원일 / 논문 발행일 / 커밋일
    collected_at TIMESTAMPTZ DEFAULT now()    -- 시스템 수집 시각
);

CREATE TABLE raw_people_data (
    id BIGSERIAL PRIMARY KEY,                 -- 원천 데이터 PK
    source_type VARCHAR(50) NOT NULL,         -- GOOGLE_TRENDS, NAVER_DATALAB, LINKEDIN 등
    source_url TEXT,                          -- 쿼리 URL

    -- 핵심 엔티티 정보
    keyword_or_job VARCHAR(100) NOT NULL,     -- 검색 키워드/채용 직무
    search_volume_or_count INT,               -- 검색량/건수

    -- 확장 정보 (Silver 계층 LLM 파싱용)
    raw_metadata JSONB,                       -- 연관 검색어, 디바이스 비율, 지역별 분포 등 부가정보

    -- 시간 정보
    reference_date DATE,                      -- 해당 데이터가 가리키는 실제 기준 일자 (시계열 분석 핵심)
    collected_at TIMESTAMPTZ DEFAULT now()    -- 시스템 수집 시각
);

CREATE TABLE raw_discourse_data (
    id BIGSERIAL PRIMARY KEY,                 -- 원천 데이터 PK
    source_type VARCHAR(50) NOT NULL,         -- NEWS, REDDIT, BLIND, REPORT, JOB_INFO, SKILL_INFO, SUCCESS_CASE 등
    source_url TEXT,                          -- 뉴스/게시글 링크 또는 출처 URL

    -- 핵심 엔티티 정보
    headline VARCHAR(500) NOT NULL,           -- 헤드라인 / 게시글 제목 / 직업명 / 직무명
    author_or_publisher VARCHAR(255),         -- 언론사명 / 작성자 ID / 발간 기관 / 정부 기관명
    content_body TEXT,                        -- 본문 전문/요약 / 직업·직무 설명 / 우수사례 내용

    -- 확장 정보 (Silver 계층 LLM 파싱용)
    raw_metadata JSONB,                       -- 댓글 수, 좋아요 수, 감성 분석 점수, 카테고리
                                              -- (REPORT 계열) 연봉 정보, 전망 점수, 요구 역량, 학습 경로
                                              -- (SUCCESS_CASE 계열) 선정 기업명, 지원 금액, 성과 지표 등

    -- 시간 정보
    published_at TIMESTAMPTZ,                 -- 기사 송고 시각 / 게시글 작성 시각 / 발간일
    collected_at TIMESTAMPTZ DEFAULT now()    -- 시스템 수집 시각
);
-- 설명: 담론·정성적 데이터 수집 테이블
--   - NEWS: 일반 뉴스 기사 (네이버, 구글 뉴스 등)
--   - REDDIT, BLIND: 커뮤니티 게시글
--   - REPORT: 정부 보고서, 업계 리포트
--   - JOB_INFO: 워크넷 직업정보 (연봉, 전망, 업무 환경 등 구조화된 직업 설명)
--   - SKILL_INFO: 워크넷 직무정보 (요구 스킬셋, 학습 경로, 자격증 등)
--   - SUCCESS_CASE: 정부 지원사업 우수사례 (선정 기업의 성공 스토리)

-- Chance 원천 수집 (채용/부트캠프/공모전/지원사업)
CREATE TABLE raw_opportunity_data (
    id BIGSERIAL PRIMARY KEY,                 -- 원천 데이터 PK
    source_type VARCHAR(50) NOT NULL,         -- JOB / BOOTCAMP / CONTEST / GRANT
    source_url TEXT NOT NULL,                 -- 원본 공고 링크

    -- 핵심 엔티티 정보
    raw_title VARCHAR(500) NOT NULL,          -- 공고 제목
    host_name VARCHAR(150),                   -- 주최/주관 기관 또는 기업명
    raw_content TEXT,                         -- 원문 본문

    -- 확장 정보 (Silver 계층 LLM 파싱용)
    raw_metadata JSONB,                       -- 지원 자격, 상금 규모, 근무지, 경력 요건 등 부가정보

    -- 시간 정보
    published_at TIMESTAMPTZ,                 -- 공고 게시일
    deadline_at TIMESTAMPTZ,                  -- 지원 마감일시 (앱 알림 기능의 핵심)
    collected_at TIMESTAMPTZ DEFAULT now()    -- 시스템 수집 시각
);

-- 검증된 기업 마스터 (정부 인증·선정 기업 명단)
CREATE TABLE verified_company_master (
    id BIGSERIAL PRIMARY KEY,                 -- 기업 마스터 PK
    source_type VARCHAR(50) NOT NULL,         -- KSTARTUP_PREUNICORN / VENTURE_CERTIFIED / INNOBIZ / MAINBIZ 등
    
    -- 핵심 식별 정보
    company_name VARCHAR(255) NOT NULL,       -- 기업명 (필수)
    business_number VARCHAR(20),              -- 사업자등록번호 (10자리)
    corp_number VARCHAR(20),                  -- 법인등록번호 (13자리, 있는 경우)
    ceo_name VARCHAR(100),                    -- 대표자명
    
    -- 인증/선정 정보
    certification_type VARCHAR(100),          -- 인증·선정 명칭 (예: "K-예비유니콘", "벤처기업 인증")
    certification_date DATE,                  -- 인증일자 또는 선정 발표일
    expiry_date DATE,                         -- 인증 만료일 (해당 시)
    certifying_agency VARCHAR(150),           -- 인증·선정 기관 (예: "중소벤처기업부")
    
    -- 기업 세부 정보
    industry_sector VARCHAR(100),             -- 업종·분야 (예: "AI", "바이오", "핀테크")
    establishment_date DATE,                  -- 설립일
    address TEXT,                             -- 주소
    
    -- 확장 정보
    raw_metadata JSONB,                       -- 원천 CSV/XLSX의 추가 필드 (투자 유치 이력, 특허 수 등)
    
    -- 데이터 출처 정보
    source_file_url TEXT,                     -- 원본 파일 다운로드 URL
    source_file_version VARCHAR(50),          -- 파일 버전 또는 배포 년월 (예: "2026-04")
    
    -- 시간 정보
    collected_at TIMESTAMPTZ DEFAULT now(),   -- 최초 수집 시각
    updated_at TIMESTAMPTZ DEFAULT now()      -- 갱신 시각 (재수집 시 덮어쓰기)
);
CREATE INDEX idx_verified_company_biz_num ON verified_company_master(business_number);
CREATE INDEX idx_verified_company_name ON verified_company_master(company_name);
CREATE INDEX idx_verified_company_source_type ON verified_company_master(source_type);
CREATE UNIQUE INDEX uq_verified_company_source_biz ON verified_company_master(source_type, business_number) 
    WHERE business_number IS NOT NULL;
-- 설명: 동일 출처(source_type)에서 동일 사업자번호는 1개만 존재 (갱신 시 UPDATE)
```

---

## 5) Silver Layer (AI 정제/추론)

### 5.0 교차융합형 혁신 Silver — 결함 B·C·D 수정 (🟡 스키마만, 정제 서비스 미구현)

> 마이그레이션 `d7f3a9c1e5b2`로 **테이블만** 물리 생성됐고, 이를 채우는 정제 서비스/리포지토리는 아직 없다(=🟡). Innovation Flow 산출의 기준 스키마이며,
> Pulse/Gap/Chance Silver도 본격 구현 시 이 패턴(데이터 기준기간·data_role 1급화·N:M 리니지)을 따른다.
>
> **다음 마이그레이션 보강 예정(미적용):** 멱등 재처리를 위해 자연키 `UNIQUE(sector_slug, data_role, signal_topic, reference_period_start, reference_period_end)`와, 재현·회귀 추적용 `model_name`·`prompt_version` 컬럼을 추가한다. `data_role`은 자유문자열 대신 닫힌 집합(§5.3 표준값 참조)으로 CHECK를 건다.
> **리니지 주의:** `refined_signal_sources.signal_id`는 `refined_innovation_signal`에만 FK로 묶여 있어, §5.1의 다른 Silver는 이 테이블을 그대로 재사용할 수 없다. 범용 리니지(`refined_source_links`)로의 일반화는 P1에서 다룬다.

```sql
-- 섹터별 혁신 모멘텀 신호 (한 신호 = 여러 원천의 융합 결과)
CREATE TABLE refined_innovation_signal (
    id BIGSERIAL PRIMARY KEY,                            -- Silver 신호 PK
    sector_slug VARCHAR(50) NOT NULL REFERENCES sectors(slug), -- 귀속 섹터(sector_source_map으로 해소)
    sub_sector_id BIGINT REFERENCES sub_sectors(id),     -- 세부 섹터(옵션)
    data_role VARCHAR(50) NOT NULL,                      -- (D) 1급 컬럼: FUTURE_TECH_SIGNAL / EXPORT_FLOW_SIGNAL / TECH_BLOG_SIGNAL …
    signal_topic VARCHAR(255) NOT NULL,                  -- 통합 토픽/기술명
    momentum_score INT,                                  -- 정규화 모멘텀(0~100)
    confidence NUMERIC(5,2),                             -- 신뢰도
    extracted_keywords JSONB,                            -- 키워드 배열
    reference_period_start DATE NOT NULL,                -- (C) 데이터가 가리키는 기준 기간 시작
    reference_period_end DATE NOT NULL,                  -- (C) 기준 기간 끝 — lead-lag 정렬 근거
    source_count INT NOT NULL DEFAULT 0,                 -- (B) 교차 출처 보강 개수(다수 소스 = 강신호)
    processed_at TIMESTAMPTZ DEFAULT now(),              -- 분석 완료 시각
    CONSTRAINT ck_refined_innov_period CHECK (reference_period_end >= reference_period_start)
);
CREATE INDEX ix_refined_innov_sector ON refined_innovation_signal(sector_slug);
CREATE INDEX ix_refined_innov_data_role ON refined_innovation_signal(data_role);
CREATE INDEX ix_refined_innov_period ON refined_innovation_signal(reference_period_start, reference_period_end);

-- (B) N:M 리니지 — 한 신호가 가리키는 다수 Bronze 원천
CREATE TABLE refined_signal_sources (
    id BIGSERIAL PRIMARY KEY,                            -- 리니지 PK
    signal_id BIGINT NOT NULL REFERENCES refined_innovation_signal(id) ON DELETE CASCADE, -- 소속 신호
    raw_table_ref VARCHAR(50) NOT NULL,                  -- 원천 테이블명(raw_innovation_data 등)
    raw_id BIGINT NOT NULL,                              -- 원천 레코드 PK
    contribution_weight NUMERIC(5,2),                    -- 시차/신뢰 가중(선행 arXiv vs 후행 관세청 차등)
    created_at TIMESTAMPTZ DEFAULT now(),                -- 생성 시각
    UNIQUE (signal_id, raw_table_ref, raw_id)            -- 동일 원천 중복 연결 방지
);
CREATE INDEX ix_refined_signal_sources_raw ON refined_signal_sources(raw_table_ref, raw_id); -- 역추적
```

### 5.1 Pulse/Gap/Chance Silver (목표 모델)

> 아래 3개는 미구현 목표 모델이다. 결함 수정 반영: `data_role`·`reference_date`를 추가했고,
> 1:1 `raw_table_ref`/`raw_id`는 §5.0의 N:M `refined_signal_sources` 패턴으로 대체한다.

```sql
-- Pulse 분석용 Silver
CREATE TABLE refined_trend_insights (
    id BIGSERIAL PRIMARY KEY,                 -- Silver 레코드 PK
    sector_slug VARCHAR(50) REFERENCES sectors(slug), -- AI 분류 섹터
    sub_sector_id BIGINT REFERENCES sub_sectors(id),  -- AI 분류 세부 섹터
    data_role VARCHAR(50) NOT NULL,           -- (D) 신호 종류 1급 컬럼
    sentiment_score FLOAT,                    -- -1.0 ~ 1.0
    impact_score INT,                         -- 영향도 점수
    extracted_keywords JSONB,                 -- 배열
    reference_date DATE,                      -- (C) 데이터 기준 일자(lead-lag)
    processed_at TIMESTAMPTZ DEFAULT now()    -- 분석 완료 시각
    -- (B) 원천 리니지는 refined_signal_sources(signal_id→이 테이블) 패턴 사용
);
CREATE INDEX idx_refined_trend_sector ON refined_trend_insights(sector_slug);

-- Gap 분석용 Silver
CREATE TABLE refined_gap_insights (
    id BIGSERIAL PRIMARY KEY,                 -- Silver 레코드 PK
    sector_slug VARCHAR(50) REFERENCES sectors(slug), -- 관련 섹터
    data_role VARCHAR(50) NOT NULL,           -- (D) 신호 종류 1급 컬럼
    extracted_problem TEXT NOT NULL,
    extracted_opportunity TEXT NOT NULL,
    reference_date DATE,                      -- (C) 데이터 기준 일자
    processed_at TIMESTAMPTZ DEFAULT now()    -- 분석 완료 시각
    -- (B) 원천 리니지는 refined_signal_sources 패턴 사용
);
CREATE INDEX idx_refined_gap_sector ON refined_gap_insights(sector_slug);

-- Chance 분석용 Silver
CREATE TABLE refined_chance_insights (
    id BIGSERIAL PRIMARY KEY,                 -- Silver 레코드 PK
    sector_slug VARCHAR(50) REFERENCES sectors(slug), -- AI 판별 매칭 섹터
    data_role VARCHAR(50) NOT NULL,           -- (D) 신호 종류 1급 컬럼
    extracted_type VARCHAR(50) NOT NULL,      -- 채용/부트캠프/공모전/지원금 분류
    extracted_target JSONB,                   -- 지원 대상 목록(JSON 배열)
    extracted_benefits JSONB,                 -- 혜택/보상 목록(JSON 배열)
    extracted_deadline DATE,                  -- 마감일
    extracted_qualifications JSONB,           -- 자격 요건 목록(JSON 배열)
    reference_date DATE,                      -- (C) 데이터 기준 일자
    processed_at TIMESTAMPTZ DEFAULT now()    -- 분석 완료 시각
    -- (B) 원천 리니지는 refined_signal_sources 패턴 사용 (기존 raw_opportunity_data 1:1 대체)
);
CREATE INDEX idx_refined_chance_sector ON refined_chance_insights(sector_slug);
```

### 5.2 AI / RAG 인프라 (임베딩·벡터 검색) — 🔴 신규 설계 (P0)

> CLAUDE.md가 못박은 pgvector + `text-embedding-3-large`(3072차원) 기반 RAG·유사도 검색의 **물리 저장소**다. 기존 ERD에 벡터 컬럼이 전무해 Coach·유사도 검색이 구현 불가했던 공백을 메운다.
> Bronze 불변 원칙을 깨지 않도록 raw_*에 vector를 직접 넣지 않고 **별도 임베딩 테이블**에 모은다(리니지는 `source_table`/`source_id`로 보존).

```sql
CREATE EXTENSION IF NOT EXISTS vector;   -- pgvector >= 0.7 (halfvec 지원)

-- 임베딩 통합 저장소 (청크 단위 · 메타필터 + 유사도 검색을 한 쿼리로)
CREATE TABLE document_embeddings (
    id BIGSERIAL PRIMARY KEY,
    source_table VARCHAR(50) NOT NULL,        -- 원천 테이블명 (insight_wallets, coach_messages, gap_issues, refined_innovation_signal …)
    source_id BIGINT NOT NULL,                -- 원천 레코드 PK
    chunk_index INT NOT NULL DEFAULT 0,       -- 긴 본문 청크 순번 (RAG는 청크 단위)
    content_text TEXT NOT NULL,               -- 임베딩된 원문 청크 (재인덱싱·표시용)
    embedding halfvec(3072) NOT NULL,         -- 3072차원. vector(3072)는 HNSW 2000차원 한계 초과 → halfvec 사용
    embedding_model VARCHAR(60) NOT NULL DEFAULT 'text-embedding-3-large', -- 모델 고정 추적
    embedding_version VARCHAR(40),            -- 임베딩 파이프라인 버전 (재임베딩 백필 추적)
    sector_slug VARCHAR(50) REFERENCES sectors(slug), -- 메타필터용 섹터 축 (NULL 허용)
    metadata JSONB,                           -- 추가 메타필터 (data_role, user_id, lang 등)
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE (source_table, source_id, chunk_index, embedding_model) -- 동일 청크 중복 임베딩 방지(멱등)
);
-- 유사도 검색 인덱스: 코사인. halfvec + HNSW (ivfflat은 2000차원 한계로 불가)
CREATE INDEX ix_document_embeddings_hnsw
    ON document_embeddings USING hnsw (embedding halfvec_cosine_ops);
CREATE INDEX ix_document_embeddings_source ON document_embeddings(source_table, source_id); -- 역추적/재인덱싱
CREATE INDEX ix_document_embeddings_sector ON document_embeddings(sector_slug);
```

> **검색 패턴.** `WHERE sector_slug = :s AND metadata @> :filter ORDER BY embedding <=> :query_vec LIMIT k` — 메타필터 + 유사도를 단일 SQL로 처리한다.
> **차원 대안.** 3072 전차원 유지가 부담이면 OpenAI `dimensions=2000`으로 축소해 `vector(2000)` + HNSW(`vector_cosine_ops`)도 가능하다. 단 한 번 정하면 재임베딩 비용이 크므로 `embedding_model`/`embedding_version`으로 고정·추적한다.
> **감사 로그(FastMCP write tool)·LLM 관측 컬럼**은 P1(해당 도메인 구현 시) 범위다(§0 참조).

### 5.3 Sync·Pulse 산출용 Silver (재설계) — 🔴 신규 설계 (P0)

> 기존 Gold(`sync_scores_daily`, `pulse_metrics_log`)는 "점수만 적재되는 빈 결과 테이블"이었다. 무엇으로부터 계산되는지를 Silver로 명시해 **Gold가 단순 사영(projection)** 이 되도록 한다.
> 공통 원칙은 ① 일자 그레인 시계열, ② 멱등 자연키 UNIQUE(배치 재실행 안전), ③ `model_name`·`prompt_version`으로 재현·회귀 추적이다.

```sql
-- (Sync) 사용자 임베딩 — 적합도 산출 입력
CREATE TABLE user_embeddings (
    user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    embedding halfvec(3072) NOT NULL,         -- 관심사·목표직무·역량 텍스트의 임베딩
    source_version VARCHAR(40),               -- 입력 스냅샷 버전 (프로필 변경 시 재계산)
    embedding_model VARCHAR(60) NOT NULL DEFAULT 'text-embedding-3-large',
    computed_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX ix_user_embeddings_hnsw ON user_embeddings USING hnsw (embedding halfvec_cosine_ops);

-- (Pulse) 섹터×일자 정규화 시계열 Silver — Gold pulse_metrics_log의 입력
CREATE TABLE refined_pulse_metric_silver (
    id BIGSERIAL PRIMARY KEY,
    sector_slug VARCHAR(50) NOT NULL REFERENCES sectors(slug),
    sub_sector_id BIGINT REFERENCES sub_sectors(id),
    reference_date DATE NOT NULL,             -- 일자 그레인
    raw_signal_value NUMERIC(18,6),           -- 정규화 전 원시 합성값 (sentiment·volume·search 융합)
    normalized_score INT CHECK (normalized_score BETWEEN 0 AND 100), -- Gold score로 직결
    momentum_pct NUMERIC(8,2),                -- 기준 윈도우 대비 변화율 (급등 시 수천 % 가능, a1b2c3d4e5f6)
    status_badge VARCHAR(20),                 -- 급상승/태풍급 등 (닫힌 집합 권장)
    window_days INT NOT NULL,                 -- 모멘텀 산출 윈도우 (예: 20)
    baseline_method VARCHAR(40) NOT NULL,     -- zscore / pct_change / ma_ratio 등 (재현성)
    model_name VARCHAR(120),
    prompt_version VARCHAR(40),
    processed_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE (sector_slug, sub_sector_id, reference_date, baseline_method) -- 멱등
);
CREATE INDEX ix_refined_pulse_silver_sector_date ON refined_pulse_metric_silver(sector_slug, reference_date DESC);

-- (Sync) 사용자×섹터×일자 적합도 입력 — Gold sync_scores_daily의 입력
CREATE TABLE refined_sync_inputs (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    sector_slug VARCHAR(50) NOT NULL REFERENCES sectors(slug),
    reference_date DATE NOT NULL,
    affinity_score NUMERIC(5,2),              -- 사용자 임베딩 vs 섹터 트렌드 코사인 등
    trend_score NUMERIC(5,2),                 -- 섹터 트렌드 강도 (refined_pulse_metric_silver 참조)
    contributing_keywords JSONB,              -- 근거 키워드
    model_name VARCHAR(120),
    prompt_version VARCHAR(40),
    processed_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE (user_id, sector_slug, reference_date) -- 멱등
);
CREATE INDEX ix_refined_sync_inputs_user_date ON refined_sync_inputs(user_id, reference_date DESC);
```

> **data_role 표준값(닫힌 집합).** `FUTURE_TECH_SIGNAL` · `EXPORT_FLOW_SIGNAL` · `TECH_BLOG_SIGNAL` · `CAPITAL_FLOW_SIGNAL` · `DEMAND_HIRING_SIGNAL` · `SEARCH_DEMAND_SIGNAL` · `DISCOURSE_SIGNAL`. Silver 전반의 `data_role`은 이 집합으로 CHECK/ENUM 고정한다(자유문자열 금지).
> **Pulse 산출 흐름(검증 대상).** `raw_economic/innovation/people/market_timeseries` → (정제) `refined_innovation_signal`·`refined_pulse_metric_silver` → (사영) `pulse_metrics_log`(Gold). 이 한 줄을 끝까지 뚫어 ERD 적합성을 실증한다.
> ⏳ **구현 착수(2026-06-24).** `refined_pulse_metric_silver`·`pulse_metrics_log` 마이그레이션 `f1a2b3c4d5e6` 작성(미적용), 산출 로직 `pulse_pipeline.py`(결정론적·19 테스트 통과). `user_embeddings`·`refined_sync_inputs`는 설계만.

---

## 6) Gold Layer (UI 서빙)

> 🔴 **이 절의 모든 테이블은 목표 모델(물리 미존재)이다.** 단 §6.3 `user_sync_profiles`만 ✅ 실재한다. 그대로 SELECT하면 깨진다(§0 참조).

### 6.1 Pulse 탭

> ⏳ `refined_pulse_metric_silver`(§5.3)·`pulse_metrics_log` 마이그레이션 `f1a2b3c4d5e6` 작성 완료(미적용). 산출 로직 = `domain/market_insight/hub/services/pulse_pipeline.py`(결정론적·테스트 통과). DB 적용 전이라 §0 기준 여전히 🔴 미존재.

```sql
CREATE TABLE pulse_metrics_log (
    id BIGSERIAL PRIMARY KEY,                 -- Gold 레코드 PK
    sector_slug VARCHAR(50) NOT NULL REFERENCES sectors(slug), -- 집계 섹터
    sub_sector_id BIGINT REFERENCES sub_sectors(id), -- 세부 섹터(옵션)
    recorded_date DATE NOT NULL,              -- 차트 X축 날짜
    score INT NOT NULL CHECK (score BETWEEN 0 AND 100),
    status_badge VARCHAR(20) NOT NULL,        -- 태풍급/급상승 등
    momentum_pct NUMERIC(8,2),                -- 증감률(%) — 급등 시 수천 % 가능 (a1b2c3d4e5f6)
    created_at TIMESTAMPTZ DEFAULT now()      -- 적재 시각
);
CREATE INDEX idx_pulse_metrics_date_sector ON pulse_metrics_log(recorded_date, sector_slug);
-- 멱등 재생성용 자연키 (sub_sector_id NULL 안전, 마이그레이션 f1a2b3c4d5e6).
CREATE UNIQUE INDEX uq_pulse_metrics_natural ON pulse_metrics_log(sector_slug, COALESCE(sub_sector_id, -1), recorded_date);

CREATE TABLE trending_keywords (
    id BIGSERIAL PRIMARY KEY,                 -- 키워드 레코드 PK
    keyword_text VARCHAR(100) NOT NULL,       -- 키워드 텍스트
    display_type VARCHAR(20) NOT NULL,        -- TICKER / CLOUD
    value_label VARCHAR(50),                  -- +27%, 고정/하락 등 부가 라벨
    rank_order INT NOT NULL,                  -- 노출 순서
    is_active BOOLEAN DEFAULT TRUE,           -- 활성 여부
    updated_at TIMESTAMPTZ DEFAULT now()      -- 갱신 시각
);

CREATE TABLE economic_briefings (
    id BIGSERIAL PRIMARY KEY,                 -- 브리핑 레코드 PK
    published_date DATE NOT NULL,             -- 브리핑 기준일
    line_number INT NOT NULL CHECK (line_number IN (1,2,3)),
    content VARCHAR(255) NOT NULL,            -- 브리핑 문장
    trend_icon VARCHAR(20) NOT NULL,          -- UP_RIGHT / DOWN_RIGHT / WAVE
    created_at TIMESTAMPTZ DEFAULT now(),     -- 생성 시각
    UNIQUE (published_date, line_number)
);
CREATE INDEX idx_economic_briefings_date ON economic_briefings(published_date);

CREATE TABLE causal_chains (
    id BIGSERIAL PRIMARY KEY,                 -- 인과 체인 PK
    sector_slug VARCHAR(50) NOT NULL REFERENCES sectors(slug), -- 섹터 FK
    macro_event VARCHAR(255) NOT NULL,        -- 거시 이벤트
    industry_impact VARCHAR(255) NOT NULL,    -- 산업 영향
    youth_chance VARCHAR(255) NOT NULL,       -- 청년 기회
    published_date DATE NOT NULL,             -- 게시일
    is_active BOOLEAN DEFAULT TRUE,           -- 활성 여부
    created_at TIMESTAMPTZ DEFAULT now()      -- 생성 시각
);

CREATE TABLE crossover_metrics (
    id BIGSERIAL PRIMARY KEY,                 -- 크로스오버 레코드 PK
    title VARCHAR(100) NOT NULL,              -- 차트 주제
    legacy_label VARCHAR(50) NOT NULL,        -- 기존 축 라벨
    emerging_label VARCHAR(50) NOT NULL,      -- 신흥 축 라벨
    recorded_date DATE NOT NULL,              -- 시계열 날짜
    legacy_value INT NOT NULL,                -- 기존 축 값
    emerging_value INT NOT NULL,              -- 신흥 축 값
    is_crossover_point BOOLEAN DEFAULT FALSE, -- 교차 지점 여부
    created_at TIMESTAMPTZ DEFAULT now()      -- 생성 시각
);
```

### 6.2 Gap(블루오션) 탭

```sql
CREATE TABLE gap_issues (
    id BIGSERIAL PRIMARY KEY,                 -- 이슈 PK
    sector_slug VARCHAR(50) NOT NULL REFERENCES sectors(slug), -- 섹터 FK
    problem_summary VARCHAR(255) NOT NULL,    -- 카드: 세상의 문제
    chance_summary VARCHAR(255) NOT NULL,     -- 카드: 청년의 기회
    detail_summary TEXT,                      -- 상세: 요약
    stakeholders JSONB,                       -- 상세: 불릿 리스트
    next_actions JSONB,                       -- 상세: 번호 리스트
    is_active BOOLEAN DEFAULT TRUE,           -- 노출 여부
    published_date DATE NOT NULL,             -- 발행일
    created_at TIMESTAMPTZ DEFAULT now()      -- 생성 시각
);
CREATE INDEX idx_gap_issues_sector ON gap_issues(sector_slug);
CREATE INDEX idx_gap_issues_date ON gap_issues(published_date);
CREATE INDEX idx_gap_issues_active_date ON gap_issues(is_active, published_date DESC);

CREATE TABLE issue_evidences (
    id BIGSERIAL PRIMARY KEY,                 -- 근거 PK
    issue_id BIGINT NOT NULL REFERENCES gap_issues(id) ON DELETE CASCADE, -- 소속 이슈
    evidence_type VARCHAR(50) NOT NULL,       -- NEWS / REPORT / DATA / PATENT
    title VARCHAR(255) NOT NULL,              -- 근거 제목
    url VARCHAR(500) NOT NULL,                -- 출처 링크
    raw_table_ref VARCHAR(50),                -- 원천 테이블명(옵션)
    raw_id BIGINT,                            -- 원천 레코드 ID(옵션)
    created_at TIMESTAMPTZ DEFAULT now()      -- 생성 시각
);
CREATE INDEX idx_issue_evidences_issue_id ON issue_evidences(issue_id);
```

### 6.3 Sync(싱크) 탭

> ✅ `user_sync_profiles`는 물리 존재. 🔴 `sync_scores_daily`는 목표 모델(미존재). 산출 입력은 §5.3(`refined_sync_inputs`·`user_embeddings`) 참조.

```sql
-- 사용자 명시적 관심사/목표 직무 (AI 매칭 기준 데이터)
CREATE TABLE user_sync_profiles (
    user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE, -- 사용자 FK
    target_job VARCHAR(100),                  -- 목표 직무
    interest_keywords JSONB DEFAULT '[]'::jsonb, -- 관심 키워드 배열
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now() -- 갱신 시각
);

-- 사용자-섹터 적합도(싱크로율) 일별 스냅샷
CREATE TABLE sync_scores_daily (
    id BIGSERIAL PRIMARY KEY,                 -- 싱크 점수 PK
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE, -- 사용자 FK
    sector_slug VARCHAR(50) NOT NULL REFERENCES sectors(slug), -- 섹터 FK
    recorded_date DATE NOT NULL,              -- 일자 기준 스냅샷
    sync_score INT NOT NULL CHECK (sync_score BETWEEN 0 AND 100),
    trend_delta_pct DECIMAL(5,2),             -- 전일/전주 대비 변화율
    reason_lines JSONB,                        -- ["이유1", "이유2", "이유3"]
    keyword_evidence JSONB,                    -- ["키워드A", "키워드B"]
    created_at TIMESTAMPTZ DEFAULT now(),      -- 생성 시각
    UNIQUE (user_id, sector_slug, recorded_date)
);
CREATE INDEX idx_sync_scores_user_date ON sync_scores_daily(user_id, recorded_date DESC);
```

### 6.4 Chance(다이렉트 찬스) 탭

```sql
-- 다이렉트 찬스 마스터 (UI 컴포넌트 1:1 대응)
CREATE TABLE chance_opportunities (
    id BIGSERIAL PRIMARY KEY,                 -- 기회 PK
    sector_slug VARCHAR(50) NOT NULL REFERENCES sectors(slug), -- 섹터 FK

    title VARCHAR(255) NOT NULL,              -- 화면 노출 제목
    opportunity_type VARCHAR(50) NOT NULL,    -- 뱃지용 타입(교육/공모전/채용 등)
    host_name VARCHAR(150) NOT NULL,          -- 주최 기관명
    benefit_summary VARCHAR(255),             -- 카드용 혜택 요약
    target_audience VARCHAR(255),             -- 대상 요약
    d_day_date DATE NOT NULL,                 -- 마감일(D-Day 계산 기준)

    brief_description TEXT NOT NULL,          -- 상세 서술 요약
    eligibility_checks JSONB,                 -- 지원/참가 자격 체크 리스트
    actionable_preps JSONB,                   -- 바로 실행 준비물/액션 리스트
    reference_links JSONB,                    -- 관련 링크 객체 배열([{label,url}, ...])

    is_active BOOLEAN DEFAULT TRUE,           -- 노출 여부
    created_at TIMESTAMPTZ DEFAULT now()      -- 생성 시각
);
CREATE INDEX idx_chance_opps_sector ON chance_opportunities(sector_slug);
CREATE INDEX idx_chance_opps_dday ON chance_opportunities(d_day_date);

-- 유저별 기회 매칭 및 액션 상태
CREATE TABLE user_chance_matches (
    id BIGSERIAL PRIMARY KEY,                 -- 매칭 PK
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE, -- 사용자 FK
    opportunity_id BIGINT NOT NULL REFERENCES chance_opportunities(id) ON DELETE CASCADE, -- 기회 FK

    match_score INT NOT NULL CHECK (match_score BETWEEN 0 AND 100), -- 적합도 점수
    match_reason VARCHAR(255) NOT NULL,       -- 추천 사유 1줄

    is_saved BOOLEAN DEFAULT FALSE,           -- 북마크 여부
    is_applied BOOLEAN DEFAULT FALSE,         -- 지원 완료 여부

    created_at TIMESTAMPTZ DEFAULT now(),     -- 생성 시각
    updated_at TIMESTAMPTZ DEFAULT now(),     -- 갱신 시각
    UNIQUE (user_id, opportunity_id)          -- 중복 매칭 방지
);
CREATE INDEX idx_user_chance_matches_user ON user_chance_matches(user_id, match_score DESC);
```

### 6.5 Roadmap(전략 로드맵) 탭

```sql
-- 유저별 로드맵 마스터(로드맵 '판')
CREATE TABLE user_roadmaps (
    id BIGSERIAL PRIMARY KEY,                 -- 로드맵 PK
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE, -- 사용자 FK

    skill_triangle JSONB NOT NULL,            -- 3축 정보 (top/left/right)
    bridge_keywords JSONB NOT NULL,           -- 브릿지 키워드 배열

    ai_generated_reason TEXT,                 -- AI 생성 이유(상단 안내문)
    base_profile_snapshot JSONB,              -- 생성 당시 사용자 스냅샷

    is_active BOOLEAN DEFAULT TRUE,           -- 활성 로드맵 여부
    created_at TIMESTAMPTZ DEFAULT now(),     -- 생성 시각
    updated_at TIMESTAMPTZ DEFAULT now()      -- 갱신 시각
);
-- 사용자별 활성 로드맵 빠른 조회
CREATE INDEX idx_user_roadmaps_active ON user_roadmaps(user_id) WHERE is_active = true;

-- 로드맵 하위 퀘스트 트리 (자기참조 parent_quest_id)
CREATE TABLE roadmap_quests (
    id BIGSERIAL PRIMARY KEY,                 -- 퀘스트 PK
    roadmap_id BIGINT NOT NULL REFERENCES user_roadmaps(id) ON DELETE CASCADE, -- 소속 로드맵
    parent_quest_id BIGINT REFERENCES roadmap_quests(id), -- 부모 퀘스트(루트는 NULL)

    title VARCHAR(255) NOT NULL,              -- 퀘스트 제목
    description TEXT,                         -- 퀘스트 설명
    difficulty VARCHAR(20) NOT NULL,          -- 입문/중급/심화
    status VARCHAR(20) NOT NULL DEFAULT 'locked', -- locked/available/active/done
    tags JSONB,                               -- 해시태그 배열

    sort_order INT DEFAULT 0,                 -- 동일 레벨 정렬
    created_at TIMESTAMPTZ DEFAULT now(),     -- 생성 시각
    updated_at TIMESTAMPTZ DEFAULT now()      -- 갱신 시각
);
CREATE INDEX idx_roadmap_quests_roadmap ON roadmap_quests(roadmap_id);
CREATE INDEX idx_roadmap_quests_parent ON roadmap_quests(parent_quest_id);

-- 성장 아카이브(일별 로그, 캘린더 점 표시)
CREATE TABLE growth_daily_logs (
    id BIGSERIAL PRIMARY KEY,                 -- 일별 로그 PK
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE, -- 사용자 FK
    log_date DATE NOT NULL,                   -- 기준 일자

    completed_quest_ids JSONB DEFAULT '[]'::jsonb, -- 완료 퀘스트 ID 배열
    learned_note TEXT,                        -- 마크다운 로그 원문

    created_at TIMESTAMPTZ DEFAULT now(),     -- 생성 시각
    updated_at TIMESTAMPTZ DEFAULT now(),     -- 갱신 시각
    UNIQUE (user_id, log_date)                -- 1일 1로그
);
CREATE INDEX idx_growth_logs_user_date ON growth_daily_logs(user_id, log_date DESC);
```

### 6.6 Coach(AI 코치) 탭

```sql
-- 코치 세션 (활성 컨텍스트 포함)
CREATE TABLE coach_sessions (
    id BIGSERIAL PRIMARY KEY,                 -- 코치 세션 PK
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE, -- 사용자 FK

    context_type VARCHAR(20) NOT NULL,        -- ROADMAP / CHANCE / GENERAL
    context_id BIGINT,                         -- 연결 대상 ID(퀘스트/찬스 등)

    context_title VARCHAR(255),               -- ACTIVE CONTEXT 제목
    context_description TEXT,                 -- ACTIVE CONTEXT 설명
    context_tags JSONB,                       -- ACTIVE CONTEXT 태그 배열

    is_active BOOLEAN DEFAULT TRUE,           -- 활성 세션 여부
    created_at TIMESTAMPTZ DEFAULT now(),     -- 생성 시각
    updated_at TIMESTAMPTZ DEFAULT now()      -- 갱신 시각
);
CREATE INDEX idx_coach_sessions_user ON coach_sessions(user_id) WHERE is_active = true;

-- 코치 대화 메시지 (좌측 인터랙티브 캔버스)
CREATE TABLE coach_messages (
    id BIGSERIAL PRIMARY KEY,                 -- 메시지 PK
    session_id BIGINT NOT NULL REFERENCES coach_sessions(id) ON DELETE CASCADE, -- 세션 FK

    role VARCHAR(20) NOT NULL,                -- user / assistant / system
    content TEXT NOT NULL,                    -- 마크다운 본문

    badge_label VARCHAR(50),                  -- 배지 라벨(예: 로드맵 연계 질문)
    code_snippet TEXT,                        -- 코드 블록 분리 저장
    attached_context JSONB,                   -- 입력 시 동봉된 맥락 정보

    created_at TIMESTAMPTZ DEFAULT now()      -- 생성 시각
);
CREATE INDEX idx_coach_messages_session ON coach_messages(session_id, created_at ASC);

-- 인사이트 지갑 (우측 Wallet 패널)
CREATE TABLE insight_wallets (
    id BIGSERIAL PRIMARY KEY,                 -- 지갑 아이템 PK
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE, -- 사용자 FK
    source_message_id BIGINT REFERENCES coach_messages(id) ON DELETE SET NULL, -- 출처 메시지

    item_type VARCHAR(20) NOT NULL,           -- TEXT / CODE / LINK / PROMPT
    title VARCHAR(255),                       -- 지갑 아이템 제목
    content TEXT NOT NULL,                    -- 저장 콘텐츠(문장/코드)
    tags JSONB,                               -- 태그 배열

    is_used_in_archive BOOLEAN DEFAULT FALSE, -- 로드맵 아카이브 반영 여부
    created_at TIMESTAMPTZ DEFAULT now()      -- 생성 시각
);
CREATE INDEX idx_insight_wallets_user ON insight_wallets(user_id, created_at DESC);
```

코치 워크플로우(요약):
1. 로드맵/찬스에서 코치 진입 시 `coach_sessions`를 열고 `context_*` 스냅샷 저장  
2. 대화 턴은 `coach_messages`에 누적(배지/코드/첨부 컨텍스트 포함)  
3. 지갑 저장 액션 시 `insight_wallets`에 upsert/insert  
4. 이후 로드맵 아카이브 반영 시 `is_used_in_archive`로 사용 여부 추적

---

## 7) Consult / Profile / Competency

> 🔴 **이 절 전체가 목표 모델(물리 미존재)이다.** `consultation_*`·`user_personas`·`user_competencies`는 `9f2a6d4e1b0c` reset 이후 한 번도 생성된 적이 없다(§0 참조).

```sql
CREATE TYPE consultation_session_status AS ENUM ('active', 'completed', 'abandoned');

CREATE TABLE consultation_sessions (
    id UUID PRIMARY KEY,                       -- 세션 PK
    user_id UUID NOT NULL REFERENCES users(id), -- 사용자 FK
    current_graph_node VARCHAR(80) NOT NULL,  -- 현재 LangGraph 노드
    graph_name VARCHAR(80),                    -- 그래프 식별자
    graph_state_version INT NOT NULL DEFAULT 1, -- 그래프 버전
    session_status consultation_session_status NOT NULL, -- active/completed/abandoned
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(), -- 시작 시각
    ended_at TIMESTAMPTZ,                      -- 종료 시각
    last_turn_at TIMESTAMPTZ,                  -- 마지막 턴 시각
    metadata JSONB                             -- 부가 메타데이터
);

CREATE TABLE consultation_turns (
    id UUID PRIMARY KEY,                       -- 턴 PK
    session_id UUID NOT NULL REFERENCES consultation_sessions(id) ON DELETE CASCADE, -- 세션 FK
    turn_index INT NOT NULL,                   -- 세션 내 턴 순번
    ai_question TEXT NOT NULL,                 -- AI 질문
    user_answer TEXT NOT NULL,                 -- 사용자 답변
    psych_analysis JSONB,                      -- 심리 분석 결과
    tech_analysis JSONB,                       -- 기술 역량 분석 결과
    routing_decision JSONB,                    -- 라우팅/분기 결정
    llm_reasoning TEXT,                        -- 내부 추론 근거
    model_name VARCHAR(120),                   -- 사용 모델명
    prompt_version VARCHAR(40),                -- 프롬프트 버전
    tokens_in INT,                             -- 입력 토큰 수
    tokens_out INT,                            -- 출력 토큰 수
    latency_ms INT,                            -- 응답 지연(ms)
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(), -- 생성 시각
    UNIQUE (session_id, turn_index)
);

CREATE TABLE user_personas (
    user_id UUID PRIMARY KEY REFERENCES users(id), -- 사용자 FK(PK)
    persona_summary TEXT NOT NULL,            -- 페르소나 요약
    values_score JSONB NOT NULL DEFAULT '{}'::jsonb, -- 가치관 점수 맵
    dominant_emotion VARCHAR(40),             -- 대표 감정
    signals JSONB,                            -- 보조 신호
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now() -- 갱신 시각
);

-- domain_id -> sectors.slug 로 정렬 (충돌 해소 포인트)
CREATE TABLE user_competencies (
    id UUID PRIMARY KEY,                       -- 역량 레코드 PK
    user_id UUID NOT NULL REFERENCES users(id), -- 사용자 FK
    sector_slug VARCHAR(50) NOT NULL REFERENCES sectors(slug), -- 섹터 FK
    skill_name VARCHAR(120) NOT NULL,          -- 역량명
    skill_level INT NOT NULL CHECK (skill_level BETWEEN 0 AND 100), -- 역량 점수
    evidence_log JSONB NOT NULL DEFAULT '[]'::jsonb, -- 근거 로그
    confidence NUMERIC(5,2),                   -- 신뢰도
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(), -- 갱신 시각
    UNIQUE (user_id, sector_slug, skill_name)
);
```

---

## 8) 폐기/이관 대상 (구버전 정리)

> ⚠️ **갱신(2026-06-24):** 아래 구버전 테이블은 `9f2a6d4e1b0c`(reset)가 이미 전부 DROP했다. 현 DB에 존재하지 않으므로 추가 drop 작업은 불필요하며, 이 목록은 과거 이력 참고용이다. 구 `user_competency`는 `BIGSERIAL`+`is_certified` 형태였고 `domain_id` 컬럼은 없었다(아래 표기 정정).

아래 구버전은 이 문서 기준에서 **폐기 또는 뷰/마이그레이션용 한시 유지** 대상입니다.

- `domains`
- `pulse_metrics`
- `causal_insights`
- `trend_keywords`
- `user_competencies.domain_id` (UUID FK 방식)

권장: 배포 시점에 `v_old_*` 백업 테이블로 rename 후 ETL 이관 완료 시 drop.

---

## 9) API 조회 기준 (권장)

- Pulse: `GET /pulse/*` → `pulse_metrics_log`, `trending_keywords`, `economic_briefings`, `causal_chains`, `crossover_metrics`
- Gap: `GET /gap/issues`, `GET /gap/issues/{id}` → `gap_issues`, `issue_evidences`
- Sync: `GET /sync/overview` → `sync_scores_daily`
- Chance: `GET /chance/opportunities`, `GET /chance/opportunities/{id}` → `chance_opportunities`, `user_chance_matches`
- Roadmap: `GET /roadmap/active`, `GET /roadmap/quests`, `PUT /roadmap/quests/{id}/status`, `PUT /roadmap/logs/{log_date}` → `user_roadmaps`, `roadmap_quests`, `growth_daily_logs`
- Coach: `POST /coach/sessions`, `GET /coach/sessions/{id}/messages`, `POST /coach/sessions/{id}/messages`, `POST /coach/wallet`, `GET /coach/wallet` → `coach_sessions`, `coach_messages`, `insight_wallets`
- Consult/Profile: `consultation_*`, `user_personas`, `user_competencies`

---

문서 버전: v2.9  
최종 업데이트: 2026-06-26 (v2.9 — §0 마이그레이션 정합 갱신: 파일 head `b8e4c2a6f1d9`, 인사이트 6수직 Silver/Gold 정의 반영, 미문서 테이블 2종·런타임 산출 2종 명시)
마이그레이션 파일 head: `b8e4c2a6f1d9` (Neon 적용은 `alembic current` 확인 필요)
이전: v2.8 (2026-06-24, P0 개정 — `e2c5a7b9d3f4`) · v2.7 (2026-06-12, 결함 A·B·C·D — `d7f3a9c1e5b2`)
