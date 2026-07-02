# 상담실 이전 — 코치 대화 엔진을 user_intelligence 로 이동 설계

2026-07-03 확정. `/coach`에 얹혀 있던 대화·세션·자기모델 추출 엔진을 **AI 상담실(`/consult`)** 로 옮기고,
백엔드를 `ai_coach` → `user_intelligence` 도메인으로 이전한다. 상담실은 성격·성향·자기이해 발견을
담당하는 상담사이고, 로드맵 구성은 코치에게 위임하므로 상담 엔진에서 로드맵 로직을 제거한다.

## 배경

- 사용자 의도: `/consult`(AI 상담실)에서 성격 분석·성향 파악. 그러나 실제 대화 엔진(SSE·세션·자기모델 추출)은
  `ai_coach` 도메인에 구현되어 `/coach`에 노출됨. `/consult`는 완전 목업(하드코딩 Deep Discovery + 레이더).
- 자기모델 데이터층(`user_self_model`·`user_self_model_evidence`·`self_model_service`)은 이미
  `user_intelligence`에 있음. 대화 엔진을 같은 도메인으로 옮기면 "대화→자기모델" 파이프라인이 한 도메인에 응집된다.

## 확정 결정 (사용자 확답)

| 결정 | 선택 |
|---|---|
| 상담실↔코치 구조 | **분리 유지** — 상담실=대화·자기모델, 코치=로드맵 전용 |
| 백엔드 코드 위치 | **`user_intelligence`로 이동** |
| rename 깊이 | **테이블까지 전수 개명** (Neon 마이그레이션) |
| `/coach` 탭 즉시 운명 | **"로드맵 코치 준비 중" 플레이스홀더** + `/roadmap` 링크 |

## A. 백엔드 이동·개명 (ai_coach → user_intelligence)

| 현재 (`domain/ai_coach/`) | 이동 후 (`domain/user_intelligence/`) | 개명 |
|---|---|---|
| `models/bases/coach_session.py` | `models/bases/consult_session.py` | `CoachSession`→`ConsultSession`, 테이블 `consult_sessions` |
| `models/bases/coach_message.py` | `models/bases/consult_message.py` | `CoachMessage`→`ConsultMessage`, 테이블 `consult_messages` |
| `hub/repositories/coach_session_repository.py` | `hub/repositories/consult_session_repository.py` | `CoachSessionRepository`→`ConsultSessionRepository` |
| `hub/repositories/coach_repository.py` | `hub/repositories/consult_context_repository.py` | `CoachRepository`→`ConsultContextRepository`, **로드맵 쿼리 삭제** |
| `hub/services/coach_context.py` | `hub/services/consult_context.py` | 순수 헬퍼(윈도우 분할·조립) 그대로 |
| `hub/services/coach_service.py` | `hub/services/consult_service.py` | `CoachService`→`ConsultService`, `build_coach_context`→`build_consult_context` |
| `hub/services/self_model_extraction_service.py` | 동일 경로로 이동 | 클래스명 유지 (`SelfModelExtractionService`), 임포트 경로만 변경 |

- `ai_coach` 도메인 폴더는 **삭제하지 않고 빈 스캐폴딩으로 보존**(향후 로드맵 코치용). 이동한 `.py`만 제거.
- `self_model_extraction_service`는 `ConsultSessionRepository`·`SelfModelService`를 참조하도록 임포트 갱신
  (둘 다 이제 `user_intelligence` 동일 도메인).

### 외부 참조 갱신

- `alembic/env.py` — `coach_session`/`coach_message` 임포트를 `user_intelligence.models.bases.consult_*`로.
- `api/v1/coach/coach_routor.py` → `api/v1/consult/consult_routor.py` — `prefix="/consult"`, `tags=["consult"]`,
  `ConsultService` 임포트. 라우트 4개 경로 `/coach/*`→`/consult/*`(sessions·stream·end·messages).
- `main.py` — `coach_v1_router`→`consult_v1_router` 임포트·등록.
- `core/scheduler.py` — `_job_self_model_extract` 의 `SelfModelExtractionService` 임포트 경로를 user_intelligence로.

## B. 맥락 주입에서 로드맵 제거 + 상담사 프롬프트

- `consult_context_repository.fetch_context` — `user_personas`(페르소나 skills·summary) + `pulse_metrics_log`
  (시장 상위 섹터) 만 반환. **`user_roadmaps`·`roadmap_quests` 쿼리 2개 삭제**, 반환 dict 에서 `roadmap`·`quests` 제거.
- `build_consult_context` — 페르소나·시장 섹터만 조립. **`"- 로드맵:"`·`"- 진행 중/예정 퀘스트:"` 주입 삭제.**
- **신규 `_CONSULT_SYSTEM_PROMPT`** (`core/llm/client.py`): 청년 진로 **상담사** 역할. 성격·성향·가치관·호불호를
  대화로 파악하고 사용자가 미처 몰랐던 강점·패턴을 짚어준다. 막연한 응원 대신 통찰 질문. 로드맵·퀘스트 언급 없음.
  간결(3~6문장). `ConsultService`는 이 프롬프트를 사용. 기존 `_COACH_SYSTEM_PROMPT`는 향후 로드맵 코치용으로 보존.

## C. 프론트

- `components/features/coach/` → `components/features/consult/`: `CoachView.tsx`→`ConsultView.tsx`
  (컴포넌트 `CoachView`→`ConsultView`), `InsightWalletPanel.tsx` 동반 이동. `lib/api/coach.ts`→`lib/api/consult.ts`
  (엔드포인트 `/api/coach/*`→`/api/consult/*`, 함수·타입명 consult 계열).
- `app/(main)/consult/page.tsx` — 목업 전체 교체 → `<ConsultView />`. (목업의 레이더·라이브 키워드·`/roadmap` CTA 제거.)
- `app/(main)/coach/page.tsx` — "로드맵 코치 준비 중" 플레이스홀더 + `/roadmap` 링크 카드.
- `MainTabBar.tsx` — 라벨(상담실·코치) 유지. `/consult`·`/coach` 경로 그대로.

## D. 마이그레이션 (수기 · Neon 승인 후 적용)

autogenerate 는 rename 을 drop+add 로 오탐하므로 **수기 작성**. 단일 리비전:

- `op.rename_table('coach_sessions', 'consult_sessions')` · `op.rename_table('coach_messages', 'consult_messages')`
- 인덱스: `ix_coach_sessions_user`→`ix_consult_sessions_user`, `ix_coach_messages_session`→`ix_consult_messages_session`
  (`ALTER INDEX ... RENAME TO`).
- FK: `fk_coach_session_user`→`fk_consult_session_user`, `fk_coach_message_session`→`fk_consult_message_session`
  (`ALTER TABLE ... RENAME CONSTRAINT`).
- 컬럼: `user_self_model_evidence.coach_session_ref`→`consult_session_ref` (`alter_column ... new_column_name`).
- 데이터 값(**유일한 라이브 값 변경**, 되돌리기 가능): `UPDATE user_self_model SET source='consult_extraction'
  WHERE source='coach_extraction'` + `UPDATE user_self_model_evidence SET source='consult_extraction'
  WHERE source='coach_extraction'`. 상수 `SOURCE_COACH`/`SOURCE`(self_model_service·extraction_service) 값도 갱신.
  downgrade 는 모든 rename·UPDATE 역순.
- `backend/docs/erd.md` §6.6 coach 스키마 표기를 consult 로 갱신.

## E. 테스트

- 백엔드 스크립트 6개 이동·개명·임포트 갱신(assertion 유지):
  `coach_context_test`→`consult_context_test`, `coach_service_test`→`consult_service_test`,
  `coach_session_repository_test`→`consult_session_repository_test`,
  `coach_session_models_import_test`→`consult_session_models_import_test`,
  `coach_stream_test`→`consult_stream_test`, `coach_extract_repo_test`→`consult_extract_repo_test`.
  `self_model_extraction_test`는 임포트 경로만 갱신.
- **추가 단정**: `build_consult_context` 출력에 "로드맵"·"퀘스트" 문자열이 없음(로드맵 제거 회귀 가드).
- 스케줄러 스모크(`self_model_extract_job_test`) 임포트 경로 갱신 후 green.
- 프론트 `pnpm exec tsc --noEmit` 0 에러.

## F. 범위 밖 (후속)

- **SP-4**: 자기모델 레이더·키워드 라이브 시각화를 실데이터(`GET /api/user/self-model`)로 연결(현재 목업 레이더 제거만).
- 로드맵 코치 백엔드(`ai_coach` 재활성) 구현.
- 상담→코치 핸드오프(상담 결과 자기모델을 로드맵 생성 입력으로).
- InsightWalletPanel(인사이트 지갑)의 상담실 적합성 재검토(현재 이동만, 로직 변경 없음).

## 파일 지도

| 영역 | 파일 |
|---|---|
| 모델 | `domain/user_intelligence/models/bases/consult_session.py`·`consult_message.py` |
| 리포 | `.../hub/repositories/consult_session_repository.py`·`consult_context_repository.py` |
| 서비스 | `.../hub/services/consult_service.py`·`consult_context.py`·`self_model_extraction_service.py` |
| LLM | `core/llm/client.py` (`_CONSULT_SYSTEM_PROMPT`) |
| API | `api/v1/consult/consult_routor.py` · `main.py` |
| 스케줄러·마이그 | `core/scheduler.py` · `alembic/versions/<new>` · `alembic/env.py` |
| 프론트 | `components/features/consult/*` · `lib/api/consult.ts` · `app/(main)/consult/page.tsx` · `app/(main)/coach/page.tsx` |
