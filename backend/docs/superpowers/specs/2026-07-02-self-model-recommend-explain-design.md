# SP-3 — 자기모델 추천 반영 + LLM 설명 레이어 설계

2026-07-02 확정. SP-1(자기모델 데이터층)·SP-2b(대화→자기모델 추출)의 후속으로,
축적된 자기모델이 실제 Sync/Chance 추천을 바꾸고 사용자에게 "왜 이 추천인지"를 보여준다.

## 배경

- 사용자 임베딩 텍스트(`build_user_embed_text`)는 프로필(직무·관심·성향·스펙)만 직렬화 — 자기모델 미반영.
- 재임베딩 후보(`_FETCH_UNEMBEDDED_USERS`)는 `user_sync_profiles` 행 보유자만 잡고, 타임스탬프도
  프로필 3테이블만 봐서 자기모델 갱신이 재임베딩을 트리거하지 못한다. 프로필 미작성·코치 대화만
  있는 사용자는 임베딩·추천 대상에서 아예 빠진다.
- Chance `match_reason`은 계산→저장→API→프론트 모델까지 배선돼 있으나 UI 미렌더·기술적 문구.
  Sync는 score+badge뿐 사유 필드가 없다(단 `refined_sync_inputs`에 적합도·트렌드·키워드 분해값 보존).

## 확정 결정 (사용자 확답)

| 결정 | 선택 |
|---|---|
| 임베딩 재료 | 구조축(RIASEC 라벨) + 서사 + 비민감·긍정 근거 상위 N. dislike/constraint/민감 제외 |
| 코치-only 사용자 | 포함 — `users` 기준 후보 재구성, 프로필 없어도 자기모델 있으면 임베딩·추천 |
| 설명 문구 | LLM 생성 문장(결정론 사실 주입으로 환각 봉쇄, top-N만, 나머지 결정론 폴백) |
| dislike 활용 | 경량 주의 표시 — 감점 없이 LLM 설명 문장 안에 주의 문구 포함 |
| 생성 시점 | 일일 배치 — `_REFINE_PIPELINE` 끝(sync_refine 뒤)에 추가 |

## A. 임베딩 직렬화 확장

### A-1. `build_user_embed_text` (순수 유지)

`domain/market_insight/hub/services/user_embed_text.py`에 kwargs 3개 추가.

- `riasec: dict | None` — `{"top_codes": ["R", ...]}` 형태(SP-2b 저장 형태). 라벨 매핑
  `R 현실형 · I 탐구형 · A 예술형 · S 사회형 · E 진취형 · C 관습형`, 닫힌집합 외 코드는 무시.
- `narrative_summary: str | None` — 그대로 이어붙임.
- `evidence_contents: list[str] | None` — 근거 문장 리스트.
- 이어붙임 순서: 기존 프로필 파츠 → RIASEC 라벨 → narrative → 근거.
- **전체 텍스트 1000자 캡을 빌더 내부에서 적용**(`MAX_EMBED_TEXT_CHARS = 1000`) — 다운스트림
  해시(source_version)가 캡 후 텍스트 기준이 되어, 캡으로 잘린 불변 텍스트가 재임베딩되지 않는다.

### A-2. 재임베딩 후보 재구성 (`embed_repository.py`)

`_FETCH_UNEMBEDDED_USERS`를 `users u` 기준 LEFT JOIN으로 전환.

- 조인: `user_sync_profiles p` · `user_preferences pref` · `user_personas per` ·
  `user_self_model sm` · (비민감 근거 `max(created_at)` 집계 서브쿼리 `ev`) · `user_embeddings e`.
- 후보 조건: `p·sm·ev 중 하나라도 존재` AND (`e` 미존재 OR
  `GREATEST(p/pref/per/sm.updated_at, ev.last_evidence_at 각 COALESCE) > e.computed_at`).
- SELECT에 `sm.riasec, sm.narrative_summary` 추가.

### A-3. 근거 선택 규칙 (긍정·비민감만)

pending 사용자 대상 2차 쿼리(`user_id = ANY(:uids)` + `ROW_NUMBER() PARTITION BY user_id`).

- `is_sensitive = false`
- `dimension IN ('like', 'value', 'aspiration', 'skill_signal')`
- `polarity IS NULL OR polarity <> 'dislike'`
- 정렬 `confidence DESC NULLS LAST, created_at DESC`, 사용자당 상위 10개.

dislike/constraint는 임베딩에 넣으면 부정 대상 문서를 의미적으로 끌어당기는 역효과 — 제외.
민감 근거는 파생 산출물(임베딩) 전체에서 배제(프라이버시 by design).

### A-4. Chance 매칭 사용자 확장 (`chance_repository.py`)

`_FETCH_USERS`도 `users u` 기준 LEFT JOIN + 동일 존재 조건으로 전환. 코치-only 사용자는
user_terms가 비어도 임베딩 보유 시 semantic 경로로 매칭된다(폴백 불필요).
Sync는 `user_embeddings` 기반이라 임베딩만 생기면 기존 경로로 자동 포함
(`fetch_user_keywords`의 프로필 부재 사용자는 기존 `.get(user_id, [])` 빈 리스트 처리 그대로).

## B. 스키마 변경 (마이그레이션 1건 · Neon 승인 후 적용)

- `sync_scores_daily.explanation TEXT NULL`
- `user_chance_matches.match_explanation TEXT NULL`
- ORM 베이스 2개 수정 후 `alembic revision --autogenerate` — 무관 drift(sectors 등) 제거 관행 준수.
- `backend/docs/erd.md` SSOT 반영.

기존 `match_reason`(결정론)은 감사·폴백용으로 유지 — LLM 문장으로 덮어쓰지 않는다.

### 설명 무효화 (CASE 보존)

재점수 upsert 시 입력이 안 바뀌면 설명 보존, 바뀌면 NULL로 무효화.

- `_UPSERT_MATCH`: `match_explanation = CASE WHEN 기존 score·reason이 EXCLUDED와
  IS NOT DISTINCT FROM 이면 기존 값 ELSE NULL END`
- `_UPSERT_SYNC_GOLD`: 동일 패턴(score·badge 기준).

시간별 refresh(user_embed→chance_match→sync_refine)가 점수를 바꾸면 설명이 NULL로 돌아가고
다음날 일일 배치가 재생성 — 그 사이 프론트는 결정론 폴백(match_reason / 미표시)을 쓴다.

## C. LLM 설명 배치

### C-1. `LlmClient.explain_recommendations` + 순수 파서

- 입력: 사용자 컨텍스트(직무·관심키워드·RIASEC 라벨·narrative·긍정 근거 top 5·**비민감 dislike 근거 top 3**)
  + Sync 항목(섹터명·score·badge·적합도/트렌드 분해값) + Chance 항목(공고 제목·유형·score·match_reason).
- 시스템 프롬프트: 진로 코치 톤 존댓말 1~2문장, 주어진 사실만 사용(환각 금지), dislike 근거와
  충돌하는 항목은 문장 안에 주의 문구 포함, JSON only.
- 출력: `{"sync": [{"sector_slug", "text"}], "chance": [{"opportunity_id", "text"}]}`.
- `_parse_recommend_explain(raw, valid_slugs, valid_opp_ids)` — 닫힌 키 검증, 모르는
  slug/id 무시, text 200자 클램프, 실패 시 빈 리스트(쓰기 없음 → 다음날 재시도). SP-2b 파서 관행.
- **민감 근거(is_sensitive=true)는 어떤 경우에도 프롬프트에 넣지 않는다.**

### C-2. `RecommendExplainService` (market_insight)

`hub/services/recommend_explain_service.py` + `hub/repositories/recommend_explain_repository.py`(신규).

- 상수: `TOP_SYNC = 3`, `TOP_CHANCE = 10`, `EVIDENCE_POS = 5`, `EVIDENCE_DISLIKE = 3`.
- 대상 산출: 오늘 `sync_scores_daily` 중 `explanation IS NULL` 상위 3개 섹터(점수순,
  `badge = '데이터 부족'` 행은 설명할 신호가 없으므로 제외) ∪ `user_chance_matches` 중
  `match_explanation IS NULL` 상위 10개 매치(점수순) — 사용자 단위로 묶어 **사용자당 LLM 1회 호출**.
- 사실 수집: `refined_sync_inputs`(당일 affinity/trend) · `user_chance_matches`+`chance_opportunities`
  (score·reason·제목) · `user_self_model`/`user_self_model_evidence`(비민감) · 프로필 — 리포 raw SQL.
- 쓰기: 반환된 항목만 `UPDATE ... SET explanation/match_explanation`. 미반환 항목은 NULL 유지(폴백 표시).
- per-user try/except 격리 + `processed/failed` 집계 반환, OpenAI 키 없으면 `{"skipped": true}`
  (SP-2b `extract_pending` 관행).

### C-3. 스케줄러

- `_job_recommend_explain` 추가, `_REFINE_PIPELINE` 맨 끝(`sync_refine` 뒤)에
  `("recommend_explain", _job_recommend_explain)` 등록. 시간별 refresh에는 미포함(비용).

## D. 서빙 API·프론트

- `_FETCH_SCORES`에 `d.explanation`, `_FETCH_MATCHES`에 `m.match_explanation` 추가 + dict 매핑.
- `www.yeotaeho.kr/src/lib/api/dashboard.ts` — `SyncScoreLive.explanation: string | null`,
  `ChanceMatchLive.match_explanation: string | null` + 매핑.
- `DashboardView.tsx` — Sync 행 아래 설명 서브텍스트(있을 때만), Chance 매치 카드에
  `match_explanation ?? match_reason` 서브텍스트.

## 테스트 계획

- 순수: RIASEC 라벨 매핑·근거 이어붙임·1000자 캡·캡 후 해시 안정성, `_parse_recommend_explain`
  (정상·모르는 id·비JSON·클램프).
- 리포: 후보 쿼리(코치-only 포함, 자기모델 갱신 → 후보 재진입), 근거 선택 필터(민감·dislike 제외),
  upsert CASE(불변 시 보존·변경 시 NULL).
- 서비스: FakeLLM으로 explain_pending 멱등(2회차 0건)·per-user 격리·민감 근거 미주입(프롬프트 검사).
- 잡 스모크 + 기존 백엔드 127 assertion 회귀 + `tsc --noEmit` 0 에러.

## 범위 밖 (후속)

- dislike 기반 감점·매칭 제외(스코어링 변경) — 주의 표시의 다음 단계.
- 시간별 설명 재생성(현재 일일만) · UI 주의 배지 분리(현재 문장 내 포함).
- SP-4 — AI 상담실 UX를 개인화 본가로 승격(자기모델 가시화·"나도 몰랐던 나" 카드).

## 파일 지도

| 영역 | 파일 |
|---|---|
| 직렬화 | `backend/domain/market_insight/hub/services/user_embed_text.py` |
| 임베딩 후보·적재 | `backend/domain/market_insight/hub/repositories/embed_repository.py` · `hub/services/embed_service.py` |
| 매칭 사용자 확장·CASE | `backend/domain/market_insight/hub/repositories/chance_repository.py` |
| Sync CASE·서빙 | `backend/domain/market_insight/hub/repositories/sync_repository.py` |
| LLM·파서 | `backend/core/llm/client.py` |
| 설명 배치 | `backend/domain/market_insight/hub/services/recommend_explain_service.py` · `hub/repositories/recommend_explain_repository.py` (신규) |
| 스케줄러 | `backend/core/scheduler.py` |
| ORM·마이그 | `backend/domain/market_insight/models/bases/sync_scores_daily.py` · `user_chance_matches.py` · `backend/alembic/versions/` |
| 프론트 | `www.yeotaeho.kr/src/lib/api/dashboard.ts` · `src/components/features/dashboard/DashboardView.tsx` |
