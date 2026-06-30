# 선택적 사용자 데이터로 개인화 엔진 강화 — 설계

- **작성일** — 2026-06-30
- **도메인** — `auth`(기본정보·키워드) · `user_intelligence`(성향·스펙) · `market_insight`(임베딩 통합)
- **상태** — 승인됨, 구현 진행 예정

## 1. 배경·목표

인증·프로필·페르소나 인프라는 라이브 완성됐다(OAuth 3사·JWT·`user_personas` 폼·프로필 페이지). 그러나 개인화 추천(Sync/Chance)이 소비하는 사용자 신호는 `user_sync_profiles.target_job` + `interest_keywords` **단 2개뿐**이라, 메모리에 "개인화 병목"으로 기록돼 있다.

개인화 엔진은 **임베딩 텍스트 기반**이다. [embed_service.py:63](../../../domain/market_insight/hub/services/embed_service.py)의 `_user_text()`가 `target_job + interest_keywords`를 한 줄 텍스트로 합쳐 `text-embedding-3-large`로 임베딩 → 섹터/공고 임베딩과 코사인 비교(Sync 0.6·트렌드 0.4, Chance 코사인+키워드 가산). 따라서 **새 사용자 필드를 `_user_text()` 직렬화에 넣고 embed 쿼리가 그 필드를 읽게 하면 개인화에 자동 반영**된다.

이번 작업은 **선택적(전부 nullable) 사용자 데이터 4차원**을 추가해 이 신호를 풍부화한다. 모든 필드는 입력 강제가 없어 사용자 부담이 없어야 한다.

### 성공 기준
1. 4개 데이터 차원(기본정보·성향·스펙·키워드)의 테이블/컬럼이 생성되고 전부 nullable이다.
2. 신규 필드를 채운 사용자의 임베딩 텍스트가 그 내용을 포함하고, 데이터 변경 시 재임베딩된다.
3. 각 차원에 폼 입력 API(`GET/PUT`)가 있고 미입력 시 기본값/null을 반환한다.
4. 선택 데이터를 **회원가입(OAuth 후 선택 온보딩 단계)과 프로필 페이지 양쪽에서** 입력할 수 있고, 둘 다 건너뛰기 가능(전부 nullable)하다. 회원가입의 기존 필수 폼(직무+키워드)은 변경되지 않는다.
5. provenance(`source`)와 병합 규칙이 설계돼 있어, 미래 대화 추출 경로가 같은 쓰기 인터페이스를 재사용할 수 있다.
6. 순수함수/엔드포인트 테스트 통과(persona 패턴).

## 2. 핵심 설계 원칙

- **전부 nullable·선택 입력.** 입력 경로는 두 곳 — (a) 회원가입의 **OAuth 후 선택 온보딩 단계**, (b) 프로필 페이지 선택 섹션. 둘 다 건너뛰기 가능하다. 회원가입의 기존 필수 폼(직무+키워드, OAuth 전)은 그대로 유지해 가입 마찰을 늘리지 않는다.
- **개인화 반영 2경로** — 의미 데이터(직무·키워드·성향·스펙)는 임베딩 텍스트에 직렬화. **데모그래픽(나이·성별·지역)은 임베딩에서 제외**(편향·노이즈 방지), 향후 필터링/표시용으로만 보관.
- **추출-레디(extraction-ready)** — 이번엔 폼 경로만 구현하되, 대화 추출이 나중에 얹히도록 provenance·병합 규칙·쓰기 인터페이스를 설계에 못박는다. 대화 추출 파이프라인 구현은 **범위 밖(후속 스펙)**.

## 3. 데이터 모델

`users.id`는 UUID(리셋 `9f2a6d4e1b0c` 이후). 신규 FK는 전부 `UUID(as_uuid=True)` → `users.id` CASCADE. FK가 `users`만이라 sectors-autogenerate 함정 없음.

### 3.1 `user_profiles` — 신규, `auth` 도메인 (기본정보 확장, 전부 nullable)

| 컬럼 | 타입 | 설명 |
|---|---|---|
| user_id | UUID PK, FK users CASCADE | 사용자 |
| birth_year | SMALLINT NULL | 출생연도(나이 대신 — 덜 민감·갱신 불필요) |
| gender | VARCHAR(10) NULL | `male`/`female`/`other` |
| region | VARCHAR(50) NULL | 거주 지역(예: 서울, 경기) |
| current_status | VARCHAR(20) NULL | `student`/`job_seeking`/`employed`/`career_switch` |
| education_level | VARCHAR(20) NULL | `high_school`/`undergrad`/`bachelor`/`master`/`phd` (coarse 1값, `user_personas.education` 상세 기록과 별개) |
| source | VARCHAR(20) NOT NULL DEFAULT `user_form` | provenance — `user_form`/`coach_extraction`/`mock`/`import` |
| updated_at | TIMESTAMPTZ DEFAULT now() | 갱신 |

ORM: `domain/auth/models/bases/user_profile.py`. 기본정보는 정체성에 가깝지만 인증 핵심 `users` 테이블은 건드리지 않고 분리 테이블로 둔다.

### 3.2 `user_preferences` — 신규, `user_intelligence` 도메인 (성향/선호 = disposition, 전부 nullable)

| 컬럼 | 타입 | 설명 |
|---|---|---|
| user_id | UUID PK, FK users CASCADE | 사용자 |
| work_style | VARCHAR(20) NULL | `stability`/`challenge`/`balanced` (안정↔도전) |
| company_size_pref | VARCHAR(20) NULL | `startup`/`sme`/`large`/`public` |
| work_type_pref | VARCHAR(20) NULL | `office`/`remote`/`hybrid` |
| work_values | JSONB NULL | 일의 가치 다중 — 예 `["growth","work_life_balance","autonomy","impact","compensation"]` |
| source | VARCHAR(20) NOT NULL DEFAULT `user_form` | provenance(동일 enum) |
| updated_at | TIMESTAMPTZ DEFAULT now() | 갱신 |

ORM: `domain/user_intelligence/models/bases/user_preference.py`.

### 3.3 `user_personas` 확장 — 기존, `user_intelligence` (스펙 심화, JSONB 4컬럼 추가·nullable)

기존 `education`/`experiences`/`skills`/`summary`/`source` 유지. 다음 4개 JSONB 컬럼 추가:

| 컬럼 | 타입 | 형태 |
|---|---|---|
| certifications | JSONB NULL | `[{name, issuer, year}]` |
| languages | JSONB NULL | `[{language, test, score}]` |
| links | JSONB NULL | `[{type: github\|portfolio\|blog, url}]` |
| projects | JSONB NULL | `[{title, description, role, period, tech_stack: [str]}]` |

`source` enum에 `user_form`/`coach_extraction` 값을 추가 사용(기존 `mock`/`coach_session` 호환 유지).

### 3.4 `user_sync_profiles` 키워드 고도화 — 기존, `auth` (스키마 무변경)

`interest_keywords` JSONB 컬럼 그대로 사용(하위호환·기존 임베딩 경로 유지). **변경은 프론트 선택지 풀 재설계뿐** — 현재 8개 뉴스 카테고리(경제·정치 등) → **12개 산업 섹터 한국어 라벨**(반도체·바이오헬스·AI·핀테크·모빌리티·콘텐츠·에듀·에너지·식품·물류·뷰티·사회서비스) **+ 직무군**(백엔드·데이터·기획·디자인 등) + 자유 커스텀. 섹터명이 Pulse 섹터와 정렬돼 affinity를 직접 강화한다.

## 4. 임베딩 통합 (개인화 자동 반영)

### 4.1 직렬화 확장 — `_user_text()`
[embed_service.py:63](../../../domain/market_insight/hub/services/embed_service.py)의 `_user_text()`를 확장해 다음을 순서대로 직렬화(각 null 필드는 건너뜀):
- 직무(`target_job`) + 관심키워드(`interest_keywords`) — 기존
- **성향** — `work_style`·`work_values`·`work_type_pref`·`company_size_pref`를 한국어 단어로 매핑(예: `challenge`→"도전적", `growth`→"성장"). enum→라벨 매핑은 순수 헬퍼로 분리.
- **스펙** — `skills[].name`·`certifications[].name`·`languages[].language`·`projects[].title`·`projects[].tech_stack`.
- **데모그래픽(`user_profiles`)은 직렬화 제외.**

### 4.2 fetch 쿼리 — embed_repository
`_FETCH_UNEMBEDDED_USERS`([embed_repository.py](../../../domain/market_insight/hub/repositories/embed_repository.py))에 `user_preferences`·`user_personas` **LEFT JOIN** 추가(데이터 없는 사용자도 기존처럼 임베딩). `user_profiles`는 JOIN하지 않음.

### 4.3 재임베딩 보장
`source_version`이 입력 텍스트 SHA256 해시이므로 사용자가 데이터를 채우면 해시가 바뀐다. **`embed_users()`의 "미임베딩 fetch" WHERE 조건이 해시 변경 시 사용자를 재선택하는지 구현 시 반드시 검증**한다. 현재 "임베딩 없음"만 보고 skip한다면, `source_version != 최신 해시`도 재임베딩 대상에 포함하도록 보강한다.

### 4.4 Chance 키워드 가산
[chance_match_service.py:95](../../../domain/market_insight/hub/services/chance_match_service.py)의 `user_terms` 구성에 성향·스펙 핵심어(work_values 라벨, skill명, cert명)를 추가해 키워드 가산점 경로도 강화한다.

## 5. provenance·병합 규칙 (추출-레디)

- 모든 쓰기 테이블에 레코드 단위 `source` 컬럼. 필드 단위 provenance는 지금 도입하지 않음(YAGNI — 추출 스펙에서 재검토).
- **repository/service의 upsert가 `source` 인자를 받는다.** 폼 경로는 `source='user_form'`로만 호출. 미래 코치 추출 경로가 동일 인터페이스를 `source='coach_extraction'`로 재사용.
- **병합 규칙(시행은 추출 단계, 지금은 문서화만)**: `user_form` 값이 우위. `coach_extraction`은 (a) 빈 칸만 채우거나 (b) 충돌 시 덮어쓰지 않고 사용자에게 확인 제안. **무단 덮어쓰기 금지.**

## 6. API (기존 persona 패턴 답습, 전부 auth·선택)

| 메서드·경로 | 대상 | 비고 |
|---|---|---|
| `GET/PUT /api/user/profile` | `user_profiles` | 신규, user 라우터 |
| `GET/PUT /api/preferences` | `user_preferences` | 신규, user_intelligence(persona 라우터 옆) |
| `GET/PUT /api/persona` | `user_personas` | 기존 재사용 — 확장 4필드만 DTO에 추가 |
| `GET/PUT /api/user/sync-profile` | `user_sync_profiles` | 기존 재사용(스키마 무변경) |

- 모든 GET은 미입력 시 기본값/null 반환, PUT은 부분 upsert(`source='user_form'` 고정).
- 응답은 chance/insight 라우터와 동일하게 plain dict + `success` 래핑. PUT 바디는 인라인 Pydantic DTO.
- 신규 라우터는 `main.py`에 등록(`user_intelligence`의 preferences 라우터).

## 7. 서비스·리포지토리

- `domain/auth/hub/services/profile_service.py` + `repositories/profile_repository.py` — `user_profiles` get/upsert.
- `domain/user_intelligence/hub/services/preference_service.py` + `repositories/preference_repository.py` — `user_preferences` get/upsert.
- 기존 `persona_service`/`persona_repository`에 확장 4필드 추가.
- 모든 repo는 기존 패턴대로 `text()` 원시 SQL 또는 ORM 일관 유지(기존 persona repo 방식 답습).
- `embed_service`의 enum→한국어 라벨 매핑은 순수 헬퍼 함수로 분리(테스트 용이).

## 8. 프론트엔드 UX

- 프로필 페이지([www.yeotaeho.kr/src/app/(main)/profile/page.tsx](../../../../www.yeotaeho.kr/src/app/(main)/profile/page.tsx))에 선택 섹션(아코디언) 추가: **기본정보 / 성향·선호 / 스펙(PersonaForm 확장) / 관심 분야**.
- 각 섹션 헤더에 "선택 입력 · 채울수록 추천이 정확해져요" 안내 + 상단 **프로필 완성도 미터**(강요 없는 넛지).
- API 레이어: `lib/api/`에 `profile`·`preferences` 추가, 기존 `persona`·`user`(sync-profile) 확장. 훅은 `usePersona` 패턴.
- 관심 분야 선택지를 12 섹터+직무군 한국어 라벨로 재설계.

### 8.1 회원가입 — OAuth 후 선택 온보딩
- 기존 가입 폼(직무+키워드, OAuth 전)·OAuth 리다이렉트·콜백은 그대로. 신규 사용자(`isNewUser`)가 OAuth 콜백을 마치면(이미 인증 토큰 보유) `/onboarding` 선택 화면으로 라우팅한다.
- `/onboarding`은 위 4개 선택 섹션을 **프로필과 동일한 컴포넌트·인증 PUT API로 재사용**하여 단계별(또는 한 화면)로 제시한다. 각 단계/섹션에 **"나중에 입력"(건너뛰기)** 명시. 건너뛰면 앱 메인으로.
- 미입력 필드는 저장하지 않음(null 유지). 인증 상태이므로 `update-signup-info`/signupToken 확장 불필요 — 실제 `PUT /api/user/profile`·`/api/preferences`·`/api/persona` 호출.
- 기존 사용자(`isSignupComplete`)는 온보딩을 거치지 않고 바로 로그인(프로필에서 언제든 입력).

## 9. 마이그레이션·검증

- **alembic 1 리비전**: `user_profiles`·`user_preferences` 생성 + `user_personas` 4 JSONB 컬럼 추가. 수동 DDL 금지(autogenerate 후 검토). `down_revision = c8f1a2d3e4b5`(현재 head, market_forecast) — 구현 시 `alembic heads`로 재확인.
- `alembic/env.py`에 신규 ORM 2종(`user_profile`·`user_preference`) import 등록.
- **테스트**:
  - `_user_text()` 직렬화 순수함수 테스트 — 신규 필드 포함·null 스킵·enum 라벨 매핑.
  - 재임베딩 테스트 — 데이터 변경 시 `source_version` 변경 → 재선택.
  - 엔드포인트 테스트 — `profile`/`preferences`/확장 `persona` get·upsert·401(persona_endpoint_test 패턴, httpx ASGITransport 인프로세스).
  - 프론트 `tsc` 0 + 폼 동작.
- **DB 적용은 사용자 승인 후 실행**(Neon 단일 DB, 쓰기 민감). uvicorn 기동은 `--host 127.0.0.1`, `SCHEDULER_ENABLED=false`.

## 10. 구현 단계화

- **Phase 1 — 백엔드 데이터층**: ORM 2종 + persona 확장 + 마이그레이션 + repo/service + 4 API. 엔드포인트 테스트.
- **Phase 2 — 임베딩 통합**: `_user_text()` 확장 + embed_repository JOIN + 재임베딩 보장 + Chance 가산. 직렬화/재임베딩 테스트.
- **Phase 3 — 프론트**: 프로필 선택 섹션 + 완성도 미터 + API 배선 + 키워드 풀 재설계 + **OAuth 후 `/onboarding` 선택 화면**(프로필 컴포넌트 재사용·건너뛰기). 신규 사용자 라우팅은 OAuth 콜백에서 분기.

각 단계 독립 검증·커밋. 작업 기록은 도메인별 `audit_trail.md`(auth·user_intelligence·market_insight)에 분산 기록.

## 11. 범위 밖

- **대화 추출 파이프라인**(ai_coach LLM 속성 추출→병합·확인 UX) — 추출-레디 설계만, 구현은 후속 스펙.
- 필드 단위 provenance·confidence 추적.
- 데모그래픽 기반 필터링/세그먼트 기능(데이터만 적재, 활용은 후속).
- Sync/Chance 점수 공식 자체 개편(임베딩 텍스트 풍부화로 간접 개선만).
