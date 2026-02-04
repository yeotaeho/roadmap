# 🏗️ AI 파이프라인 아키텍처 (4070Super 기반)

## 1. 하드웨어 환경

- **GPU**: RTX 4070 Super (VRAM 12GB)
- **최적화 전략**: QLoRA (4-bit Quantization)를 통한 효율적인 모델 학습

## 2. 언어 모델 (NLP)

### 2.1. 모델 선택

- **모델**: `Llama-3.1-8B-Korean-Bllossom` (HuggingFace)
- **선택 이유**:
  - 한국어 특화 모델
  - 8B 파라미터로 12GB VRAM에서 학습 가능
  - 오픈소스 라이선스

### 2.2. 튜닝 기법

**QLoRA (Quantized Low-Rank Adaptation)**
- 4-bit Quantization으로 메모리 사용량 최소화
- LoRA (Low-Rank Adaptation)로 효율적인 파인튜닝
- 12GB 환경에서 최적의 학습 효율 달성

**장점**:
- 전체 모델 파라미터를 학습하지 않고도 효과적인 튜닝 가능
- 학습 시간 단축
- 메모리 효율성 극대화

## 3. 예측 모델 (Time-Series)

### 3.1. 모델 선택

- **GRU (Gated Recurrent Unit)**: 시계열 데이터 학습에 적합
- **Time-Series Transformer**: 장기 의존성 학습에 우수 (대안)

### 3.2. 학습 데이터 구조

**Input (X)**: 현재 시점(t) 기준 과거 4주간의 5대 지표 데이터 시퀀스
- `funding_volume_growth` (돈의 흐름)
- `patent_filing_rate` (혁신의 흐름)
- `learning_demand_growth` (역량의 흐름)
- `search_volume_growth` (수요 포착)
- `policy_change_frequency` (안정성 측정)

**Target (Y)**: 미래 4주 후의 실제 계산된 `Velocity Score` 변화량

**Loss Function**: MSE (Mean Squared Error)

## 4. AI 서비스 로직 파이프라인

### 4.1. 온보딩 (Onboarding)

1. **회원가입 시 데이터 수집**:
   - 관심 분야 태그 선택
   - 역량 슬라이더 설정 (1~5점)
   - 기본 프로필 정보

2. **AI 코치와의 첫 대화**:
   - 주관식 질문을 통한 심층 가치관 추출
   - 사용자의 진로 고민, 목표, 가치관 파악

### 4.2. 데이터 처리

1. **대화 내용 분석**:
   - 4070 Super에서 QLoRA로 튜닝된 Llama 모델 사용
   - 대화 텍스트를 임베딩 벡터로 변환
   - `value_score` (성장 지향성, 안정성 선호 등) 추출
   - `persona_vector` (1536차원) 생성

2. **프로필 벡터 생성**:
   - 사용자의 관심사, 역량, 가치관을 종합한 벡터 생성
   - PostgreSQL의 `VECTOR` 타입으로 저장

### 4.3. 매칭 및 예측

1. **트렌드 예측**:
   - 과거 4주간의 지표 변화를 학습하여 미래 4주 후의 트렌드 변화 예측
   - GRU 또는 Time-Series Transformer 모델 활용

2. **코사인 유사도 계산**:
   - 사용자 벡터 (`persona_vector`)와 트렌드 벡터 간의 유사도 계산
   - 가장 관련성이 높은 트렌드 3가지 선별

3. **로드맵 큐레이션**:
   - 매칭된 트렌드에 필요한 핵심 역량 추천
   - 온라인 강의/도서 목록 연결
   - 학습 진척도 추적

## 5. 마이크로서비스 아키텍처

### 5.1. 서비스 구조

- Docker Compose 환경
- 마이크로서비스 기반 아키텍처

### 5.2. 주요 서비스

1. **OAuth Service**: 사용자 인증 및 프로필 관리
2. **News Service**: RSS 피드 수집 및 분석
3. **Trend Analysis Service**: 트렌드 데이터 수집 및 예측
4. **AI Service**: LLM 기반 대화 및 분석
5. **User Service**: 사용자 역량 및 로드맵 관리

## 6. 데이터 흐름

```
외부 API/RSS → 데이터 수집 서비스 → 전처리 → 
트렌드 분석 서비스 → 예측 모델 → Velocity Score 계산 →
사용자 매칭 서비스 → 로드맵 큐레이션 → 사용자 대시보드
```

## 7. 성능 최적화

### 7.1. 모델 최적화

- QLoRA를 통한 메모리 효율성
- 배치 처리로 학습 속도 향상
- 모델 캐싱으로 추론 속도 개선

### 7.2. 데이터베이스 최적화

- 벡터 인덱싱 (pgvector)으로 유사도 검색 최적화
- JSONB 인덱싱으로 유연한 데이터 쿼리
- 연결 풀링으로 동시성 처리

## 8. 향후 확장 계획

1. **Kubernetes 도입**: 프로덕션 환경 확장
2. **모델 업그레이드**: 더 큰 모델 또는 멀티모달 모델 검토
3. **실시간 스트리밍**: 실시간 트렌드 업데이트
4. **A/B 테스트**: 추천 알고리즘 개선
