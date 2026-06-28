# hrowth_journey (Roadmap) 작업 기록

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
