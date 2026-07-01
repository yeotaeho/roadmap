# CLAUDE.md

## Coding Behavior

1. **Think first** — 가정을 명시하고, 해석이 여러 개면 제시. 불명확하면 묻기.
2. **Simplicity** — 요청한 것만. 투기적 기능·단일 사용 추상화·불가능한 시나리오 처리 금지.
3. **Surgical edits** — 태스크가 요구하는 줄만 수정. 기존 스타일 유지. 내 변경이 만든 orphan만 제거.
4. **Verify** — 코딩 전 성공 기준 정의. 코드 수정 후 반드시 테스트 실행 (`pytest` / `pnpm test`).
5. **Korean sentences** — 한국어 문장 종결은 `.` `?` `!` 만. `:` 로 끝내지 않기.
6. **File headers** — 새 소스 파일 첫 줄: 한 줄 한국어 주석으로 역할 명시 (config 파일 제외).  
   예) `// 사용자 인증 상태를 관리하는 Context Provider` / `# KIS API 클라이언트`
7. **Semantic commits** — 논리적 단위 완성 시 즉시 커밋. 무관한 변경 묶지 않기.
8. **Read errors** — 실제 에러/스택 트레이스 읽고 수정. 패턴 매칭 추측 금지.
9. **Work log** — 작업 단위 완료(커밋 직후)마다 변경 내용을 관련 md 에 기록. 형식·위치는 아래 [작업 기록 규칙](#작업-기록-규칙-audit-trail) 참고. **md 를 수정·생성하기 전 반드시 대상 경로를 제시하고 허락받기.**
10. **Codex 최종 리뷰** — 계획·구현·수정 작업을 논리적 단위로 마치고 커밋한 뒤, **마지막에 Codex 리뷰를 거친다**. 형식·절차는 아래 [Codex 리뷰 규칙](#codex-리뷰-규칙) 참고.

---

## Project Overview

**Roadmap** — 진로 막연함을 느끼는 청년(10대 후반~30대 초반)에게 선행 행동 지표(투자 흐름·특허·검색량)를 분석해 객관적 인사이트와 성장 로드맵을 제공하는 AI 내비게이션 플랫폼.

| 탭 | 역할 |
|---|---|
| Pulse | 산업 섹터별 트렌드 점수·경제 브리핑 |
| Gap | 시장 미해결 기회 시각화 |
| Sync | 사용자-트렌드 적합도 일별 점수 |
| Chance | 채용/부트캠프/공모전/지원사업 매칭 |
| Roadmap | AI 생성 퀘스트 트리 + 성장 아카이브 |
| Coach | SSE 스트리밍 멘토링 + 인사이트 지갑 |

**Stack** — Frontend: Next.js/TS/React 19/Zustand/TanStack Query/Tailwind (`www.yeotaeho.kr/`) · Backend: FastAPI/Python/PostgreSQL(Neon)/SQLAlchemy 2.0/Alembic (`backend/`) · Mobile: Flutter (`app/app_mobile/`) · Admin: Next.js (`admin.yeotaeho.kr/`) · Infra: Docker Compose, pgvector, Redis(Upstash) · AI: LangGraph StateGraph, FastMCP, OpenAI/Gemini/Groq · Worker: Celery 또는 ARQ

---

## Commands

```bash
# Frontend
pnpm install && pnpm run dev        # http://localhost:3000

# Backend
pip install -r requirements.txt
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload  # http://localhost:8000/docs

# Alembic
alembic upgrade head
alembic revision --autogenerate -m "description"

# Docker
docker-compose up -d   # api, worker, redis, nginx

# Integration tests
python scripts/smes_integration_test.py
python scripts/yahoo_finance_integration_test.py
```

---

## Architecture

### Backend — 모듈러 모놀리스 + 7대 Bounded Context (DDD-lite)

```
backend/
├── main.py                         # FastAPI 엔트리, CORS, 라우터 등록 (API_V1_PREFIX="/api")
├── api/v1/<name>/<name>_routor.py  # HTTP 라우터 — chance·insight·master·news·oauth·sync·trend_analysis·user
├── core/
│   ├── config/settings.py          # Pydantic settings
│   ├── database.py                 # DB 세션·엔진
│   ├── llm/client.py               # LLM 클라이언트
│   ├── logging_config.py
│   └── scheduler.py                # APScheduler 배치 잡
├── domain/                         # 7대 Bounded Context + 보조 도메인
│   ├── auth/                       # 1. Auth & Identity — JWT·OAuth·세션
│   ├── master/                     # 2. Master & Pipeline — Bronze 수집기(collectors)·정제
│   ├── market_insight/             # 3. Market Insight — Pulse·Gap·Chance·Sync·Causal Silver→Gold
│   ├── opportunity/                # 4. Opportunity — 공고·매칭·북마크 (스캐폴딩)
│   ├── user_intelligence/          # 5. User Intelligence — AI 상담·페르소나·싱크 (스캐폴딩)
│   ├── hrowth_journey/             # 6. Growth Journey — 로드맵·퀘스트·아카이브 (스캐폴딩·폴더명 오타)
│   ├── ai_coach/                   # 7. AI Coach — SSE·RAG·FastMCP·지갑 (스캐폴딩)
│   ├── news/                       # 보조 — RSS 뉴스 수집·서빙
│   └── shard/                      # 공유 (현재 비어있음·"shared" 오타)
├── alembic/                        # 마이그레이션
├── docs/                           # 백엔드 공통 설계 문서·ERD SSOT
└── scripts/                        # 통합 테스트·운영 스크립트
```

각 DDD 도메인 `domain/<name>/` 내부 — **Hub-Spoke (Star Topology)**:
- `hub/` — 중심부. `orchestrator/` · `services/`(유스케이스·파이프라인) · `repositories/`(DB 접근) · `routing/` · `mcp/`(FastMCP 툴)
- `models/` — `bases/`(SQLAlchemy 테이블) · `enums/` · `states/`(LangGraph State) · `transfer/`(DTO)
- `spokes/` — 외곽부. `agents/`(LangGraph 노드) · `infra/`(외부 API) · `retreivers/`(RAG·폴더명 오타)
- `docs/` — 도메인 설계 스펙 + `audit_trail.md`(작업 기록)

- 수집기 위치: `domain/master/hub/services/collectors/<axis>/<source>/` (axis: economic·innovation·people·discourse·opportunity·company)
- 현 구현 분포: Pulse·Gap·Chance·Sync·Causal·Briefing 등 인사이트 수직은 `market_insight` 한 도메인에 집중. `opportunity`·`user_intelligence`·`hrowth_journey`·`ai_coach` 는 스캐폴딩 단계.

**요청 흐름**: `api/v1/<name>/<name>_routor.py` → `domain/<name>/hub/services` → `hub/repositories` → DB  
**도메인 간 호출**: 직접 import 최소화, 교차 접근은 hub orchestrator 에서 조율.

### 데이터 계층 — Medallion

```
Bronze (원천 수집) → Silver (AI 정제) → Gold (UI 서빙)
raw_economic_data    refined_trend_insights   pulse_metrics_log
raw_innovation_data  refined_gap_insights     gap_issues / issue_evidences
raw_people_data      refined_chance_insights  chance_opportunities
raw_discourse_data                            sync_scores_daily
raw_opportunity_data                          user_roadmaps / coach_sessions
```

- Bronze: 불변 원칙 · Silver: LLM 정제 (`raw_table_ref`/`raw_id`로 리니지 추적) · Gold: 읽기 전용 + Redis 캐시
- 스키마 SSOT: `backend/docs/erd.md`

### AI / LLM

- LangGraph `StateGraph` Star Topology — 노드: `PulseAnalyzer` `GapIssueAnalyst` `ChanceMatcher` `RoadmapPlanner` `CoachMentor`
- FastMCP (idempotent/read-only 우선, write tool은 감사 로그 필수)
- pgvector — 메타데이터 필터 + 유사도 검색
- FastAPI `StreamingResponse` + SSE (코치·로드맵 진행률)
- 임베딩: `text-embedding-3-large` 고정

### Frontend State

- Zustand: auth(토큰·silent refresh) · user(프로필·설정) · UI(모달·테마)
- TanStack Query: axios 기반 서버 상태 캐싱
- Silent refresh: `services/silentRefresh.ts` → `/api/oauth/refresh`

### Auth Flow

1. Kakao/Google OAuth 리다이렉트
2. `/api/oauth/<provider>/callback` — code ↔ 사용자 정보 교환
3. JWT 발급 — HTTP-only 쿠키 + 로컬 액세스 토큰
4. 리프레시 토큰 → Redis(Upstash) stateful 저장 (revoke 가능)

### Background Jobs

- 브로커: Redis · 워커: Celery/ARQ
- 일별 09:00 KST: DART, MSIT, 스타트업 뉴스, SMES, 네이버 뉴스
- 주별 월 09:00 KST: ALIO, Yahoo Finance ETF, Yahoo Macro
- 태스크 원칙: idempotent 키 · retry + dead-letter · 장기 태스크 heartbeat

---

## Key Environment Variables

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | PostgreSQL (Neon) |
| `REDIS_URL` | Redis (Upstash) |
| `JWT_SECRET` / `JWT_ACCESS_TTL_MIN` / `JWT_REFRESH_TTL_DAYS` | JWT |
| `OPENAI_API_KEY` / `GEMINI_API_KEY` / `GROQ_API_KEY` | LLM |
| `KAKAO/GOOGLE_CLIENT_ID/SECRET/REDIRECT_URI` | OAuth |
| `CORS_ORIGINS` | 허용 origin (쉼표 구분) |
| `ENV` | `local` / `staging` / `prod` |

---

## Adding New Endpoints

1. `api/v1/<name>/<name>_routor.py` 라우터 정의 (`router = APIRouter(prefix="/<name>")`)
2. `domain/<name>/hub/services/` 유스케이스 구현
3. `domain/<name>/models/transfer/` Pydantic DTO 정의
4. `domain/<name>/hub/repositories/` DB 접근 레이어
5. `main.py`에 `app.include_router(<name>_router, prefix=API_V1_PREFIX)` 등록

## Database Changes

1. `domain/<name>/models/bases/` ORM 모델 수정
2. `alembic revision --autogenerate -m "..."` — 생성 파일 검토 필수
3. `alembic upgrade head` → 마이그레이션 파일 커밋 (수동 DDL 금지)

## 작업 기록 규칙 (Audit Trail)

작업 단위 완료 시(커밋 직후) 변경 내용을 **관련 도메인**의 작업 기록 md 에 남긴다.

- **위치** — 도메인 작업은 `backend/domain/<name>/docs/audit_trail.md`, 공통·인프라는 `backend/docs/`. 적절한 md 가 없으면 새로 만든다.
- **순서** — 최신 항목을 맨 위에 추가(역순).
- **허락** — md 를 수정·생성하기 전 반드시 대상 경로를 제시하고 사용자 승인을 받는다. 승인 없이는 쓰지 않는다.

**기록 형식**

```markdown
## YYYY-MM-DD — <작업 한 줄 제목>
- **무엇** — 무엇을 바꿨나 (요약 한 줄)
- **왜** — 배경·트리거
- **어디** — 핵심 파일·테이블 (`경로:라인` clickable)
- **검증** — 실행한 테스트·결과 (`pytest` / `pnpm test`)
- **후속** — 남은 TODO (없으면 생략)
```

## Codex 리뷰 규칙

계획·구현·수정 작업을 논리적 단위로 마치고 **커밋한 뒤**, 턴을 끝내기 전에 Codex 리뷰를 최종 게이트로 실행한다.

- **언제** — 각 작업 단위(기능·수정·리팩터) 커밋 직후, 완료를 선언하기 전. 여러 커밋이 쌓였으면 마지막에 한 번 범위 리뷰.
- **어떻게** — `/codex:review` 슬래시 커맨드로 실행한다(내부적으로 codex-companion `review`).
  - 미커밋 변경 = working-tree 기본. **이미 커밋한 분** = `--base <직전 ref> --scope branch` 로 커밋 범위 리뷰.
  - 규모: 1~2파일 소규모 → foreground(`--wait`). 그 이상·불확실 → background.
  - 커스텀·적대적 관점이 필요하면 `/codex:adversarial-review`.
- **원칙** — 리뷰는 **read-only**. 지적사항을 무비판 수용하지 말고 실제 결함인지 별도 판단 후 반영한다([receiving-code-review 태도]). **Critical/Important** 는 조치 후 **재리뷰**, **Minor** 는 트리아지(즉시 vs 후속).
- **자동화(선택)** — `/codex:setup --enable-review-gate` 로 stop-time 리뷰 게이트를 켜면 턴 종료 전 자동으로 직전 변경을 리뷰한다.

## MSA 분리 후보

현재 모듈러 모놀리스. 아래 조건 충족 시 분리 검토.
1. `ai_coach` — 대화량·LLM 비용·SSE 집중 시 1순위
2. `master` — 배치(수집·정제) 독립 스케일아웃 필요 시
