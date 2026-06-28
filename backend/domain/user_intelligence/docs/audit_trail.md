# user_intelligence 작업 기록

## 2026-06-28 — 구조화 폼 페르소나 수집(도메인 첫 구현)
- **무엇** — 빈 스텁이던 user_intelligence 도메인에 페르소나(스킬·경험·학력·요약) 구조화 폼 수집 기능 구현. Roadmap·Sync 분석의 실데이터 기반.
- **왜** — Roadmap을 실데이터 기반으로 전환하려면 사용자 역량 데이터 수집 주체가 필요. 대화형 LLM 추출 대신 결정론 폼으로 확정(LLM은 RoadmapPlanner에서).
- **어디** — [persona_repository.py](../hub/repositories/persona_repository.py)·[persona_service.py](../hub/services/persona_service.py)(source=user_form) + 라우터 [persona_routor.py](../../../api/v1/persona/persona_routor.py)(`GET/PUT /api/persona`, auth, Pydantic 검증). ORM은 [user_persona.py](../models/bases/user_persona.py)(테이블 `user_personas`, 마이그레이션 c4e7a9d2f6b1). 프론트 `www.yeotaeho.kr/src/lib/api/persona.ts`·`hooks/usePersona.ts`·`components/features/profile/PersonaForm.tsx`(프로필 페이지 마운트).
- **검증** — `scripts/persona_endpoint_test.py` 9/9 PASS(Neon 실DB), tsc --noEmit 0 에러. 커밋 11e7c8c.
- **후속** — PersonaForm 저장 후 자동 로드맵 재생성(/refine) 연계. 대화형 추출(ai_coach SSE)은 향후 별도 레이어.
