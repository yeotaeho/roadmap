# Unified ERD (Medallion + App Domains)

이 문서는 기존 `erd.md`의 중복/충돌(`domains` vs `sectors`, 구버전 Pulse 테이블 중복, FK 방향 불일치, `users` DDL 누락)을 정리한 **최종 통합본**입니다.

- 기준 마스터는 `sectors(slug)`로 단일화
- Pulse/Gap은 메달리온 아키텍처(Bronze/Silver/Gold) 기준
- Consult/Coach/Sync도 동일 기준(`user_id`, `sector_slug`)으로 연결

---

## 1) 핵심 설계 원칙

1. **마스터 단일화**: 산업 기준은 `sectors.slug` 하나만 사용  
2. **Bronze 불변**: 원천 수집 테이블은 가급적 변경하지 않음  
3. **Silver 확장**: AI 추론/정제 결과는 도메인별 Silver 테이블로 분리  
4. **Gold 서빙 전용**: 앱/웹 UI는 Gold 테이블만 조회  
5. **데이터 리니지 보존**: Silver/Gold에서 `raw_table_ref`, `raw_id`로 역추적 가능

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

---

## 4) Bronze Layer (원천 수집)

```sql
CREATE TABLE raw_economic_data (
    id BIGSERIAL PRIMARY KEY,                 -- 원천 데이터 PK
    source_type VARCHAR(50) NOT NULL,        -- VC, ETF, Govt_Budget 등
    source_url VARCHAR(255),                  -- 원문/출처 URL
    target_company_or_fund VARCHAR(100),      -- 투자 대상 기업/펀드
    investment_amount BIGINT,                 -- 투자/유입 금액
    collected_at TIMESTAMPTZ DEFAULT now()    -- 수집 시각
);

CREATE TABLE raw_innovation_data (
    id BIGSERIAL PRIMARY KEY,                 -- 원천 데이터 PK
    source_type VARCHAR(50) NOT NULL,        -- Patent, arXiv, GitHub 등
    title VARCHAR(255) NOT NULL,              -- 문서/리포트 제목
    abstract_text TEXT,                       -- 요약/본문 일부
    published_at DATE,                        -- 원문 발행일
    collected_at TIMESTAMPTZ DEFAULT now()    -- 수집 시각
);

CREATE TABLE raw_people_data (
    id BIGSERIAL PRIMARY KEY,                 -- 원천 데이터 PK
    source_type VARCHAR(50) NOT NULL,        -- GoogleTrends, LinkedIn 등
    keyword_or_job VARCHAR(100) NOT NULL,     -- 검색 키워드/채용 직무
    search_volume_or_count INT,               -- 검색량/건수
    collected_at TIMESTAMPTZ DEFAULT now()    -- 수집 시각
);

CREATE TABLE raw_discourse_data (
    id BIGSERIAL PRIMARY KEY,                 -- 원천 데이터 PK
    source_type VARCHAR(50) NOT NULL,        -- Reuters, Reddit, McKinsey 등
    headline VARCHAR(255) NOT NULL,           -- 헤드라인
    content_body TEXT,                        -- 본문 전문/요약 본문
    published_at TIMESTAMPTZ,                 -- 원문 발행 시각
    collected_at TIMESTAMPTZ DEFAULT now()    -- 수집 시각
);

-- Chance 원천 수집 (채용/부트캠프/공모전/지원사업)
CREATE TABLE raw_opportunity_data (
    id BIGSERIAL PRIMARY KEY,                 -- 원천 데이터 PK
    source_type VARCHAR(50) NOT NULL,         -- JOB / BOOTCAMP / CONTEST / GRANT
    source_url VARCHAR(500) NOT NULL,         -- 원본 공고 링크
    host_name VARCHAR(150),                   -- 주최/주관 기관 또는 기업명
    raw_title VARCHAR(255) NOT NULL,          -- 원문 제목
    raw_content TEXT,                         -- 원문 본문
    collected_at TIMESTAMPTZ DEFAULT now()    -- 수집 시각
);
```

---

## 5) Silver Layer (AI 정제/추론)

```sql
-- Pulse 분석용 Silver
CREATE TABLE refined_trend_insights (
    id BIGSERIAL PRIMARY KEY,                 -- Silver 레코드 PK
    raw_table_ref VARCHAR(50) NOT NULL,       -- 원천 테이블명
    raw_id BIGINT NOT NULL,                   -- 원천 레코드 PK
    sector_slug VARCHAR(50) REFERENCES sectors(slug), -- AI 분류 섹터
    sub_sector_id BIGINT REFERENCES sub_sectors(id),  -- AI 분류 세부 섹터
    sentiment_score FLOAT,                    -- -1.0 ~ 1.0
    impact_score INT,                         -- 영향도 점수
    extracted_keywords JSONB,                 -- 배열
    processed_at TIMESTAMPTZ DEFAULT now()    -- 분석 완료 시각
);
CREATE INDEX idx_refined_trend_sector ON refined_trend_insights(sector_slug);
CREATE INDEX idx_refined_trend_raw ON refined_trend_insights(raw_table_ref, raw_id);

-- Gap 분석용 Silver
CREATE TABLE refined_gap_insights (
    id BIGSERIAL PRIMARY KEY,                 -- Silver 레코드 PK
    raw_table_ref VARCHAR(50) NOT NULL,       -- 원천 테이블명
    raw_id BIGINT NOT NULL,                   -- 원천 레코드 PK
    sector_slug VARCHAR(50) REFERENCES sectors(slug), -- 관련 섹터
    extracted_problem TEXT NOT NULL,
    extracted_opportunity TEXT NOT NULL,
    processed_at TIMESTAMPTZ DEFAULT now()    -- 분석 완료 시각
);
CREATE INDEX idx_refined_gap_sector ON refined_gap_insights(sector_slug);
CREATE INDEX idx_refined_gap_raw ON refined_gap_insights(raw_table_ref, raw_id);

-- Chance 분석용 Silver
CREATE TABLE refined_chance_insights (
    id BIGSERIAL PRIMARY KEY,                 -- Silver 레코드 PK
    raw_table_ref VARCHAR(50) NOT NULL DEFAULT 'raw_opportunity_data', -- 원천 테이블명
    raw_id BIGINT NOT NULL,                   -- 원천 레코드 PK
    sector_slug VARCHAR(50) REFERENCES sectors(slug), -- AI 판별 매칭 섹터
    extracted_type VARCHAR(50) NOT NULL,      -- 채용/부트캠프/공모전/지원금 분류
    extracted_target JSONB,                   -- 지원 대상 목록(JSON 배열)
    extracted_benefits JSONB,                 -- 혜택/보상 목록(JSON 배열)
    extracted_deadline DATE,                  -- 마감일
    extracted_qualifications JSONB,           -- 자격 요건 목록(JSON 배열)
    processed_at TIMESTAMPTZ DEFAULT now()    -- 분석 완료 시각
);
CREATE INDEX idx_refined_chance_sector ON refined_chance_insights(sector_slug);
CREATE INDEX idx_refined_chance_raw ON refined_chance_insights(raw_table_ref, raw_id);
```

---

## 6) Gold Layer (UI 서빙)

### 6.1 Pulse 탭

```sql
CREATE TABLE pulse_metrics_log (
    id BIGSERIAL PRIMARY KEY,                 -- Gold 레코드 PK
    sector_slug VARCHAR(50) NOT NULL REFERENCES sectors(slug), -- 집계 섹터
    sub_sector_id BIGINT REFERENCES sub_sectors(id), -- 세부 섹터(옵션)
    recorded_date DATE NOT NULL,              -- 차트 X축 날짜
    score INT NOT NULL CHECK (score BETWEEN 0 AND 100),
    status_badge VARCHAR(20) NOT NULL,        -- 태풍급/급상승 등
    momentum_pct DECIMAL(5,2),                -- 증감률(%)
    created_at TIMESTAMPTZ DEFAULT now()      -- 적재 시각
);
CREATE INDEX idx_pulse_metrics_date_sector ON pulse_metrics_log(recorded_date, sector_slug);

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

문서 버전: v2.6  
최종 업데이트: 2026-05-05
