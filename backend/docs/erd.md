# Pulse Domain ERD (PostgreSQL + FastAPI/SQLAlchemy)

## 목적
- 실시간 펄스 대시보드에서 사용하는 산업/테마(도메인) 기준 데이터를 일관되게 저장/조회하기 위한 DB 스키마 정의
- 프론트 시각화(속도계, 매트릭스, 인과관계 체인, 키워드)를 동일한 데이터 축으로 연결

---

## 1) 도메인 분류 체계 (v1)
1. AI & Data (지능형 기술)
2. Sustainability & ESG (지속 가능성)
3. Future Finance (미래 금융)
4. Bio & Health-Tech (웰니스)
5. Smart Manufacturing (지능형 제조)
6. Next-Gen Media (콘텐츠/IP)

> 메모: 분류는 고정값이 아니라 버전 관리되는 taxonomy입니다.  
> 운영 중 변경 가능하며, 변경 시 `slug`는 최대한 안정적으로 유지합니다.

---

## 2) ERD 개요

```text
domains (1) ───< pulse_metrics (N)
   │
   ├────< causal_insights (N)  [primary_domain_id]
   │
   └────< trend_keywords (N)

users (1) ───< consultation_sessions (N) ───< consultation_turns (N)
   │
   ├────(0..1) user_personas (1)  [user_id unique]
   │
   └────< user_competencies (N)  [domain_id -> domains(id)]
```

---

## 3) 테이블 정의

## 3.1 `domains` (도메인 마스터)
시스템 전역에서 참조하는 산업/테마 기준 테이블

- `id` UUID PK
- `name` VARCHAR(80) NOT NULL  -- 예: AI·데이터
- `slug` VARCHAR(80) NOT NULL UNIQUE  -- 예: ai-data
- `color_code` VARCHAR(16) NOT NULL  -- 예: #4F46E5
- `description` TEXT NULL
- `is_active` BOOLEAN NOT NULL DEFAULT TRUE
- `sort_order` INT NOT NULL DEFAULT 0
- `created_at` TIMESTAMPTZ NOT NULL DEFAULT now()
- `updated_at` TIMESTAMPTZ NOT NULL DEFAULT now()

권장 인덱스:
- `ux_domains_slug` UNIQUE (`slug`)
- `ix_domains_is_active_sort_order` (`is_active`, `sort_order`)

---

## 3.2 `pulse_metrics` (도메인별 속도/지수 시계열)
속도계, 매트릭스, Top 섹터 카드의 원천 데이터

- `id` UUID PK
- `domain_id` UUID NOT NULL FK -> `domains(id)`
- `speed_kmh` NUMERIC(6,2) NOT NULL  -- 0~200+ 확장 가능
- `status_label` VARCHAR(40) NOT NULL  -- 태풍급/급상승/상승/관찰 등
- `score_current` NUMERIC(5,2) NOT NULL  -- 0~100
- `score_previous` NUMERIC(5,2) NULL  -- 전일/전주 비교값
- `delta_pct` NUMERIC(6,2) NULL  -- 증감률(선계산 저장)
- `evidence_count` INT NOT NULL DEFAULT 0  -- 근거 데이터 수
- `recorded_at` TIMESTAMPTZ NOT NULL
- `created_at` TIMESTAMPTZ NOT NULL DEFAULT now()

권장 제약:
- CHECK (`score_current` >= 0 AND `score_current` <= 100)
- CHECK (`score_previous` IS NULL OR (`score_previous` >= 0 AND `score_previous` <= 100))

권장 인덱스:
- `ix_pulse_metrics_domain_recorded_at` (`domain_id`, `recorded_at` DESC)
- `ix_pulse_metrics_recorded_at` (`recorded_at` DESC)

---

## 3.3 `causal_insights` (인과관계 체인)
"거시 이벤트 -> 산업 영향 -> 청년 기회" 3단 흐름 저장

- `id` UUID PK
- `primary_domain_id` UUID NOT NULL FK -> `domains(id)`
- `macro_event` TEXT NOT NULL
- `industry_impact` TEXT NOT NULL
- `youth_opportunity` TEXT NOT NULL
- `confidence_score` NUMERIC(5,2) NULL  -- 0~100
- `is_active` BOOLEAN NOT NULL DEFAULT TRUE
- `effective_from` TIMESTAMPTZ NOT NULL DEFAULT now()
- `effective_to` TIMESTAMPTZ NULL
- `created_at` TIMESTAMPTZ NOT NULL DEFAULT now()
- `updated_at` TIMESTAMPTZ NOT NULL DEFAULT now()

권장 인덱스:
- `ix_causal_insights_domain_active` (`primary_domain_id`, `is_active`)
- `ix_causal_insights_effective` (`effective_from` DESC, `effective_to`)

---

## 3.4 `trend_keywords` (급상승 키워드)
키워드 클라우드/티커/도메인별 핫 토픽 표시에 사용

- `id` UUID PK
- `domain_id` UUID NOT NULL FK -> `domains(id)`
- `word` VARCHAR(120) NOT NULL
- `frequency_score` NUMERIC(8,3) NOT NULL  -- 가중 점수
- `source_count` INT NOT NULL DEFAULT 0  -- 출처 개수
- `rank_score` NUMERIC(8,3) NULL  -- 랭킹용 추가 지표
- `recorded_at` TIMESTAMPTZ NOT NULL
- `created_at` TIMESTAMPTZ NOT NULL DEFAULT now()

권장 제약:
- CHECK (`source_count` >= 0)

권장 인덱스:
- `ix_trend_keywords_domain_recorded_at` (`domain_id`, `recorded_at` DESC)
- `ix_trend_keywords_recorded_rank` (`recorded_at` DESC, `rank_score` DESC)
- `ux_trend_keywords_domain_word_recorded_at` UNIQUE (`domain_id`, `word`, `recorded_at`)

---

## 4) SQL DDL 예시 (초기 버전)

```sql
CREATE TABLE domains (
  id UUID PRIMARY KEY,
  name VARCHAR(80) NOT NULL,
  slug VARCHAR(80) NOT NULL UNIQUE,
  color_code VARCHAR(16) NOT NULL,
  description TEXT,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  sort_order INT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE pulse_metrics (
  id UUID PRIMARY KEY,
  domain_id UUID NOT NULL REFERENCES domains(id),
  speed_kmh NUMERIC(6,2) NOT NULL,
  status_label VARCHAR(40) NOT NULL,
  score_current NUMERIC(5,2) NOT NULL CHECK (score_current >= 0 AND score_current <= 100),
  score_previous NUMERIC(5,2) CHECK (score_previous >= 0 AND score_previous <= 100),
  delta_pct NUMERIC(6,2),
  evidence_count INT NOT NULL DEFAULT 0,
  recorded_at TIMESTAMPTZ NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE causal_insights (
  id UUID PRIMARY KEY,
  primary_domain_id UUID NOT NULL REFERENCES domains(id),
  macro_event TEXT NOT NULL,
  industry_impact TEXT NOT NULL,
  youth_opportunity TEXT NOT NULL,
  confidence_score NUMERIC(5,2),
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  effective_from TIMESTAMPTZ NOT NULL DEFAULT now(),
  effective_to TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE trend_keywords (
  id UUID PRIMARY KEY,
  domain_id UUID NOT NULL REFERENCES domains(id),
  word VARCHAR(120) NOT NULL,
  frequency_score NUMERIC(8,3) NOT NULL,
  source_count INT NOT NULL DEFAULT 0 CHECK (source_count >= 0),
  rank_score NUMERIC(8,3),
  recorded_at TIMESTAMPTZ NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (domain_id, word, recorded_at)
);
```

---

## 5) 데이터 매칭 파이프라인 (개념)
1. 수집: 뉴스/공고/검색량/투자 데이터 수집
2. 분류: 원천 텍스트를 도메인 taxonomy(`domains.slug`)로 매핑
3. 계산: 도메인별 속도/점수/증감률 계산 -> `pulse_metrics` 저장
4. 추론: 대표 인과관계 1~N개 생성 -> `causal_insights` 저장
5. 키워드: 급상승 키워드 랭킹 -> `trend_keywords` 저장
6. 출력: 프론트는 최신 `recorded_at` 기준으로 조회하여 렌더링

---

## 6) API 조회 기준 (권장)
- `/pulse/summary`: `pulse_metrics` 최신 집계
- `/pulse/matrix`: `domains` x `pulse_metrics` 상태 축 변환 데이터
- `/pulse/causal-chain`: `causal_insights`의 `is_active = true`
- `/pulse/ticker` / `/pulse/keywords`: `trend_keywords` 최신 랭킹

---

## 7) 운영 메모
- 도메인 taxonomy 변경 시 `slug`는 안정 유지, `name`/`description`만 변경 권장
- `recorded_at`는 UTC 기준 저장, 프론트에서 로컬 타임존 변환
- 초기에는 배치(예: 10~30분) 업데이트, 이후 스트리밍/이벤트 기반 확장 가능

---

## 8) AI 상담실(Consult) — LangGraph 턴/라우팅/누적 프로필

> 목적: **대화 1턴(Turn)마다** 심리/역량/라우팅 메타를 정밀 저장하고, 누적하여 **페르소나/역량**을 갱신한다.  
> 전제: `user_id`는 기존 인증/유저 테이블(예: `users`)에 FK로 연결한다. (이 문서는 `users` DDL을 중복 정의하지 않음)

### 8.1 `consultation_sessions` (상담 세션)
- `id` UUID PK
- `user_id` UUID NOT NULL FK -> `users(id)`
- `current_graph_node` VARCHAR(80) NOT NULL  -- LangGraph node id (예: `value_dialog`, `tech_interview`)
- `graph_name` VARCHAR(80) NULL  -- 그래프 식별(여러 그래프 운용 시)
- `graph_state_version` INT NOT NULL DEFAULT 1  -- 그래프/스키마 마이그레이션 대비
- `session_status` consultation_session_status NOT NULL  -- `active` | `completed` | `abandoned`
- `started_at` TIMESTAMPTZ NOT NULL DEFAULT now()
- `ended_at` TIMESTAMPTZ NULL
- `last_turn_at` TIMESTAMPTZ NULL
- `metadata` JSONB NULL  -- 클라이언트 컨텍스트(디바이스, 실험 플래그 등)

권장 인덱스:
- `ix_consultation_sessions_user_started_at` (`user_id`, `started_at` DESC)
- `ix_consultation_sessions_status` (`session_status`, `last_turn_at` DESC)

### 8.2 `consultation_turns` (대화 턴 + 실시간 분석)
- `id` UUID PK
- `session_id` UUID NOT NULL FK -> `consultation_sessions(id)` ON DELETE CASCADE
- `turn_index` INT NOT NULL  -- 0-base 또는 1-base 중 하나로 표준 고정
- `ai_question` TEXT NOT NULL
- `user_answer` TEXT NOT NULL
- `psych_analysis` JSONB NULL  -- 감정/가치/고민 등
- `tech_analysis` JSONB NULL  -- 스택/깊이/도메인 신호 등
- `routing_decision` JSONB NULL  -- 다음 노드/난이도/분기 정보
- `llm_reasoning` TEXT NULL  -- 디버깅용 근거
- `model_name` VARCHAR(120) NULL
- `prompt_version` VARCHAR(40) NULL
- `tokens_in` INT NULL
- `tokens_out` INT NULL
- `latency_ms` INT NULL
- `created_at` TIMESTAMPTZ NOT NULL DEFAULT now()

권장 제약:
- UNIQUE (`session_id`, `turn_index`)

권장 인덱스:
- `ix_consultation_turns_session_turn` (`session_id`, `turn_index`)
- (선택) GIN (`psych_analysis`) / GIN (`tech_analysis`) / GIN (`routing_decision`) — 검색 패턴이 생기면 추가

### 8.3 `user_personas` (누적 성향/가치관 요약)
- `user_id` UUID PK FK -> `users(id)`
- `persona_summary` TEXT NOT NULL
- `values_score` JSONB NOT NULL DEFAULT '{}'::jsonb
- `dominant_emotion` VARCHAR(40) NULL
- `signals` JSONB NULL  -- 부가 요약(키워드, 리스크 등)
- `updated_at` TIMESTAMPTZ NOT NULL DEFAULT now()

### 8.4 `user_competencies` (누적 역량/기술)
- `id` UUID PK
- `user_id` UUID NOT NULL FK -> `users(id)`
- `domain_id` UUID NOT NULL FK -> `domains(id)`
- `skill_name` VARCHAR(120) NOT NULL
- `skill_level` INT NOT NULL  -- 0~100
- `evidence_log` JSONB NOT NULL DEFAULT '[]'::jsonb  -- turn id 목록/근거 스니펫 등
- `confidence` NUMERIC(5,2) NULL  -- 0~100
- `updated_at` TIMESTAMPTZ NOT NULL DEFAULT now()

권장 제약:
- CHECK (`skill_level` >= 0 AND `skill_level` <= 100)
- UNIQUE (`user_id`, `domain_id`, `skill_name`)

권장 인덱스:
- `ix_user_competencies_user_domain` (`user_id`, `domain_id`)

### 8.5 Enum
```sql
CREATE TYPE consultation_session_status AS ENUM ('active', 'completed', 'abandoned');
```

### 8.6 SQL DDL 예시 (Consult)

```sql
CREATE TABLE consultation_sessions (
  id UUID PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES users(id),
  current_graph_node VARCHAR(80) NOT NULL,
  graph_name VARCHAR(80),
  graph_state_version INT NOT NULL DEFAULT 1,
  session_status consultation_session_status NOT NULL,
  started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  ended_at TIMESTAMPTZ,
  last_turn_at TIMESTAMPTZ,
  metadata JSONB
);

CREATE TABLE consultation_turns (
  id UUID PRIMARY KEY,
  session_id UUID NOT NULL REFERENCES consultation_sessions(id) ON DELETE CASCADE,
  turn_index INT NOT NULL,
  ai_question TEXT NOT NULL,
  user_answer TEXT NOT NULL,
  psych_analysis JSONB,
  tech_analysis JSONB,
  routing_decision JSONB,
  llm_reasoning TEXT,
  model_name VARCHAR(120),
  prompt_version VARCHAR(40),
  tokens_in INT,
  tokens_out INT,
  latency_ms INT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (session_id, turn_index)
);

CREATE TABLE user_personas (
  user_id UUID PRIMARY KEY REFERENCES users(id),
  persona_summary TEXT NOT NULL,
  values_score JSONB NOT NULL DEFAULT '{}'::jsonb,
  dominant_emotion VARCHAR(40),
  signals JSONB,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE user_competencies (
  id UUID PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES users(id),
  domain_id UUID NOT NULL REFERENCES domains(id),
  skill_name VARCHAR(120) NOT NULL,
  skill_level INT NOT NULL CHECK (skill_level >= 0 AND skill_level <= 100),
  evidence_log JSONB NOT NULL DEFAULT '[]'::jsonb,
  confidence NUMERIC(5,2),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (user_id, domain_id, skill_name)
);
```

### 8.7 API 초안 (권장)
- `POST /consult/sessions` — 세션 생성
- `POST /consult/sessions/{session_id}/turns` — 턴 append + 분석/라우팅 저장
- `GET /consult/sessions/{session_id}` — 세션 + 최근 턴 요약
- `GET /profile/persona` — `user_personas`
- `GET /profile/competencies` — `user_competencies`

---

문서 버전: v1.1  
최종 업데이트: 2026-04-28
