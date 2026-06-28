# Roadmap(hrowth_journey) 목업 수직 슬라이스 — 설계

- **작성일** — 2026-06-28
- **도메인** — `hrowth_journey`(Roadmap 탭) · 페르소나 테이블은 `user_intelligence` 소유
- **상태** — 승인됨, 구현 진행

## 1. 배경·목표

`market_insight`·`master` 도메인은 라이브 완성됐고, 다음 구현 대상으로 Roadmap(`hrowth_journey`)을 선택했다. 프론트(`RoadmapView`)는 이미 2개 서브탭으로 완성돼 있으나 데이터가 [roadmapQuestMap.ts](../../../../www.yeotaeho.kr/src/data/roadmapQuestMap.ts)에 **로컬 하드코딩**된 목업 상태다. 백엔드 `hrowth_journey`는 빈 스텁이다.

이번 작업은 **프론트가 기대하는 모양(퀘스트 트리·성장 아카이브)을 그대로 서빙하는 백엔드 수직 슬라이스를, 내용은 목업으로 채워** 만든다. LLM 생성(`RoadmapPlanner`)과 coach의 실제 페르소나 수집은 범위 밖이다.

성공 기준:
1. `GET /api/roadmap/journey`가 인증 사용자에게 중첩 퀘스트 트리 + 스킬 트라이앵글 + 키워드 브릿지를 반환한다.
2. `GET/PUT /api/roadmap/archive`로 성장 아카이브 일별 로그가 실제 영속화된다.
3. 페르소나(스킬/경험/학력) 테이블이 생성되고 목업 1건이 시드된다.
4. 순수 조립 함수 `assemble_quest_tree`가 pytest 통과.

## 2. 도메인·API 네이밍

- 도메인 폴더: `domain/hrowth_journey/`(기존 오타 폴더 그대로).
- 라우터: `api/v1/roadmap/roadmap_routor.py`, `router = APIRouter(prefix="/roadmap")` → 최종 `/api/roadmap/*`. (market_insight가 `insight` 라우터로 서빙하듯 도메인명≠API명.)
- `main.py`에 `roadmap_v1_router` 등록.

## 3. 데이터 모델 (테이블 4개)

`users.id`는 현재 UUID(리셋 마이그레이션 `9f2a6d4e1b0c` 이후)다. 신규 FK는 전부 `UUID(as_uuid=True)` → `users.id`. 2월 구 테이블(`user_competency`/`user_roadmap_status`, BigInteger users)은 **재사용하지 않는다**.

### 3.1 `user_personas` — `user_intelligence` 도메인 소유 (미래 작성자 = coach)

| 컬럼 | 타입 | 설명 |
|---|---|---|
| user_id | UUID PK, FK users CASCADE | 사용자 |
| education | JSONB | `[{school, major, degree, status}]` |
| experiences | JSONB | `[{title, description, period}]` |
| skills | JSONB | `[{name, level: 입문\|중급\|심화}]` |
| summary | TEXT | 상담 요약(mock) |
| source | VARCHAR(30) | 도출 출처 (`mock`/`coach_session`) |
| updated_at | TIMESTAMPTZ | 갱신 |

ORM: `domain/user_intelligence/models/bases/user_persona.py`. 바운디드 컨텍스트상 페르소나는 user_intelligence 소유임을 코드로 표기. Roadmap은 **읽기만**(현재 공유 DB read, 향후 hub orchestrator 경유).

### 3.2 Roadmap — `hrowth_journey` 도메인 소유 (3개)

**`user_roadmaps`** — 사용자당 1 활성 로드맵
| 컬럼 | 타입 | 설명 |
|---|---|---|
| id | BigInteger PK | |
| user_id | UUID FK users CASCADE | |
| title, summary | VARCHAR/TEXT | 여정 헤더 |
| skill_pillars | JSONB | 스킬 트라이앵글 `[{id,label,blurb}]` |
| bridge_keywords | JSONB | 키워드 브릿지 `[str]` |
| status | VARCHAR(20) | `active` 등 |
| generated_at, updated_at | TIMESTAMPTZ | |
| UNIQUE(user_id) | | 1인 1활성 |

**`roadmap_quests`** — 퀘스트 트리 노드(자기참조)
| 컬럼 | 타입 | 설명 |
|---|---|---|
| id | BigInteger PK | |
| roadmap_id | FK user_roadmaps CASCADE | |
| quest_key | VARCHAR(60) | 프론트 id (`q-esg-map`) — API에서 `id`로 노출 |
| parent_key | VARCHAR(60) NULL | 자기참조(트리). root는 NULL |
| title, purpose | VARCHAR/TEXT | |
| difficulty | VARCHAR(10) | `입문\|중급\|심화` |
| keywords | JSONB | `[str]` |
| state | VARCHAR(12) | `start\|available\|active\|done\|locked` |
| sort_order | INT | 형제 정렬 |
| UNIQUE(roadmap_id, quest_key) | | |

**`growth_logs`** — 아카이브 일별 로그
| 컬럼 | 타입 | 설명 |
|---|---|---|
| id | BigInteger PK | |
| user_id | UUID FK users CASCADE | |
| log_date | DATE | |
| note | TEXT | 자유 기록 |
| completed_quest_keys | JSONB | `[quest_key]` |
| created_at, updated_at | TIMESTAMPTZ | |
| UNIQUE(user_id, log_date) | | 멱등 upsert |

## 4. API (프론트 모양에 정확 매핑)

- `GET /api/roadmap/journey` (auth) → `{ success, roadmap: {title, summary, skillPillars, bridgeKeywords}, questTree: <중첩 root> }`. 로드맵 없으면 `roadmap: null, questTree: null`.
- `GET /api/roadmap/archive?month=YYYY-MM` (auth) → `{ success, logs: { "YYYY-MM-DD": {completedQuestIds, note} } }`.
- `PUT /api/roadmap/archive/{log_date}` (auth, body `{completedQuestIds, note}`) → upsert 후 `{ success, date, completedQuestIds, note }`.
- `POST /api/roadmap/refine` (internal token) → 페르소나→로드맵 재생성 훅. **이번엔 mock 재시드 스텁**(향후 LLM `RoadmapPlanner`).

응답은 chance/insight 라우터와 동일하게 plain dict + `success` 래핑. PUT 바디만 인라인 Pydantic(`SyncProfileUpsertRequest` 패턴).

## 5. 서비스·리포지토리

- `hub/services/journey_assembler.py` — 순수함수 `assemble_quest_tree(flat: list[dict]) -> dict | None`. 평면 행 → 중첩 트리(부모-자식 연결, `sort_order` 정렬, 상태/키워드 보존). pytest 대상.
- `hub/services/journey_service.py` — `JourneyService(db)`: repo로 로드맵+퀘스트 조회 → 조립.
- `hub/services/archive_service.py` — `ArchiveService(db)`: 월별 조회, 일별 upsert.
- `hub/repositories/roadmap_repository.py` — `RoadmapRepository(BaseRepository)`: `text()` 원시 SQL.

## 6. 시드·검증

- **마이그레이션 = 스키마만**(수동 DDL 금지 준수). FK가 `users`만이라 sectors-autogenerate 함정 없음. down_revision = 현재 head `d7a1f3c9e2b5`. `alembic/env.py`에 신규 ORM 4종 import 등록.
- **목업 시드** = `scripts/seed_roadmap_mock.py` — roadmapQuestMap.ts의 QUEST_TREE·SKILL_TRIANGLE·BRIDGE_KEYWORDS·ARCHIVE_SEED + mock 페르소나 1건 적재. 멱등(존재 시 skip/upsert). 대상 user_id 인자.
- **pytest** = `scripts/roadmap_journey_assembler_test.py`(무DB 순수함수).
- **엔드포인트** = `scripts/roadmap_endpoint_test.py`(uvicorn 127.0.0.1 기동 후 라이브 확인).
- **DB 적용은 사용자 승인 후 실행**(Neon 단일 DB, 쓰기 민감).

## 7. 범위 밖

- LLM `RoadmapPlanner` 실제 생성 — `/refine`은 mock 재시드 스텁.
- coach/user_intelligence의 실제 페르소나 수집 플로우.
- 프론트 로컬목업 → API 전환 배선(백엔드 계약 확정 후 별도 작업).
