# auth 작업 기록

## 2026-06-30 — 기본정보(user_profiles) 수직 신설 — 개인화 Phase 1
- **무엇** — 선택적 사용자 기본정보(출생연도·성별·지역·현재상태·학력단계) 저장·조회 수직 신설. 전부 nullable, `source` provenance 컬럼으로 미래 coach 추출 경로 재사용 대비. 데모그래픽이라 임베딩 직렬화에서는 제외(편향 방지) — auth 도메인에 격리.
- **왜** — Sync/Chance 개인화가 target_job+interest_keywords만 쓰던 "개인화 병목" 해소를 위한 사용자 데이터 풍부화(Phase 1 데이터층). 강요 없이 선택 입력.
- **어디** — ORM [user_profile.py](../models/bases/user_profile.py)(테이블 `user_profiles`, 마이그레이션 `a3f7c1e9d2b4`) · [profile_repository.py](../hub/repositories/profile_repository.py)(text SQL ON CONFLICT) · [profile_service.py](../hub/services/profile_service.py)(null 기본값·source=user_form 고정) · 라우터 [user_routor.py](../../../api/v1/user/user_routor.py)(`GET/PUT /api/user/profile`, auth).
- **검증** — `scripts/profile_endpoint_test.py` 9/9 PASS(Neon 실DB, gender null 부분입력 케이스 포함). `scripts/user_models_import_test.py` 19/19. 커밋 75b779f..01fe097.
- **후속** — Phase 2: `_user_text()`는 데모그래픽 제외 유지. `user_routor.get_current_user_id`를 공용 `core.api_guards.get_authenticated_user_id`로 수렴(중복 제거). 프론트 프로필/온보딩 입력(Phase 3).
