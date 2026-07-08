# hrowth_journey (Roadmap) 작업 기록

## 2026-07-08 — R-1 로드맵 딥 에이전트 라이브 verify + 스펙 현행화(마지막 Task)
- **무엇** — R-1(로드맵 딥 에이전트) 마지막 태스크로 실 DB·실 Anthropic 대상 라이브 verify 스크립트를 작성하고, 기존 로드맵 보유 실사용자(퀘스트 6개·플래너 태스크 2개)로 2회 실행(허용 한도 전부 소진). 스펙 §6·§8·§10 을 구현 실체로 현행화.
- **왜** — Task 1~6(테이블·서비스·병합·프론트 진행률 UI)이 오프라인 테스트로만 검증됐고, `agent.astream(stream_mode=["updates","values"])` 소비부의 실 스트림 형태(튜플 언패킹)와 `roadmap_agent_cheap_model` 기본값(`claude-haiku-4-5`)의 실 API 수용 여부가 미검증 상태였다.
- **어디** —
  - 신규 [`backend/scripts/roadmap_agent_live_verify.py`](../../../scripts/roadmap_agent_live_verify.py) — 사전/사후 퀘스트·플래너 태스크 스냅샷 비교, SSE 완주 관찰, `roadmap_generation_runs` 최종 상태 확인.
  - 소비부 [`roadmap_generation_service.py:131-160`](../hub/services/roadmap_generation_service.py) `_run_inner` — 실행 결과 실 스트림으로 튜플 언패킹·`map_agent_event` 매핑 모두 정상 동작 확인(코드 수정 없음).
  - 설정 [`backend/core/config/settings.py:184-193`](../../../core/config/settings.py) `roadmap_agent_cheap_model`/`roadmap_agent_timeout_s`/`roadmap_agent_recursion_limit` — 모델명은 API 수용 확인(수정 불필요), 타임아웃·recursion_limit 은 아래 검증에서 실사용자 완주 기준 부족 확인(이번 태스크 범위 밖이라 기본값은 미변경).
  - 스펙 [`docs/superpowers/specs/2026-07-05-ai-coach-roadmap-agent-design.md`](../../../../docs/superpowers/specs/2026-07-05-ai-coach-roadmap-agent-design.md) §6(구현 실체+변경 이력+라이브 검증 결과)·§8(R-1 행)·§10(리스크 실증 행 추가).
- **검증** — 라이브 실행 총 5회(대상 `user_id=50885bf5-...`, 사전 퀘스트 6개/done 0/태스크 2개), 예산 튜닝을 거치며 완주(done)까지 도달:
  - **1회차**(기본 `roadmap_agent_timeout_s=300`) — `start`→`market_analyst`→`opportunity_scout` 단계까지 진행 후 300s `TimeoutError` 폴백. 무변경 실패 안전 경로 발동. `RESULT: PASS 3 / FAIL 3`.
  - **2회차**(`ROADMAP_AGENT_TIMEOUT_S=480` 환경변수 임시 상향, 코드 미변경) — `quest_designer`(80%) 도달했으나 `recursion_limit=50` 소진으로 실패. `RESULT: PASS 3 / FAIL 3`.
  - 결론(1~2회차) — Risk 1(스트림 튜플 언패킹)·Risk 2(모델명 거부) 둘 다 **미발생**. 병목은 시간/스텝 예산 부족으로 판명 → 커밋 `8399fa5`(`roadmap_agent_timeout_s` 300→900, `roadmap_agent_recursion_limit` 50→100 + 오케스트레이터 스텝 절감 프롬프트: write_todos 1회·최종 검토 read_file 1개·초안 그대로 옮겨쓰기)로 재검증.
  - **3회차**(튜닝 후 `timeout=900s`) — `quest_designer`(80%) 도달 후 재차 900s `TimeoutError`(소요 904s). SSE keepalive 틱 수 역산 결과 `opportunity_scout` 한 단계가 ~540~570s 소모. `parse_agent_output` 은 `final_state={}`로 호출조차 안 돼 파싱 버그 가능성 배제 — 순수 wall-clock 부족 확정. `RESULT: PASS 3 / FAIL 3`. 커밋 `111d14d`로 `roadmap_agent_timeout_s` 900→1500 재상향.
  - **4회차**(`timeout=1500s`) — docker exec 셸 자체 타임아웃이 프로세스를 강제 종료(`error='cancelled'`) — 에이전트 실행 도중 CancelledError 안전망이 정상 작동해 run 을 `failed`로 남기고 기존 데이터는 무손상 보존됨을 확인. 근본 병목 분석: `opportunity_scout` 의 `fetch_url`(WaterCrawl, 호출당 ~45s)을 haiku 가 tool 호출 상한 지시를 지키지 않고 반복 호출. 커밋 `0412e2a`로 scout tools 를 `get_chance_matches`+`web_search`만으로 좁히고(fetch_url 제외) 프롬프트에서 fetch_url 문구 제거.
  - **5회차(최종, `timeout=1500s`+fetch_url 제거)** — **완주 성공**. 소요 약 4분(이전 대비 대폭 단축). 이벤트: `start`→`market_analyst`→`opportunity_scout`→`quest_designer`→`saving`→`done`. `result={'source': 'deep_agent', 'quest_count': 10, 'tasks_seeded': 12, 'roadmap_id': 3}`. `RESULT: PASS 7 / FAIL 0`(발주 성공·progress 수신·done 종결·결과 소스 기록·퀘스트 저장·run succeeded·시드 수 정합 전부 PASS). 병합 사후 확인 — 기존 퀘스트 6개(`root`·`learn-python-advanced`·`sql-database-design`·`api-development`·`system-architecture`·`startup-opportunity-exploration`) **6/6 quest_key 전부 재사용**, 신규 4개(`avoid-semiconductor-pivot`·`capstone-data-service`·`gap-signal-mapping`·`startup-support-program-scan`) 추가로 총 10개. 태스크 2→14(+12) 시드, `post_task_count - pre_task_count == tasks_seeded` 정합 확인.
  - done 상태 퀘스트가 이번 대상자에 없어 "기존 done 보존" 분기는 이번에도 미발동(설계상 정상 — 다른 done 보유 사용자로 별도 검증 필요).
- **후속** — R-1 완주 검증 완료. done 상태 퀘스트 보유 사용자 대상 "기존 done 보존(생존 key)" 케이스는 별도 사용자로 재검증 필요. `opportunity_scout` 에서 제거한 `fetch_url`(웹 페이지 본문 읽기)이 향후 "공고 원문 상세 확인" 품질에 영향을 줄 수 있어 실사용 피드백에 따라 재도입 여부 검토.

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
