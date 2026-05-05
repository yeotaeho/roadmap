# 인사이트 대시보드 플랫폼 백엔드 아키텍처 설계도 (v1)

이 문서는 현재 프로젝트(`backend/`)를 기준으로, 그동안 합의된 기술 의사결정을 **실행 가능한 백엔드 기준 아키텍처**로 정리한 문서입니다.  
목표는 “빠른 땜질 런칭”이 아니라, **1인 개발자가 끝까지 통제 가능한 구조 + 운영 가능한 품질**입니다.

---

## 1. 아키텍처 원칙

### 1.1 최상위 패턴
- **모듈러 모놀리스 (Modular Monolith)**: 배포 단위는 1개 API 애플리케이션(FastAPI), 내부는 도메인 단위로 격리
- **DDD-lite**: 전략적 설계(도메인 분리, 경계) 우선, 전술적 DDD는 과도하지 않게 적용
- **API-First + Async-First**: 비동기 I/O와 명확한 API 계약을 우선
- **Data-Centric AI**: 파인튜닝보다 데이터 파이프라인(Bronze/Silver/Gold) + RAG/Agent 품질로 승부

### 1.2 설계 우선순위
1. 유지보수성 (코드 경계, 문서, 테스트)
2. 운영 안정성 (관측성, 토큰/큐 관리, 백그라운드 분리)
3. 확장성 (특정 도메인 서비스 분리 가능)
4. 비용 효율 (단일 DB, Redis 재활용, 최소 운영 구성)

---

## 2. 시스템 구성 개요

## 2.1 런타임 구성요소
- `api`: FastAPI (동기화/조회/쓰기 API, SSE 스트리밍 엔드포인트)
- `worker`: Celery 또는 ARQ 워커 (무거운 AI/집계 작업)
- `redis`: 토큰 상태 저장 + 메시지 브로커
- `nginx`: 리버스 프록시, TLS 종료, 기본 보안 정책
- `postgresql(neon)`: 트랜잭션/분석/벡터(pgvector) 통합 저장소

### 2.2 요청 흐름
1. 클라이언트(Web/Flutter) -> `nginx`
2. `nginx` -> `api` (REST/SSE)
3. `api`는 즉시 처리 가능한 작업은 DB 직접 처리
4. 장기 작업은 Redis 큐로 enqueue 후 즉시 ACK
5. `worker`가 작업 수행 후 PostgreSQL 업데이트
6. 클라이언트는 폴링/SSE로 결과 반영

---

## 3. 코드베이스 구조 (권장)

```text
backend/
  api/
    routers/                 # FastAPI 라우터 (HTTP 경계)
    dependencies/            # 인증/권한/세션 의존성
    schemas/                 # pydantic DTO
  domain/
    auth/
    pulse/
    gap/
    sync/
    chance/
    roadmap/
    coach/
      application/           # use-case/service orchestration
      model/                 # SQLAlchemy models
      repository/            # DB 접근
      llm/                   # prompt, tool bindings
  data/
    pipelines/               # Bronze/Silver/Gold 배치 로직
    workers/                 # Celery/ARQ task entry
  alembic/
  main.py
```

도메인 간 호출 규칙:
- `router -> application service -> repository/model`
- 도메인 직접 import 최소화, 교차 접근은 application 계층에서 orchestration

---

## 4. 데이터 계층 전략

## 4.1 단일 DB 전략 (PostgreSQL + pgvector)
- 관계형 데이터 + 벡터를 분리하지 않고 PostgreSQL에서 통합 관리
- 장점:
  - 메타데이터 필터 + 유사도 검색을 SQL 한 번에 처리
  - 운영 복잡도(별도 Vector DB) 감소
  - 백업/복구/권한 모델 단일화

### 4.2 메달리온 아키텍처
- **Bronze**: 원천 수집(`raw_*`)
- **Silver**: AI 정제/추론(`refined_*`)
- **Gold**: UI 서빙(`*_log`, `*_issues`, `chance_opportunities`, `sync_scores_daily`, `coach_*`, `roadmap_*`)

`backend/docs/erd.md`를 스키마 단일 진실(SSOT)로 사용

### 4.3 마이그레이션
- Alembic으로 모든 변경 관리
- 규칙:
  - 수동 DDL 금지 (운영 DB 직접 변경 금지)
  - 모든 스키마 변경은 migration + 롤백 경로 포함
  - 배포 전 `alembic upgrade head` dry-run 검증

---

## 5. 인증/인가/보안

## 5.1 인증 방식
- 로컬 계정 + OAuth(Google/Kakao) 혼합
- `users.auth_provider`, `provider_id`로 계정 계보 관리

### 5.2 토큰 전략
- Access Token: 짧은 TTL(예: 15분)
- Refresh Token: Redis에 stateful 저장 후 회수(revoke) 가능하게 관리

### 5.3 전송/저장 보안
- 토큰은 `HttpOnly`, `Secure`, `SameSite` 쿠키 우선
- LocalStorage 토큰 저장 지양
- 비밀번호/민감 데이터는 해시/암호화

### 5.4 네트워크 경계
- Nginx에서:
  - TLS termination
  - Rate limit (IP/경로 기준)
  - 기본 보안 헤더
  - 허용 CORS origin 제한

---

## 6. AI/LLM 인텔리전스 레이어

## 6.1 모델 역할 분리
- **추론/대화(코치/로드맵 생성)**: 고품질 장문 추론 모델
- **실시간 탐색/수집**: 외부 검색 특화 모델/도구
- **임베딩**: 고정 임베딩 모델(`text-embedding-3-large` 계열)

### 6.2 오케스트레이션
- LangGraph `StateGraph` 기반, Router 중심 **Star Topology**
- 노드 예:
  - `PulseAnalyzer`
  - `GapIssueAnalyst`
  - `ChanceMatcher`
  - `RoadmapPlanner`
  - `CoachMentor`

### 6.3 도구 연동
- FastMCP 기반 Tool 노출
- 원칙:
  - Tool은 idempotent/read-only 우선
  - write tool은 권한/감사 로그 필수
  - DB 직접 write보다 application service 경유

### 6.4 스트리밍
- FastAPI `StreamingResponse` + SSE
- 코치 채팅/로드맵 생성 진행률에 적용
- fallback: 스트리밍 실패 시 일반 응답 모드 자동 전환

---

## 7. 백그라운드 작업 아키텍처

## 7.1 분리 대상
- 뉴스/공고 수집
- 대량 문서 파싱/임베딩
- 자정 배치 집계(Pulse/Gap/Chance/Sync)
- 대화 로그 후처리(요약/지갑 추천)

### 7.2 큐/워커
- 브로커: Redis
- 워커: Celery 또는 ARQ (현 팀 운영 난이도 기준 선택)

### 7.3 태스크 설계 원칙
- idempotent 키 보장
- retry 정책 + dead-letter 대응
- task 상태 추적 테이블/로그 필수
- 장기 태스크는 단계별 heartbeat 로그

---

## 8. 도메인별 백엔드 책임 매핑

### 8.1 Pulse
- Bronze 수집 -> Silver 정제 -> Gold 집계
- API는 Gold 조회 전용

### 8.2 Gap
- `refined_gap_insights`에서 문제/기회 추출
- `gap_issues` + `issue_evidences`로 게시/근거 서빙

### 8.3 Sync
- `user_sync_profiles` + `sync_scores_daily`
- 사용자-섹터 적합도 스냅샷 제공

### 8.4 Chance
- `raw_opportunity_data` -> `refined_chance_insights`
- `chance_opportunities` + `user_chance_matches` 기반 개인화 추천

### 8.5 Roadmap
- `user_roadmaps` + `roadmap_quests`(self-tree)
- `growth_daily_logs` 업서트

### 8.6 Coach
- `coach_sessions`(active context 스냅샷)
- `coach_messages`(배지/코드/attached_context)
- `insight_wallets`(지갑 자산화)

---

## 9. 인프라/배포 표준

## 9.1 Docker Compose 기준
- `api`, `worker`, `redis`, `nginx` 컨테이너
- PostgreSQL은 Neon 외부 managed

### 9.2 환경 변수(예시)
- `DATABASE_URL`
- `REDIS_URL`
- `JWT_SECRET`, `JWT_ACCESS_TTL_MIN`, `JWT_REFRESH_TTL_DAYS`
- `OPENAI_API_KEY`, `GEMINI_API_KEY`, `GROQ_API_KEY`
- `CORS_ORIGINS`
- `ENV` (`local`/`staging`/`prod`)

### 9.3 배포 절차(요약)
1. migration 생성/검토
2. staging 배포 + smoke test
3. prod 배포 전 DB 백업 확인
4. `alembic upgrade head`
5. API/worker 헬스체크
6. 모니터링 지표 확인

---

## 10. 관측성/운영 체크리스트

### 10.1 로그
- 구조화 JSON 로그
- request_id / user_id / session_id 상관관계 키
- LLM 호출 비용/지연 분리 기록

### 10.2 메트릭
- API latency p50/p95/p99
- worker queue depth, task fail ratio
- DB query latency / slow query
- 토큰 발급/갱신/회수 통계

### 10.3 알림
- 배치 실패
- 큐 정체
- 인증 실패 급증
- 외부 LLM API 장애율 상승

---

## 11. 테스트 전략

- 단위 테스트: 도메인 서비스/리포지토리
- 통합 테스트: API + DB + Redis
- 계약 테스트: 프론트 기대 응답 스키마
- 데이터 테스트: Bronze->Silver->Gold 샘플 파이프라인 검증
- 회귀 테스트: 코치/로드맵 시나리오 템플릿

---

## 12. 확장 로드맵 (MSA 분리 기준)

아래 조건을 만족하면 도메인 분리를 고려:
- 도메인별 배포 주기 충돌
- 특정 도메인(QPS/AI 비용) 과도 집중
- 독립 스케일링 필요

우선 분리 후보:
1. `coach` (대화량/LLM 비용 집중 가능성)
2. `pipelines` (배치 및 수집 워커)

---

## 13. 결정 로그 (ADR 요약)

- ADR-001: 모듈러 모놀리스 채택
- ADR-002: PostgreSQL + pgvector 통합 저장
- ADR-003: Redis 기반 refresh token revoke
- ADR-004: 메달리온 아키텍처 채택
- ADR-005: 코치/로드맵/찬스 데이터 자산화 스키마 채택

---

## 부록 A. 현재 저장소와의 정합성

- 스키마 기준: `backend/docs/erd.md`
- ORM/마이그레이션: `sqlalchemy` + `alembic` (requirements 확인)
- AI 오케스트레이션: `langgraph`, `fastmcp` 의존성 이미 포함

---

문서 버전: v1.0  
최종 업데이트: 2026-05-06
