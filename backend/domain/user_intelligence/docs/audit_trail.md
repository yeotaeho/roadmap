# user_intelligence 작업 기록

## 2026-06-30 — 개인화 Phase 3: 프론트 선택 입력 섹션·완성도 미터·온보딩 (프론트 전용)
- **무엇** — Phase 1/2 백엔드 API(`/api/user/profile`·`/api/preferences`·확장 `/api/persona`·`/api/user/sync-profile`)에 프론트를 배선. 프로필 페이지에 자기완결 선택 섹션(기본정보·성향·스펙·관심) + 완성도 미터, 로그인 후 1회 `/onboarding`(건너뛰기), 관심키워드 풀 12섹터+직무군 재설계. 백엔드 무변경.
- **왜** — 사용자가 부담 없이(전부 선택) 성향·스펙을 입력해 Sync/Chance 개인화 품질을 끌어올리는 입력 경로 완성. 가입 직후 토큰 없는 실제 auth 플로우 반영해 온보딩은 로그인 후 트리거.
- **어디** — 프론트 `www.yeotaeho.kr/src/`: `lib/api/{profile,preferences}.ts`·`hooks/{useProfile,usePreferences}.ts`·`data/personalizationOptions.ts`·`components/features/profile/{ChipSelect,BasicInfoSection,PreferencesSection,InterestSection,CompletionMeter}.tsx`+`PersonaForm.tsx`(스펙 4필드)·`app/(main)/profile/page.tsx`·`app/onboarding/page.tsx`·`lib/onboarding.ts`·3 OAuth 콜백. (user_intelligence 도메인 데이터를 서빙하는 프론트라 여기 기록.)
- **검증** — `pnpm exec tsc --noEmit` 0 에러(프론트 unit test 없음). 최종 리뷰(opus): 전체교체 데이터보존·camelCase 계약 백엔드 대비 end-to-end 검증, Critical/Important 0. 커밋 06a4c40..7b46bbf.
- **후속** — useSyncProfile 공유훅 추출 · onboarding 인증가드 early-return · signup 페이지 기존 8 뉴스카테고리→신규 풀 통일.

## 2026-06-30 — 성향·선호(user_preferences) 신설 + persona 스펙 4필드 확장 — 개인화 Phase 1
- **무엇** — (1) 성향·선호(disposition) 수직 신설: `user_preferences`(작업성향·선호 기업규모·근무형태·일의 가치) + `GET/PUT /api/preferences`. (2) 기존 `user_personas`에 스펙 심화 4 JSONB 컬럼(자격증·어학·링크·프로젝트) 추가 + `/api/persona` 확장. 전부 nullable·선택 입력, `source` provenance(미래 coach 추출 재사용 대비).
- **왜** — 개인화 병목(target_job+keywords만 사용) 해소. 성향·스펙은 의미 데이터라 Phase 2에서 임베딩 직렬화 대상 — user_intelligence 도메인에 배치해 사전 분리.
- **어디** — 신규 ORM [user_preference.py](../models/bases/user_preference.py)(테이블 `user_preferences`) · [preference_repository.py](../hub/repositories/preference_repository.py)(work_values JSONB CAST) · [preference_service.py](../hub/services/preference_service.py) · 신규 라우터 [preferences_routor.py](../../../api/v1/preferences/preferences_routor.py)(`/api/preferences`, main.py 등록). persona 확장: [persona_repository.py](../hub/repositories/persona_repository.py)·[persona_service.py](../hub/services/persona_service.py)·[persona_routor.py](../../../api/v1/persona/persona_routor.py)·[user_persona.py](../models/bases/user_persona.py). 마이그레이션 `a3f7c1e9d2b4`(Neon 적용).
- **검증** — `scripts/preferences_endpoint_test.py` 8/8 · `scripts/persona_endpoint_test.py` 13/13(기존 9+신규 4) PASS(Neon 실DB). 커밋 465829d·f0e1ad3·594fb00.
- **후속** — Phase 2: `_user_text()`에 성향(한국어 라벨)·스펙(skill/cert/project) 직렬화 + embed_repository JOIN + 재임베딩 보장 + Chance 키워드 가산. 대화 추출(ai_coach) 파이프라인은 추출-레디 설계만 완료, 구현은 별도 스펙.

## 2026-06-28 — PersonaForm 저장 시 로드맵 자동 재생성 연계
- **무엇** — 페르소나 저장 성공 후 `/api/roadmap/refine` 자동 호출 → 역량 입력 즉시 로드맵에 반영. 재생성 실패는 저장 성공을 막지 않음(try/catch).
- **왜** — 페르소나 수집과 로드맵 생성 사이 수동 단계 제거(역량 입력→개인화 로드맵 즉시 루프).
- **어디** — `www.yeotaeho.kr/src/components/features/profile/PersonaForm.tsx`(useRefreshRoadmap 연계, 버튼 "로드맵 생성 중…").
- **검증** — tsc --noEmit 0 에러. 커밋 7fcc486.

## 2026-06-28 — 구조화 폼 페르소나 수집(도메인 첫 구현)
- **무엇** — 빈 스텁이던 user_intelligence 도메인에 페르소나(스킬·경험·학력·요약) 구조화 폼 수집 기능 구현. Roadmap·Sync 분석의 실데이터 기반.
- **왜** — Roadmap을 실데이터 기반으로 전환하려면 사용자 역량 데이터 수집 주체가 필요. 대화형 LLM 추출 대신 결정론 폼으로 확정(LLM은 RoadmapPlanner에서).
- **어디** — [persona_repository.py](../hub/repositories/persona_repository.py)·[persona_service.py](../hub/services/persona_service.py)(source=user_form) + 라우터 [persona_routor.py](../../../api/v1/persona/persona_routor.py)(`GET/PUT /api/persona`, auth, Pydantic 검증). ORM은 [user_persona.py](../models/bases/user_persona.py)(테이블 `user_personas`, 마이그레이션 c4e7a9d2f6b1). 프론트 `www.yeotaeho.kr/src/lib/api/persona.ts`·`hooks/usePersona.ts`·`components/features/profile/PersonaForm.tsx`(프로필 페이지 마운트).
- **검증** — `scripts/persona_endpoint_test.py` 9/9 PASS(Neon 실DB), tsc --noEmit 0 에러. 커밋 11e7c8c.
- **후속** — PersonaForm 저장 후 자동 로드맵 재생성(/refine) 연계. 대화형 추출(ai_coach SSE)은 향후 별도 레이어.
