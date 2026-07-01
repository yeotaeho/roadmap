# 코치 대화 영속화 (SP-2a) 설계

> **목적** — AI 상담실을 무상태 채팅에서 **대화를 기억하는 세션 기반 상담**으로 바꾼다. 이는 "상담실=개인화 본가" 비전의 토대이자, SP-2b(세션 종료 후 자기모델 추출)의 전제다.
> **작성일** — 2026-07-01. 상위 비전: [self-model design](2026-07-01-ai-coach-self-model-design.md)(SP-2). 소비 대상: SP-1 `SelfModelService`(SP-2b에서).

---

## 1. 배경 — 왜

현재 코치는 **완전 무상태**다. `POST /api/coach/stream`은 단일 `message` 하나만 받고([coach_routor.py](../../../api/v1/coach/coach_routor.py)), 서버는 대화를 저장하지 않으며, LLM 호출조차 이전 턴을 보지 않는다([coach_service.py](../../../domain/ai_coach/hub/services/coach_service.py) `stream_sse` — system + 단일 user 메시지만). 따라서 (1) 코치가 대화 맥락을 기억하지 못하고, (2) "세션 후 추출"의 **세션 개념이 없다**.

SP-2a는 명시적 세션으로 대화를 영속화해 이 둘을 해소한다. 부수 효과로 코치가 멀티턴 기억을 얻는다.

## 2. 확정 결정(브레인스토밍)
- **대화 영속화** — 서버가 세션·메시지를 저장(클라 전송/교환별 추출 대신). "본가"의 진짜 토대.
- **명시적 세션** — 프론트가 세션을 생성·종료. 경계가 명확해 SP-2b 추출 트리거가 깔끔.

## 3. 데이터 모델 (ai_coach 도메인, 2 테이블)

### 3.1 `coach_sessions` (1행/대화)
| 컬럼 | 타입 | 설명 |
|---|---|---|
| `id` | UUID PK | 앱에서 uuid4 생성(확장 의존 회피) |
| `user_id` | UUID FK `users.id` CASCADE, NOT NULL, indexed | 소유자 |
| `status` | VARCHAR(10) NOT NULL default `active` | `active` / `ended` |
| `started_at` | timestamptz NOT NULL default now() | |
| `ended_at` | timestamptz nullable | 종료 시각(추출 트리거) |
| `title` | VARCHAR(120) nullable | 첫 메시지 요약(후속, SP-2a는 미채움) |
| `extracted_at` | timestamptz nullable | SP-2b가 추출 완료 표시 |
| `created_at` | timestamptz default now() | |

### 3.2 `coach_messages` (N행/세션, append-only)
| 컬럼 | 타입 | 설명 |
|---|---|---|
| `id` | BIGSERIAL PK | |
| `session_id` | UUID FK `coach_sessions.id` CASCADE, NOT NULL | |
| `role` | VARCHAR(10) NOT NULL | `user` / `assistant` |
| `content` | TEXT NOT NULL | |
| `created_at` | timestamptz NOT NULL default now() | |

인덱스 — `ix_coach_messages_session (session_id, created_at)`.

## 4. API (`coach_routor` 확장 · 전부 `get_authenticated_user_id` + 소유권)

**소유권 규칙** — 세션 스코프 엔드포인트는 세션의 `user_id`가 인증 사용자와 일치해야 한다. 불일치 403, 미존재 404(IDOR 차단).

- **`POST /api/coach/sessions`** — 세션 생성. 응답 `{"success": true, "sessionId": "<uuid>"}`.
- **`POST /api/coach/stream`** — 요청 `{"sessionId": "<uuid>", "message": "..."}`. (1) 세션 소유권 검증·active 확인. (2) 사용자 메시지 저장. (3) 세션 최근 N개 메시지 + 맥락 주입해 LLM 스트리밍. (4) 스트림 완료 시 어시스턴트 응답 누적본 저장. SSE 형식은 기존 유지(`data: {type:delta|done|error}`).
- **`POST /api/coach/sessions/{id}/end`** — 소유권 검증 후 `status='ended'`·`ended_at=now()`. 이미 ended면 멱등. 응답 `{"success": true}`. (SP-2b 추출 트리거 지점.)
- **`GET /api/coach/sessions/{id}/messages`** — 소유권 검증 후 세션 메시지 `created_at ASC`. 응답 `{"success": true, "messages": [{"role","content","createdAt"}]}`.

## 5. 멀티턴 기억 (`coach_service.stream_sse` 변경)
- 시그니처를 `stream_sse(user_id, session_id, message)`로 확장.
- 스트림 시작 시 세션 최근 N(기본 20)개 메시지를 `created_at ASC`로 로드해 LLM `messages` 배열에 순서대로 넣고, 그 뒤 현재 user 메시지를 붙인다. system(맥락 포함)은 그대로 앞에.
- `build_coach_context`(맥락 주입)는 불변.

## 6. 스트리밍 중 영속화 — DB 세션 수명 함정 (핵심)
FastAPI `Depends(get_db)`로 열린 요청 스코프 세션은 **응답 반환 후 닫히는데**, `StreamingResponse` 제너레이터는 그 **후에** 실행된다. 따라서 제너레이터 안에서 요청 세션으로 쓰기를 하면 "세션 닫힘/이벤트루프" 오류가 날 수 있다.

**규칙** — 메시지 영속화(사용자·어시스턴트)는 제너레이터 내부에서 `AsyncSessionLocal()`로 **독립 세션**을 열어 수행한다. 사용자 메시지는 스트리밍 시작 전에 저장(자체 세션 open→commit→close), 어시스턴트 응답은 델타를 누적해 완료 후 저장(또 다른 자체 세션). 스트림 도중 오류 시 누적본이 비어있지 않으면 저장하고 그렇지 않으면 생략한다. 소유권·active 검증은 라우트에서 요청 세션으로 스트리밍 시작 전에 수행한다.

## 7. 프론트 (`CoachView` · `lib/api/coach.ts`)
- `lib/api/coach.ts`에 `createCoachSession()`·`endCoachSession(id)`·`fetchCoachMessages(id)` 추가, `streamCoach`에 `sessionId` 인자 추가(body에 동봉).
- `CoachView`: 마운트 시 세션 생성(`sessionId` 상태 보관)·기존 로컬 mock 대화 대신 서버 히스토리 로드, 각 전송에 `sessionId` 동봉, 언마운트(또는 명시 "대화 종료")에서 `endCoachSession` 호출. 비로그인 시 기존 안내 유지.

## 8. 성공 기준
1. 마이그레이션이 Neon에 적용되고 두 테이블·FK·인덱스 존재.
2. 세션 생성 → 메시지 저장 → 히스토리 조회가 순서대로 동작. 스트림 후 어시스턴트 메시지가 실제로 저장됨.
3. 타 사용자 세션 접근은 403, 미존재 404, 무토큰 401.
4. 코치가 같은 세션의 이전 발화를 참조(멀티턴 기억) — 히스토리가 LLM 컨텍스트에 포함됨(테스트로 주입 확인).
5. 프론트 `tsc` 0.

## 9. 테스트 전략
- `scripts/coach_session_models_import_test.py` — ORM import·메타.
- `scripts/coach_session_repository_test.py` — 세션 생성·메시지 append·히스토리 순서·독립 세션 쓰기(Neon).
- `scripts/coach_session_endpoint_test.py` — 생성/스트림(ASGI, LLM 키 없을 때 비활성 경로로 어시스턴트 저장 스킵 확인 또는 fake)·end·messages·소유권 403/404·무토큰 401. LLM 호출은 API 키 미설정 경로(기존 "비활성" 분기)로 결정적 테스트.

## 10. 범위 밖 / 후속
- **SP-2b(다음)** — 종료 세션 → LLM 추출 → `SelfModelService.upsert_structured`/`append_evidence(source='coach_extraction')`. `extracted_at`로 멱등. 비활동 자동 마감 스케줄러 잡도 SP-2b(추출 트리거).
- 세션 `title` 자동 요약, 세션 목록 UI, 메시지 페이지네이션은 후속(YAGNI).

## 11. 가정·미해결
- **어시스턴트 저장 시점** — 스트림 정상 완료 시 누적본 저장. 클라 중도 abort 시 서버 제너레이터도 취소되어 저장 안 될 수 있음(허용 — 다음 세션 로드시 없을 뿐). 필요 시 SP-2b 전 보강.
- **동시 스트림** — 한 세션에 동시 다중 스트림은 미가정(프론트가 직렬). 서버 강제 락은 미도입(YAGNI).
- **N(히스토리 윈도우)=20** — 토큰 예산 보고 조정 가능(후속).
