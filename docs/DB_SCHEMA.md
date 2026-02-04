# 📊 데이터베이스 스키마 설계

## 1. 개요

본 프로젝트는 PostgreSQL을 사용하며, JSONB와 VECTOR 타입을 활용한 유연한 스키마 설계를 채택했습니다.

## 2. 핵심 테이블

### 2.1. `users` (사용자 프로필)

**목적**: OAuth 인증 및 사용자 기본 정보 관리

```sql
CREATE TABLE users (
    id BIGSERIAL PRIMARY KEY,
    provider VARCHAR(20) NOT NULL,              -- OAuth 제공자 (google, kakao, naver)
    provider_id VARCHAR(100) NOT NULL,          -- 제공자별 고유 ID
    email VARCHAR(100),
    name VARCHAR(100),
    nickname VARCHAR(100),
    profile_image VARCHAR(500),
    age INTEGER,
    pref_domain_json JSONB,                     -- 선호 도메인 JSON {"interests": ["economy"], "custom": ["AI"]}
    value_growth FLOAT,                         -- 성장 지향성 (0~1)
    value_stability FLOAT,                      -- 안정성 선호 (0~1)
    value_impact FLOAT,                         -- 영향력 가치 (0~1)
    role VARCHAR(20) DEFAULT 'USER',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(provider, provider_id)
);

CREATE INDEX idx_users_provider_provider_id ON users(provider, provider_id);
CREATE INDEX idx_users_pref_domain ON users USING GIN(pref_domain_json);
```

**주요 특징**:
- `pref_domain_json`: JSONB 타입으로 유연한 관심사 관리
- `value_*`: AI 분석을 위한 가치관 점수
- 향후 `persona_vector VECTOR(1536)` 컬럼 추가 예정

### 2.2. `user_competency` (사용자 역량)

**목적**: 사용자의 보유 역량 및 숙련도 관리

```sql
CREATE TABLE user_competency (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    skill_name VARCHAR(100) NOT NULL,           -- 스킬명 (Python, 기획 등)
    skill_level INTEGER NOT NULL,               -- 숙련도 (1~5) - 역량 갭(Gap) 분석
    is_certified BOOLEAN DEFAULT FALSE,         -- 자격/경험 여부 - 데이터 신뢰도 보정
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_user_competency_user_id ON user_competency(user_id);
CREATE INDEX idx_user_competency_user_skill ON user_competency(user_id, skill_name);
```

**활용 목적**:
- 역량 갭(Gap) 분석: 목표 트렌드에 필요한 역량과 현재 역량 비교
- 학습 로드맵 생성: 부족한 역량을 보완할 수 있는 학습 경로 제시

### 2.3. `user_roadmap_status` (사용자 로드맵 진행 상태)

**목적**: 사용자의 학습 로드맵 진행 상황 추적

```sql
CREATE TABLE user_roadmap_status (
    roadmap_id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    target_trend_id INTEGER,                    -- 목표로 삼은 트렌드 ID (trends 테이블 생성 후 ForeignKey 추가 예정)
    progress_rate FLOAT DEFAULT 0.0 NOT NULL,  -- 학습 진척도 (0~100) - AI 코치의 피드백 근거
    last_active_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(), -- 최종 활동 시간 - 리마인드 알림 시점 계산
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_user_roadmap_user_id ON user_roadmap_status(user_id);
CREATE INDEX idx_user_roadmap_last_active ON user_roadmap_status(last_active_at);
CREATE INDEX idx_user_roadmap_user_trend ON user_roadmap_status(user_id, target_trend_id);
```

**활용 목적**:
- AI 코치 피드백: 진척도에 따른 맞춤형 조언 제공
- 리마인드 알림: 학습 이탈 방지를 위한 알림 시점 계산

### 2.4. `external_trend_data` (외부 트렌드 데이터) - 예정

**목적**: 수집된 선행 지표 원본 및 계산된 Velocity Score 저장

```sql
CREATE TABLE external_trend_data (
    trend_id SERIAL PRIMARY KEY,
    trend_name VARCHAR(200) NOT NULL,
    category VARCHAR(100),                     -- 분야 (AI, 경제, 기술 등)
    
    -- 선행 지표 원본 데이터
    funding_volume_growth FLOAT,               -- 투자금 유입 증가율
    patent_filing_rate FLOAT,                  -- 특허 출원 증가율
    learning_demand_growth FLOAT,              -- 학습 콘텐츠 수요 증가율
    search_volume_growth FLOAT,                -- 검색량 증가율
    policy_change_frequency INTEGER,           -- 정책/규제 변화 빈도
    
    -- 계산된 지표
    velocity_score FLOAT,                      -- 최종 트렌드 속도 점수
    opportunity_level INTEGER,                 -- 기회 수준 (1~5)
    
    -- 벡터 임베딩 (향후 추가)
    trend_vector VECTOR(1536),                 -- 트렌드 벡터 (사용자 매칭용)
    
    collected_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_trend_category ON external_trend_data(category);
CREATE INDEX idx_trend_velocity ON external_trend_data(velocity_score DESC);
-- CREATE INDEX idx_trend_vector ON external_trend_data USING ivfflat(trend_vector vector_cosine_ops); -- pgvector 확장 필요
```

## 3. 확장 계획

### 3.1. 벡터 검색 지원

**pgvector 확장**:
```sql
CREATE EXTENSION IF NOT EXISTS vector;

-- 사용자 persona_vector 추가
ALTER TABLE users ADD COLUMN persona_vector VECTOR(1536);

-- 벡터 인덱스 생성
CREATE INDEX idx_users_persona_vector ON users 
USING ivfflat(persona_vector vector_cosine_ops) 
WITH (lists = 100);
```

### 3.2. 트렌드 테이블

**`trends` 테이블 생성** (향후):
```sql
CREATE TABLE trends (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    category VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
```

## 4. 데이터 타입 선택 이유

### 4.1. JSONB

**장점**:
- 유연한 스키마: 관심사나 설정 변경에 유연하게 대응
- 인덱싱 지원: GIN 인덱스로 빠른 검색 가능
- 쿼리 지원: JSONB 연산자로 복잡한 쿼리 가능

**사용 예시**:
```sql
-- 관심사가 "AI"인 사용자 검색
SELECT * FROM users 
WHERE pref_domain_json @> '{"interests": ["AI"]}';
```

### 4.2. VECTOR (pgvector)

**장점**:
- 벡터 유사도 검색: 코사인 유사도로 사용자-트렌드 매칭
- 인덱싱 지원: IVFFlat 인덱스로 빠른 검색
- AI 모델 통합: 임베딩 벡터를 직접 저장

**사용 예시**:
```sql
-- 사용자와 가장 유사한 트렌드 찾기
SELECT trend_name, 
       1 - (trend_vector <=> (SELECT persona_vector FROM users WHERE id = 1)) as similarity
FROM external_trend_data
ORDER BY trend_vector <=> (SELECT persona_vector FROM users WHERE id = 1)
LIMIT 3;
```

## 5. 인덱스 전략

### 5.1. 기본 인덱스

- **Primary Key**: 자동 인덱스 생성
- **Foreign Key**: 참조 무결성 보장
- **Unique Constraint**: 중복 방지

### 5.2. 성능 최적화 인덱스

- **복합 인덱스**: 자주 함께 조회되는 컬럼 조합
- **GIN 인덱스**: JSONB 컬럼 검색 최적화
- **벡터 인덱스**: 유사도 검색 최적화 (IVFFlat)

## 6. 마이그레이션 관리

- **Alembic** 사용: 버전 관리 및 자동 마이그레이션
- **비동기 지원**: asyncpg를 통한 비동기 쿼리
- **트랜잭션 관리**: 데이터 일관성 보장
