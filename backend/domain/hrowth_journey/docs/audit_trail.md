# hrowth_journey (Roadmap) 작업 기록

## 2026-06-28 — Roadmap 목업 수직 슬라이스 가동
- **무엇** — 빈 스텁이던 Roadmap 도메인에 여정 개요·성장 아카이브를 서빙하는 목업 수직 슬라이스 구현. 프론트 RoadmapView가 기대하는 퀘스트 트리·아카이브 모양 그대로 서빙.
- **왜** — market_insight·master 라이브 완성 후 다음 구현 대상으로 Roadmap 선택. 프론트는 로컬 하드코딩 목업 상태라 백엔드 계약 확정·영속성이 필요.
- **어디** — 테이블 4종 마이그레이션 [c4e7a9d2f6b1](../../../alembic/versions/c4e7a9d2f6b1_add_roadmap_and_persona_tables.py): `user_personas`(user_intelligence 소유), `user_roadmaps`·`roadmap_quests`(parent_key 자기참조)·`growth_logs`(멱등). 라우터 [roadmap_routor.py](../../../api/v1/roadmap/roadmap_routor.py)(`/api/roadmap/journey·archive·refine`), 순수조립 [journey_assembler.py](../hub/services/journey_assembler.py), 시드 [seed_roadmap_mock.py](../../../scripts/seed_roadmap_mock.py).
- **검증** — `scripts/roadmap_journey_assembler_test.py` 12/12, `scripts/roadmap_endpoint_test.py` 11/11 PASS (Neon 실DB, roadmap_id=3). 커밋 eeb6de1.
- **후속** — ① 프론트 로컬목업→API 배선 ② coach/user_intelligence 페르소나 수집 ③ LLM RoadmapPlanner로 `/refine` 실제 생성. LLM 생성·페르소나 수집은 이번 범위 밖(목업 페르소나 전제).
