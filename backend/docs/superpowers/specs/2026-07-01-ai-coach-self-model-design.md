# AI 상담실 = 개인화 본가 · 자기모델 설계 (SP-1 데이터층 중심)

> **목적** — AI 상담실이 사용자의 성격·가치관·호불호·제약(민감정보 포함)을 파악해 "자신도 모르는 부분"까지 드러내고, 그 자기모델이 진로 추천(Sync·Chance)과 코치 대화를 관통하게 만든다. 이 문서는 그 전체 비전의 분해와 **첫 서브프로젝트 SP-1(자기모델 데이터층)** 의 상세 설계다.
> **작성일** — 2026-07-01. 관련: [개인화 엔진 개요](../../PERSONALIZATION_ENGINE.md) · 진단으로 파생된 SP-0(Chance 배선, 커밋 `b374f15`).

---

## 1. 배경 — 왜 지금

### 1.1 진단 결과 (사용자 질문 "개인화가 안 보인다")
- **Sync(싱크로율)** — 개인화가 배선은 되어 있음. `/api/sync/scores`가 JWT로 사용자별 임베딩↔섹터 코사인을 서빙한다. 다만 최종 점수 = **코사인 적합도 60% + 전체 공통 트렌드(Pulse) 40%** 라, 사용자가 채운 데이터가 적으면 60% 신호가 얇아 "남들과 비슷하게" 보인다. → **차별화 신호가 얇다**가 정확한 진단.
- **Chance(다이렉트 찬스)** — 프론트가 인증 없는 제네릭 `/api/chance/opportunities`(전 사용자 동일)만 호출해, 매시간 배치로 계산·저장되던 사용자별 매칭(`user_chance_matches`)이 화면에 전혀 노출되지 않았음. **SP-0(커밋 `b374f15`)에서 `/matches` 연결 + 폴백으로 해소.**

두 진단의 공통 뿌리 — **사용자에 대해 아는 신호가 얇다**(현재 target_job + interest_keywords + 성향/스펙 일부). AI 상담실이 대화로 이 신호를 깊게 만드는 "본가"가 되면 Sync·Chance·Coach 전부가 두꺼워진다.

### 1.2 현재 AI 상담실의 한계
`coach_service.stream_sse`는 **맥락 주입만** 한다 — persona/roadmap/트렌드를 시스템 프롬프트에 넣어 답만 스트리밍하고, 성격·가치관·호불호·트라우마를 **사용자 테이블로 되돌려 쓰는 로직이 전혀 없다**. "자신도 모르는 부분을 찾아내는" 본가 기능은 사실상 미구현(추출-레디 설계만 존재).

---

## 2. 확정된 골격 결정 (브레인스토밍)

| 결정 | 선택 | 함의 |
|---|---|---|
| **자기모델 골격** | **하이브리드** — 구조 척추(심리 축) + 서사(대화 근거) | 구조 축은 추천·설명에, 서사는 코치 공감·심화에. 기존 임베딩 직렬화 방식 그대로 확장 |
| **추출 방식** | **세션 후 비동기 추출기** | 채팅 무지연 · confidence 게이팅 · 감사·롤백 용이 · `source='coach_extraction'` 재사용 |
| **추천 반영** | **임베딩 + 설명 레이어** | recall↑(임베딩) & "왜 이 추천"(설명) 둘 다 — 사용자 진단 "안 보인다"를 직접 겨냥 |
| **가치관·민감정보** | **분리 유지 + 민감정보 플래그** | 가치관은 기존 `user_preferences` 유지(중복 제거), 트라우마·제약은 evidence 격리(추천·코치 노출 기본 제외) |

---

## 3. 전체 로드맵 (5 서브프로젝트 · 각자 spec→plan→구현)

| SP | 이름 | 내용 | 상태 |
|---|---|---|---|
| **SP-0** | Chance 가시화 | 프론트를 `/matches`로 전환 + 폴백 | ✅ 완료(`b374f15`) |
| **SP-1** | **자기모델 데이터층** | 신규 2테이블 + 병합 규칙 + 마이그레이션 + 리포지토리/서비스/읽기 API + 테스트 | **본 문서** |
| **SP-2** | 대화 추출 엔진 | 세션 종료 → LLM 추출 패스(스키마 강제) → confidence 게이팅 → `source='coach_extraction'` upsert · 빈 축 능동 탐침 | 후속 |
| **SP-3** | 추천 반영 + 설명 레이어 | 자기모델을 임베딩 직렬화(민감정보 제외) + Sync/Chance 추천 근거·제외 사유 노출 | 후속 |
| **SP-4** | 상담실 UX = 본가 | 코치 탭을 성격/진로 발견 중심으로 재구성 · 자기모델 진행도 · "숨은 통찰" surfacing | 후속 |

**SP-1은 나머지 전부의 토대** — 스키마와 병합 규칙이 확정돼야 추출(SP-2)·추천(SP-3)이 그 위에 얹힌다.

---

## 4. SP-1 데이터 모델 (상세)

전부 nullable·선택. 두 테이블은 하이브리드의 두 축이다.

### 4.1 `user_self_model` — 구조 척추 (1행/사용자)

| 컬럼 | 타입 | 설명 |
|---|---|---|
| `user_id` | UUID PK, FK `users.id` CASCADE | 소유자 |
| `riasec` | JSONB nullable | `{"scores": {"R":0-100, "I":.., "A":.., "S":.., "E":.., "C":..}, "top_codes": ["I","A","S"]}` — Holland 직업흥미 6코드 |
| `big_five` | JSONB nullable | `{"openness":0-100, "conscientiousness":.., "extraversion":.., "agreeableness":.., "neuroticism":..}` (선택) |
| `narrative_summary` | TEXT nullable | 코치가 종합한 한 줄 자기서사 |
| `axis_confidence` | JSONB nullable | 축별 신뢰도 `{"riasec":0.0-1.0, "big_five":..}` — 얼마나 파악됐나(완성도 미터·게이팅) |
| `source` | VARCHAR(30) NOT NULL, default `coach_extraction` | `user_form` / `coach_extraction` |
| `updated_at` | timestamptz, default now() | 재임베딩 트리거(기존 `GREATEST(...) > computed_at` 패턴에 편입) |

> **RIASEC를 JSONB로** — 6컬럼 대신 JSONB. 확장(하위 관심·코드별 근거 링크)에 유연하고, 임베딩 직렬화 시 `top_codes`만 라벨로 뽑으면 되므로 충분.

### 4.2 `user_self_model_evidence` — 서사·근거 (N행/사용자 · append-only)

| 컬럼 | 타입 | 설명 |
|---|---|---|
| `id` | BIGSERIAL PK | |
| `user_id` | UUID FK `users.id` CASCADE, indexed | |
| `dimension` | VARCHAR(30) NOT NULL | `riasec_R`..`riasec_C` / `value` / `like` / `dislike` / `constraint` / `sensitive` / `aspiration` / `skill_signal` / `other` |
| `polarity` | VARCHAR(10) nullable | `like` / `dislike` / `neutral` (호불호) |
| `content` | TEXT NOT NULL | 추출 근거 문장 ("사람들 앞 발표에서 에너지를 얻는다") |
| `confidence` | NUMERIC(3,2) nullable | 0.00~1.00 (게이팅) |
| `is_sensitive` | BOOLEAN NOT NULL, default false | 트라우마·제약 등 — 추천 직렬화·코치 프롬프트에서 **기본 제외** |
| `content_hash` | VARCHAR(64) nullable | 세션 간 중복 근거 dedup 키(정규화 content 해시) |
| `coach_session_ref` | VARCHAR(64) nullable | 대화 출처 링크(감사·설명). 현재 coach 세션 테이블 부재 → 우선 자유 문자열 |
| `source` | VARCHAR(30) NOT NULL, default `coach_extraction` | |
| `created_at` | timestamptz, default now() | |

**인덱스** — `(user_id, dimension)`, `(user_id, is_sensitive)`, unique `(user_id, content_hash)`(dedup, content_hash NOT NULL 행에 한함 — partial unique).

---

## 5. 병합 규칙 (SelfModelService — SP-2/폼이 재사용)

**추출-레디 인터페이스**: `upsert_structured(user_id, payload, source, confidence)` + `append_evidence(user_id, items, source)` + `get_self_model(user_id, include_sensitive=False)`.

### 5.1 구조 축 (`user_self_model`)
- **user_form 우위** — 축(riasec/big_five/narrative)이 이미 `source='user_form'`으로 채워졌으면 `coach_extraction`은 **덮어쓰지 않는다**.
- **빈 축만 채움** — 축이 NULL/빈값일 때만 coach 값 기록.
- **confidence 게이팅** — 들어온 `confidence < THRESHOLD`(기본 0.40)면 축 점수는 보류하고 `axis_confidence`에만 반영(부분 정보로 완성도 미터는 올라가되 추천엔 미투입).
- 같은 축을 user_form이 나중에 채우면 coach 값을 대체(사용자 명시 입력 최우선).

### 5.2 근거 (`user_self_model_evidence`)
- **append-only** — 덮어쓰기 없음. 대화가 쌓일수록 근거 누적.
- **dedup** — `content_hash`(정규화 후 해시) 동일 시 무시(같은 말 반복 세션 방지).
- **민감 격리** — `is_sensitive=true` 근거는 저장하되, `get_self_model(include_sensitive=False)` 기본 응답·임베딩 직렬화·코치 프롬프트에서 제외. 노출은 명시적 옵트인 경로에서만.

---

## 6. 임베딩·추천 연동 (SP-3에서 구현 · 여기선 계약만)
- `build_user_embed_text()`(기존 순수 헬퍼)에 자기모델 직렬화 추가: RIASEC `top_codes`→한국어 라벨(예: "탐구형·예술형"), big_five 두드러진 축→라벨, **비민감** like/value 근거 상위 N개→텍스트. `is_sensitive=true`·`dislike` 처리 정책은 SP-3에서 확정(dislike는 제외 필터 후보).
- 재임베딩 트리거는 기존 `GREATEST(updated_at들) > computed_at` 에 `user_self_model.updated_at` 편입(SP-3).

---

## 7. SP-1 범위 (명확히)

**포함**
- ORM 2종(`user_self_model`, `user_self_model_evidence`) — `domain/user_intelligence/models/bases/`.
- Alembic 마이그레이션 1건(생성 파일 검토 필수, 수동 DDL 금지). **Neon 적용은 사용자 승인 후.**
- `SelfModelRepository`(병합-aware upsert + fetch) · `SelfModelService`(§5 규칙 + `get_self_model`).
- 읽기 API `GET /api/user/self-model`(인증, 기본 비민감) — 완성도·코치·프로필이 읽음.
- 테스트(Neon 라운드트립): 모델 import·병합 규칙·엔드포인트.

**제외(후속 SP)**
- 대화 추출 로직(SP-2) · 임베딩 직렬화·Sync/Chance 설명(SP-3) · 코치 UX(SP-4).
- 구조 축 폼 직접 입력 UI(필요 시 SP-4 프로필 확장). SP-1은 저장·병합·읽기 경로만.

---

## 8. 성공 기준
1. 마이그레이션이 Neon에 적용되고 두 테이블·인덱스·FK가 존재.
2. `SelfModelService`가 §5 병합 규칙을 정확히 지킴 — user_form 우위, confidence 게이팅, evidence append+dedup, 민감 격리.
3. `GET /api/user/self-model`이 인증 사용자의 구조 축 + 비민감 근거 요약을 반환하고, 무토큰은 401, 민감 근거는 기본 응답에서 제외.
4. 전 테스트 green(Neon 실DB).

## 9. 테스트 전략
- `scripts/self_model_models_import_test.py` — ORM import + 테이블 리플렉트 + nullable/기본값.
- `scripts/self_model_merge_test.py` — user_form 우위·confidence 게이트·evidence dedup·is_sensitive 격리(순수+Neon).
- `scripts/self_model_endpoint_test.py` — GET 라운드트립·무토큰 401·민감 제외.

## 10. 가정·미해결
- **RIASEC/big_five 점수 산출은 SP-2 추출기 책임** — SP-1은 저장·병합만. 점수 스케일(0~100)·top_codes 규칙은 SP-2 프롬프트 스펙에서 확정.
- **coach_session_ref** — 현재 coach는 세션 테이블 없이 스트림만. 우선 자유 문자열(nullable)로 두고, SP-2에서 coach 세션 영속화 시 정식 FK로 승격.
- **민감정보 처리 수위** — 본 스펙은 저장+플래그+기본 제외까지. 암호화·별도 접근감사·사용자 삭제권(“이 이야기 잊어줘”)은 후속 정책으로 분리(윤리·프라이버시 검토 필요).
- **완성도 미터 연동** — `axis_confidence`를 기존 CompletionMeter에 태울지는 SP-4에서.
