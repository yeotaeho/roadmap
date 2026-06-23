# AGENTS.md

## Project
- Roadmap은 청년의 잠재력과 시장의 선행 지표를 연결해 `Pulse`, `Gap`, `Sync`, `Chance`, `Roadmap`, `Coach` 기능을 제공하는 AI 진로 인사이트 플랫폼이다.
- 프론트엔드는 `www.yeotaeho.kr/`의 Next.js 19·TypeScript·Zustand·TanStack Query·Tailwind, 백엔드는 `backend/`의 FastAPI·SQLAlchemy 2·Alembic, 모바일은 `app/app_mobile/`의 Flutter, 관리자는 별도 Next.js 앱이다.
- 인프라는 PostgreSQL(Neon·pgvector), Redis(Upstash), Docker Compose이며 AI 계층은 LangGraph, FastMCP, OpenAI·Gemini·Groq를 사용한다.

## Architecture
- 백엔드는 FastAPI 단일 배포의 DDD-lite 모듈러 모놀리스다. 도메인은 `auth`, `pipeline`, `insight`, `chance`, `profile`, `roadmap`, `coach`로 구분한다.
- 요청 흐름은 `Router -> Application Service -> Repository/Model -> DB`를 따른다. 도메인 간 직접 import를 최소화하고 상위 Application Service에서 조정한다.
- 도메인 코드는 `backend/domain/<domain>/` 아래 `router.py`, `application/`, `model/`, `repository/`, `schemas/`에 둔다.
- 데이터는 Bronze 원천 불변, Silver AI 정제·리니지 유지, Gold UI 읽기 전용 구조다. 스키마 SSOT는 `backend/docs/erd.md`다.
- 프론트엔드는 Zustand로 앱 상태, TanStack Query로 서버 상태를 관리한다.
- 코치와 생성 진행률은 FastAPI `StreamingResponse`와 SSE를 사용한다. FastMCP 도구는 읽기·멱등성을 우선하며 쓰기 도구는 감사 로그를 남긴다.
- 백그라운드 작업은 Redis 기반 Celery 또는 ARQ를 사용하며 멱등 키, 재시도, heartbeat를 고려한다.

## Repository Rules
- FastAPI 라우터의 요청과 응답은 `schemas/`의 Pydantic 모델로 검증한다.
- 새 엔드포인트는 Router, Application, Pydantic Schema, Repository 순으로 책임을 분리하고 `main.py`에 등록한다.
- DB 변경은 ORM 모델 수정 후 Alembic migration을 생성·검토·적용한다. 수동 DDL로 우회하지 않는다.
- 환경 변수와 비밀값을 코드에 넣지 않는다. 주요 설정은 `DATABASE_URL`, `REDIS_URL`, JWT·OAuth·LLM 키, `CORS_ORIGINS`, `ENV`다.

## Working Rules
- 편집 전 실제 파일과 호출부를 `rg`로 확인한다. 불명확한 요구나 중요한 가정은 먼저 밝힌다.
- 요청을 충족하는 최소 변경만 수행한다. 불필요한 기능·추상화·리팩터링·서식 변경은 하지 않는다.
- 미커밋 변경은 사용자 작업으로 간주해 덮어쓰거나 되돌리지 않는다. 파괴적 Git 명령은 명시적 요청 없이 실행하지 않는다.
- 비단순 작업은 짧은 계획과 검증 기준을 세운다. 긴 작업에서만 `checklist.md`와 `context-notes.md`를 유지한다.
- 오류는 실제 로그와 stack trace를 확인한 뒤 수정한다.
- 코드 변경 후 관련성이 높은 검사부터 실행하고 최종 답변에 명령, 결과, 남은 위험을 적는다.
- 코드 제안은 불필요한 설명 없이 변경된 핵심만 간결하게 제시한다.
- 한국어 요청에는 한국어로 답하고 한국어 문장을 콜론으로 끝내지 않는다.
- 새 소스 파일에는 역할을 설명하는 한 줄 한국어 주석을 둔다. shebang과 client/server 지시문이 있으면 그 아래에 두며 설정·잠금·생성 파일은 제외한다.

## Commands
- Frontend: `cd www.yeotaeho.kr; pnpm run lint` / `pnpm run build` / `pnpm run dev`
- Backend: `cd backend; python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload`
- Migration: `cd backend; alembic revision --autogenerate -m "description"` / `alembic upgrade head`
- Integration: `cd backend; python scripts/<source>_integration_test.py`
- Docker: `docker-compose up -d` / `docker-compose logs -f api` / `docker-compose down`
