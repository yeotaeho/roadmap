# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Roadmap**는 진로에 대한 막연함을 느끼는 청년(10대 후반~30대 초반)에게 **'나의 잠재력'과 '세상의 요구'를 연결하는 AI 기반 인사이트 내비게이션 플랫폼**입니다.

단순한 직업 추천을 넘어, 후행 지표(뉴스·결과)가 아닌 **선행 행동 지표(투자 흐름, 특허 출원, 검색량 변화)**를 수집·분석하여 객관적 통찰력과 성장 로드맵을 제공합니다.

### 핵심 서비스 탭

| 탭 | 설명 |
|---|---|
| **Pulse (트렌드 속도계)** | 산업 섹터별 트렌드 점수 및 경제 브리핑 |
| **Gap (블루오션)** | 시장이 해결 못한 기회 영역 시각화 |
| **Sync (싱크로율)** | 사용자-트렌드 적합도 일별 점수 |
| **Chance (다이렉트 찬스)** | 채용/부트캠프/공모전/지원사업 매칭 |
| **Roadmap (전략 로드맵)** | AI 생성 퀘스트 트리 + 성장 아카이브 |
| **Coach (AI 코치)** | SSE 스트리밍 멘토링 + 인사이트 지갑 |

### 기술 스택

- **Frontend**: Next.js (TypeScript, React 19, Zustand, TanStack Query, Tailwind CSS) — `www.yeotaeho.kr/`
- **Backend**: Python FastAPI (async, PostgreSQL via Neon, SQLAlchemy 2.0, Alembic) — `backend/`
- **Mobile**: Flutter app (진행 중) — `app/app_mobile/`
- **Admin**: 별도 Next.js 대시보드 — `admin.yeotaeho.kr/`
- **Infrastructure**: Docker Compose, PostgreSQL (Neon + pgvector), Redis (Upstash)
- **AI/LLM**: LangGraph (StateGraph 기반 에이전트), FastMCP, OpenAI / Gemini / Groq
- **Background**: Celery 또는 ARQ 워커 (Redis 브로커)

---

## Commands

### Frontend (`www.yeotaeho.kr/`)

```bash
pnpm install
pnpm run dev       # http://localhost:3000
pnpm run build
pnpm run lint
```

### Backend (`backend/`)

```bash
pip install -r requirements.txt

# Dev server (Swagger UI at http://localhost:8000/docs)
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Alembic migrations
alembic upgrade head
alembic revision --autogenerate -m "description"
alembic downgrade -1
alembic current
```

### Docker

```bash
docker-compose up -d           # api, worker, redis, nginx
docker-compose logs -f api
docker-compose down
```

### Integration Tests (`backend/scripts/`)

```bash
python scripts/smes_integration_test.py
python scripts/yahoo_finance_integration_test.py
# 기타 데이터 소스 테스트는 backend/scripts/ 참고
```

---

## Architecture

### 백엔드 — 모듈러 모놀리스 + 7대 Bounded Context (DDD-lite)

배포 단위는 FastAPI 단일 애플리케이션이며, 내부는 도메인 경계로 격리됩니다.

```
backend/
├── main.py                    # FastAPI 앱 엔트리, CORS, 라우터 등록
├── api/
│   ├── routers/               # 도메인별 HTTP 라우터
│   └── dependencies/          # 공통 의존성 (인증 등)
├── domain/                    # 7대 Bounded Context
│   ├── auth/                  # 1. Auth & Identity — JWT·OAuth·세션
│   ├── pipeline/              # 2. Master & Pipeline — Bronze 수집·Silver 정제·배치 워커
│   ├── insight/               # 3. Market Insight — Pulse·Gap Gold 읽기 전용 서빙
│   ├── chance/                # 4. Opportunity — 다이렉트 찬스 공고·매칭·북마크
│   ├── profile/               # 5. User Intelligence — AI 상담·페르소나·싱크로율
│   ├── roadmap/               # 6. Growth Journey — 퀘스트 트리·성장 아카이브
│   └── coach/                 # 7. AI Coach — SSE 스트리밍·RAG·FastMCP·지갑
├── data/
│   ├── pipelines/             # pipeline 도메인 소유 — 수집·정제 구현
│   └── workers/               # Celery/ARQ 태스크
├── core/
│   ├── config/                # Pydantic settings, DB/Redis 연결
│   ├── scheduler.py           # APScheduler 배치 잡
│   └── logging_config.py
├── alembic/                   # 마이그레이션 버전 관리
└── scripts/                   # 데이터 소스 통합 테스트 스크립트
```

각 `domain/<name>/` 내부 레이어:
- `router.py` — HTTP 경계
- `application/` — 유스케이스·오케스트레이션
- `model/` — SQLAlchemy ORM 모델
- `repository/` — DB 접근
- `schemas/` — Pydantic DTO
- (필요 시) `llm/`, `tasks/` — 도메인 전용 프롬프트·워커 엔트리

**요청 흐름**: Router → Application Service → Repository/Model → DB  
**도메인 간 호출**: 직접 import 최소화, 교차 접근은 상위 Application Service에서 orchestration

### 데이터 계층 — 메달리온 아키텍처 (Medallion)

```
Bronze (원천 수집)     →  Silver (AI 정제/추론)    →  Gold (UI 서빙)
raw_economic_data        refined_trend_insights       pulse_metrics_log
raw_innovation_data      refined_gap_insights         gap_issues / issue_evidences
raw_people_data          refined_chance_insights      chance_opportunities
raw_discourse_data                                    sync_scores_daily
raw_opportunity_data                                  user_roadmaps / roadmap_quests
                                                      coach_sessions / insight_wallets
```

- **Bronze**: 원천 수집 — 불변 유지 원칙
- **Silver**: LLM 기반 AI 정제·추론 결과 (`raw_table_ref`, `raw_id`로 리니지 추적 가능)
- **Gold**: 앱/웹 UI는 Gold 테이블만 조회 (읽기 전용 + Redis 캐시)
- **스키마 SSOT**: `backend/docs/erd.md`

### AI / LLM 인텔리전스 레이어

- **오케스트레이션**: LangGraph `StateGraph` — Router 중심 Star Topology
  - 노드: `PulseAnalyzer`, `GapIssueAnalyst`, `ChanceMatcher`, `RoadmapPlanner`, `CoachMentor`
- **도구 연동**: FastMCP (idempotent/read-only 우선, write tool은 감사 로그 필수)
- **벡터 검색**: pgvector — PostgreSQL 단일 DB에서 메타데이터 필터 + 유사도 검색 통합
- **스트리밍**: FastAPI `StreamingResponse` + SSE (코치 채팅·로드맵 생성 진행률)
- **임베딩**: `text-embedding-3-large` 계열 고정 모델

### Frontend State

- **Zustand**: 전역 앱 상태 — auth 슬라이스(토큰·silent refresh), user 슬라이스(프로필·설정), UI 슬라이스(모달·테마)
- **TanStack Query**: 서버 상태 — axios 기반 API 캐싱·리페칭
- **Silent refresh**: `services/silentRefresh.ts` — 만료 전 토큰 자동 갱신 (`/api/oauth/refresh`)

### Authentication Flow

1. 프론트엔드가 Kakao/Google OAuth 로그인 페이지로 리다이렉트
2. 백엔드 `/api/oauth/<provider>/callback`에서 code ↔ 사용자 정보 교환
3. JWT 발급 — HTTP-only 쿠키 저장 + 헤더 주입용 액세스 토큰 로컬 보관
4. 리프레시 토큰은 Redis(Upstash)에 stateful 저장 (revoke 가능)

### Background Jobs

- **브로커**: Redis
- **워커**: Celery 또는 ARQ
- **배치 잡** (`core/scheduler.py`):
  - 일별 (매일 09:00 KST): DART, MSIT, 스타트업 뉴스 매체, SMES, 네이버 뉴스
  - 주별 (매주 월 09:00 KST): ALIO, Yahoo Finance ETF, Yahoo Macro
- 태스크 설계 원칙: idempotent 키, retry + dead-letter 대응, 장기 태스크 heartbeat 로그

---

## Key Environment Variables (`.env`)

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | PostgreSQL (Neon) 연결 문자열 |
| `REDIS_URL` | Redis (Upstash) 연결 문자열 |
| `JWT_SECRET` | JWT 서명 키 |
| `JWT_ACCESS_TTL_MIN` | 액세스 토큰 유효 시간 (분) |
| `JWT_REFRESH_TTL_DAYS` | 리프레시 토큰 유효 시간 (일) |
| `OPENAI_API_KEY` | OpenAI (임베딩·코치 추론) |
| `GEMINI_API_KEY` | Google Gemini |
| `GROQ_API_KEY` | Groq (빠른 추론) |
| `KAKAO/GOOGLE_CLIENT_ID/SECRET/REDIRECT_URI` | OAuth 프로바이더 |
| `CORS_ORIGINS` | 허용 프론트엔드 origin (쉼표 구분) |
| `ENV` | `local` / `staging` / `prod` |

---

## Adding New Endpoints

1. `domain/<domain>/router.py`에 라우터 정의
2. `domain/<domain>/application/`에 유스케이스·서비스 로직 구현
3. `domain/<domain>/schemas/`에 Pydantic 요청/응답 모델 정의
4. `domain/<domain>/repository/`에 DB 접근 레이어 작성
5. `main.py`에 `app.include_router(router, prefix="/api")`로 등록

---

## Database Changes

1. `domain/<domain>/model/`의 SQLAlchemy ORM 모델 수정
2. `alembic revision --autogenerate -m "description"` — 생성된 파일 반드시 검토
3. `alembic upgrade head`
4. 마이그레이션 파일 커밋 (수동 DDL 금지, 모든 변경은 Alembic 경유)

---

## MSA 분리 우선 후보

현재는 모듈러 모놀리스로 운영하며, 아래 조건 충족 시 분리 검토:

1. **`coach` 도메인** — 대화량·LLM 비용·SSE 집중 시 1순위 독립 컨테이너
2. **`pipeline` 도메인** — 데이터 수집·배치만 독립 스케일아웃 필요 시
