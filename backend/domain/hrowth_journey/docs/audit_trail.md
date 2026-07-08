# hrowth_journey (Roadmap) 작업 기록

## 2026-07-08 — R-1 로드맵 딥 에이전트 라이브 verify + 스펙 현행화(마지막 Task)
- **무엇** — R-1(로드맵 딥 에이전트) 마지막 태스크로 실 DB·실 Anthropic 대상 라이브 verify 스크립트를 작성하고, 기존 로드맵 보유 실사용자(퀘스트 6개·플래너 태스크 2개)로 2회 실행(허용 한도 전부 소진). 스펙 §6·§8·§10 을 구현 실체로 현행화.
- **왜** — Task 1~6(테이블·서비스·병합·프론트 진행률 UI)이 오프라인 테스트로만 검증됐고, `agent.astream(stream_mode=["updates","values"])` 소비부의 실 스트림 형태(튜플 언패킹)와 `roadmap_agent_cheap_model` 기본값(`claude-haiku-4-5`)의 실 API 수용 여부가 미검증 상태였다.
- **어디** —
  - 신규 [`backend/scripts/roadmap_agent_live_verify.py`](../../../scripts/roadmap_agent_live_verify.py) — 사전/사후 퀘스트·플래너 태스크 스냅샷 비교, SSE 완주 관찰, `roadmap_generation_runs` 최종 상태 확인.
  - 소비부 [`roadmap_generation_service.py:131-160`](../hub/services/roadmap_generation_service.py) `_run_inner` — 실행 결과 실 스트림으로 튜플 언패킹·`map_agent_event` 매핑 모두 정상 동작 확인(코드 수정 없음).
  - 설정 [`backend/core/config/settings.py:184-193`](../../../core/config/settings.py) `roadmap_agent_cheap_model`/`roadmap_agent_timeout_s`/`roadmap_agent_recursion_limit` — 모델명은 API 수용 확인(수정 불필요), 타임아웃·recursion_limit 은 아래 검증에서 실사용자 완주 기준 부족 확인(이번 태스크 범위 밖이라 기본값은 미변경).
  - 스펙 [`docs/superpowers/specs/2026-07-05-ai-coach-roadmap-agent-design.md`](../../../../docs/superpowers/specs/2026-07-05-ai-coach-roadmap-agent-design.md) §6(구현 실체+변경 이력+라이브 검증 결과)·§8(R-1 행)·§10(리스크 실증 행 추가).
- **검증** — 라이브 실행 2회(허용 한도 전부 사용, 대상 `user_id=50885bf5-...`, 사전 퀘스트 6개/done 0/태스크 2개):
  - **1회차**(기본 `roadmap_agent_timeout_s=300`) — `발주 성공`·`progress 이벤트 수신` PASS, `start`→`market_analyst`→`opportunity_scout` 단계까지 진행 후 300s 타임아웃(`TimeoutError`)으로 폴백 진입. 기존 로드맵 보유자라 "무변경 실패" 안전 경로 발동(run `failed`/`agent_output_invalid`) → `done 종결`·`결과 소스 기록`·`run succeeded` FAIL(설계상 예상된 결과). `RESULT: PASS 3 / FAIL 3`.
  - **2회차**(`ROADMAP_AGENT_TIMEOUT_S=480` 환경변수로 임시 상향 — 코드 미변경) — 타임아웃 전에 `quest_designer` 단계(80%)까지 도달했으나 LangGraph `recursion_limit=50` 도달로 실패(`Recursion limit of 50 reached`). 동일하게 무변경 실패 경로로 안전 종료. `RESULT: PASS 3 / FAIL 3`.
  - **사후 DB 확인** — 두 실행 모두 `roadmap_generation_runs.status='failed'`, `error='agent_output_invalid'`(소요 ~305s/~315s). 퀘스트 6개(상태 불변)·플래너 태스크 2개 완전히 무손상 보존 확인 — "기존 로드맵 보유자 무변경 실패" 안전장치가 실측으로 검증됨.
  - 결론 — Risk 1(스트림 튜플 언패킹)·Risk 2(모델명 거부) 둘 다 **미발생**(정상 동작 확인, 코드 수정 없음). 딥 에이전트 자체의 "완주(done)" 경로는 이번 실사용자 컨텍스트 기준 기본 타임아웃/recursion_limit 내에서 확인하지 못했다(후속 필요).
- **후속** — `roadmap_agent_timeout_s`/`roadmap_agent_recursion_limit` 상향 조정 또는 서브에이전트 tool-calling 절감 튜닝 후 재검증(별도 태스크, 실 Anthropic 과금 필요). done 상태 퀘스트가 있는 사용자 대상 "기존 done 보존" 케이스는 이번 대상자에 done 퀘스트가 없어 미검증.

## 2026-07-06 — 플래너(WBS)·노트 탭 풀스택 신설
- **무엇** — Roadmap 탭에 플래너(백로그·스프린트 보드 + 주간 간트 타임라인)와 노트(마크다운 + `[[링크]]` + 백링크) 탭을 풀스택 추가. AI 퀘스트 분해(LLM+결정론 폴백)·여정 지도 "태스크 n/m" 진행률 배지 포함.
- **왜** — 퀘스트 트리(장기 방향)에 실행 계층이 없어 일정 관리 불가. 사용자 요구: WBS + 노션/옵시디언식 메모. 스펙 `docs/superpowers/specs/2026-07-06-roadmap-planner-notes-design.md` · 플랜 `docs/superpowers/plans/2026-07-06-roadmap-planner-notes.md`.
- **어디** — 테이블 3종 마이그레이션 [e7b3a1c5d9f2](../../../alembic/versions/e7b3a1c5d9f2_add_planner_and_notes_tables.py): `planner_sprints`·`planner_tasks`(sprint_id NULL=백로그, FK SET NULL)·`roadmap_notes`(user_id+title 유니크). 백엔드 [planner_repository.py](../hub/repositories/planner_repository.py)·[planner_service.py](../hub/services/planner_service.py)·[note_repository.py](../hub/repositories/note_repository.py)·[note_service.py](../hub/services/note_service.py)·[roadmap_routor.py](../../../api/v1/roadmap/roadmap_routor.py) API 14종·[client.py](../../../core/llm/client.py) `decompose_quest`. 프론트 `www.yeotaeho.kr/src/components/features/roadmap/planner/`(PlannerTab·BoardView·TimelineView·TaskCard)·`notes/`(NotesTab·NoteEditor)·`lib/api/planner.ts`·`notes.ts`·`hooks/usePlanner.ts`·`useNotes.ts`·`data/plannerMock.ts`. 의존성: @dnd-kit 3종·react-markdown.
- **검증** — 순수 테스트 5스크립트 59/59 PASS. 라이브 verify 18/18 PASS([planner_notes_live_verify.py](../../../scripts/planner_notes_live_verify.py) — 실 Neon 보드 CRUD·소유권 가드·FK SET NULL 복귀·decompose 폴백·백링크·중복 제목, 잔여물 0). 프론트 tsc 0·build 성공·프로덕션 라이브 확인(4탭·보드·간트·위키링크/백링크). 커밋 84161d2..dce0a86(17커밋). 태스크별 리뷰 전건 Approved — 수정 5건 반영(스프린트 소유권 가드·PATCH null 날짜 400·드래그 로컬 상태 리셋·노트 입력 보존/선택 동기화·분해 슬롯 라이브 게이팅).
- **후속** — 타임라인 bar 드래그-리사이즈 · 노트 자동저장 디바운스 · 노트 연결 편집 picker+태스크 카드 노트 아이콘 · @tailwindcss/typography(prose 스타일) · patch_sprint 역전 날짜범위 검증 · 라우터 TestClient 테스트 · pnpm lint 선재 파손 수정 · 타임라인 today 자정 갱신.

## 2026-06-28 — RoadmapPlanner 맥락에 Pulse movers·Gap 주입
- **무엇** — RoadmapPlanner LLM 입력 맥락에 최신 Pulse 상위 모멘텀 섹터·최근 활성 Gap 미해결 기회를 추가. 페르소나+목표+관심사만 쓰던 것을 시장 트렌드 반영으로 강화.
- **왜** — 개인화 로드맵이 사용자 데이터뿐 아니라 시장 흐름과 연결되도록.
- **어디** — [roadmap_repository.py](../hub/repositories/roadmap_repository.py) `fetch_top_movers`(최신일 모멘텀순)·`fetch_recent_gaps`(활성 최근). [roadmap_planner_service.py](../hub/services/roadmap_planner_service.py) `build_planner_context(movers·gaps 옵션 인자, 없으면 섹션 생략)`.
- **검증** — `scripts/roadmap_planner_parse_test.py` 21/21(맥락 주입 케이스 추가), `/refine` 라이브 source=llm·7퀘스트. 커밋 09c7b29.

## 2026-06-28 — LLM RoadmapPlanner: /refine 개인화 로드맵 실제 생성
- **무엇** — `/api/roadmap/refine` 을 internal 스텁에서 인증 사용자 LLM 생성 엔드포인트로 전환. 페르소나·목표 직무·관심 키워드로 RPG 퀘스트 트리를 LLM 생성, 실패/무키 시 결정론 템플릿 폴백.
- **왜** — Roadmap을 목업 페르소나 전제에서 실데이터·LLM 기반 개인화로 전환(3단 계획의 마지막).
- **어디** — [core/llm/client.py](../../../core/llm/client.py) `_ROADMAP_SYSTEM_PROMPT`·순수 `_parse_roadmap`(루트 1개·난이도/상태 보정·pillars≤3)·`generate_roadmap`. [roadmap_planner_service.py](../hub/services/roadmap_planner_service.py)(`build_planner_context` 순수·`template_roadmap` 폴백 + 페르소나/싱크 공유 DB read→`save_roadmap`). [roadmap_repository.py](../hub/repositories/roadmap_repository.py) 리드/라이트 추가. 프론트 JourneyMapTab "내 로드맵 생성" 버튼.
- **검증** — `scripts/roadmap_planner_parse_test.py` 18/18, `scripts/roadmap_refine_test.py` 8/8(실측 source=llm·6퀘스트), `roadmap_endpoint_test.py` 11/11, tsc 0. 커밋 8a371b0.
- **후속** — PersonaForm→자동 /refine 트리거 연계, RoadmapPlanner에 Pulse movers·Gap 맥락 주입.

## 2026-06-28 — 프론트 로컬목업 → /api/roadmap/* 라이브 배선
- **무엇** — RoadmapView(JourneyMapTab·GrowthArchiveTab)의 로컬 하드코딩 목업을 백엔드 API로 전환. 로그인+로드맵 있으면 라이브, 없으면 로컬 목업 폴백("예시 로드맵" 배지). 아카이브 저장 영속화.
- **왜** — 백엔드 계약(목업 수직 슬라이스) 확정 후 프론트 연동(3단 계획 1번).
- **어디** — `www.yeotaeho.kr/src/lib/api/roadmap.ts`(fetchJourney·fetchArchive·upsertArchiveDay), `hooks/useRoadmap.ts`(useJourney·useArchive·useUpsertArchiveDay), 두 탭 컴포넌트. apiClient 토큰 자동주입, useDashboard 패턴 동일.
- **검증** — tsc --noEmit 0 에러(프로젝트 전역). 백엔드 계약은 엔드포인트 11/11. 커밋 61fca47.

## 2026-06-28 — Roadmap 목업 수직 슬라이스 가동
- **무엇** — 빈 스텁이던 Roadmap 도메인에 여정 개요·성장 아카이브를 서빙하는 목업 수직 슬라이스 구현. 프론트 RoadmapView가 기대하는 퀘스트 트리·아카이브 모양 그대로 서빙.
- **왜** — market_insight·master 라이브 완성 후 다음 구현 대상으로 Roadmap 선택. 프론트는 로컬 하드코딩 목업 상태라 백엔드 계약 확정·영속성이 필요.
- **어디** — 테이블 4종 마이그레이션 [c4e7a9d2f6b1](../../../alembic/versions/c4e7a9d2f6b1_add_roadmap_and_persona_tables.py): `user_personas`(user_intelligence 소유), `user_roadmaps`·`roadmap_quests`(parent_key 자기참조)·`growth_logs`(멱등). 라우터 [roadmap_routor.py](../../../api/v1/roadmap/roadmap_routor.py)(`/api/roadmap/journey·archive·refine`), 순수조립 [journey_assembler.py](../hub/services/journey_assembler.py), 시드 [seed_roadmap_mock.py](../../../scripts/seed_roadmap_mock.py).
- **검증** — `scripts/roadmap_journey_assembler_test.py` 12/12, `scripts/roadmap_endpoint_test.py` 11/11 PASS (Neon 실DB, roadmap_id=3). 커밋 eeb6de1.
- **후속** — ① 프론트 로컬목업→API 배선 ② coach/user_intelligence 페르소나 수집 ③ LLM RoadmapPlanner로 `/refine` 실제 생성. LLM 생성·페르소나 수집은 이번 범위 밖(목업 페르소나 전제).
