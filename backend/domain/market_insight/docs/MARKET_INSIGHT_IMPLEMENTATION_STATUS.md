# market_insight 도메인 — 구현 현황 & 추후 구현 (핸드오프)

> 최종 업데이트 2026-06-25. 새 세션 인계용. 이 도메인의 Silver/Gold 수직 6개 + 임베딩 인프라 + 프론트 연동 현황과 남은 일을 정리한다. 관련: [SILVER_PULSE_STRATEGY.md](./SILVER_PULSE_STRATEGY.md), [SILVER_TEXT_SECTOR_CLASSIFICATION.md](./SILVER_TEXT_SECTOR_CLASSIFICATION.md).

## 0. 한눈에

`market_insight`는 Bronze(`master` 도메인 수집분)를 **Silver 정제 → Gold 서빙**하는 인사이트 엔진이다. 이번 세션에 ERD가 설계만 해둔 나머지 Silver 계층을 전부 구현해, **6개 정제 수직 + pgvector 임베딩 인프라**가 가동되고 프론트 대시보드 4탭이 실데이터로 연결됐다.

- 마이그레이션 head: **`f8c2e6a0d3b7`**
- 일일 잡 체인(`core/scheduler.py` `_DAILY_JOBS`): `… → text_classify → entity_extract → gap_refine → chance_refine → chance_match → document_embed → user_embed → pulse_refine → sync_refine`
- 공용 LLM 클라이언트: `core/llm/client.py` (classify_sector·extract_signal·extract_gap·extract_chance·embed, openai lazy import, 각 파서 순수함수)
- 무네트워크 테스트: `backend/scripts/*_test.py` (총 128 PASS)

## 1. 수직별 구현 현황

| 수직 | 서비스 | Silver | Gold | API | 잡 | 상태 |
|---|---|---|---|---|---|---|
| **Pulse** | `pulse_refine_service`·`pulse_pipeline` | `refined_pulse_metric_silver` | `pulse_metrics_log` | `GET /api/insight/pulse`·`POST /pulse/refine` | `pulse_refine` | ✅ 6축 통약·융합·모멘텀 |
| **텍스트 섹터 분류** | `text_sector_classify_service` | `refined_text_sector_class` | (Pulse 축으로 합류) | — | `text_classify` | ✅ economic_text·discourse 축 |
| **엔티티·키워드 추출** | `text_entity_extract_service` | `refined_innovation_signal`+`refined_signal_sources` | — | — | `entity_extract` | 🟡 적재만, 아직 미소비 |
| **Gap** | `gap_refine_service` | `refined_gap_insights` | `gap_issues`·`issue_evidences` | `GET /api/insight/gap`·`/gap/{id}`·`POST /gap/refine` | `gap_refine` | ✅ 리스트+상세 |
| **Chance** | `chance_refine_service`·`chance_match_service` | `refined_chance_insights` | `chance_opportunities`·`user_chance_matches` | `/api/chance/{opportunities,opportunities/{id},matches,refine,match}` | `chance_refine`·`chance_match` | ✅ 추출+키워드매칭 |
| **임베딩** | `embed_service`(Document/User) | `document_embeddings`·`user_embeddings`(halfvec 3072) | — | — | `document_embed`·`user_embed` | ✅ pgvector 0.8 + HNSW |
| **Sync** | `sync_refine_service` | `refined_sync_inputs` | `sync_scores_daily` | `GET /api/sync/scores`·`POST /sync/refine` | `sync_refine` | ✅ 코사인 적합도×트렌드 |

## 2. 데이터 흐름 (Medallion + 잡 체인)

```
Bronze(master 수집) raw_* 
  → text_classify   : raw_economic/discourse 자유텍스트 → 섹터 분류(refined_text_sector_class)
  → entity_extract  : 분류된 텍스트 → 신호 토픽·키워드(refined_innovation_signal + N:M 리니지)
  → gap_refine      : discourse → 문제·기회(refined_gap_insights) → gap_issues·issue_evidences
  → chance_refine   : opportunity → 유형·자격(refined_chance_insights) → chance_opportunities
  → chance_match    : 사용자 프로필 × 공고 키워드·섹터 → user_chance_matches
  → document_embed  : gap/chance/신호 텍스트 → document_embeddings(halfvec)
  → user_embed      : 사용자 프로필 → user_embeddings
  → pulse_refine    : 6축(혁신·경제·사람·시장+economic_text·discourse) 통약·융합·모멘텀 → refined_pulse_metric_silver → pulse_metrics_log
  → sync_refine     : 사용자 임베딩 × 섹터 센트로이드 코사인 + Pulse 트렌드 → refined_sync_inputs → sync_scores_daily
```

각 잡은 `_run_job` try/except 격리 + 독립 `AsyncSessionLocal()` + `openai_api_key` 없으면 skip. 전부 멱등(Silver 자연키 ON CONFLICT, Gold upsert/사영).

## 3. 마이그레이션 체인 (이번 세션 추가분)

`a1b2c3d4e5f6`(직전 Pulse) → `b2d4f6a8c0e1`(refined_text_sector_class) → `c3e7f1a9b5d2`(refined_innovation_signal 보강) → `d4f8a2c6e0b3`(Gap) → `e5a9c3f7b1d4`(Chance) → `f6b1d4e8a2c5`(pgvector+임베딩) → **`f8c2e6a0d3b7`(Sync, head)**

## 4. 프론트 연동 현황 (`www.yeotaeho.kr`)

- 대시보드 4탭(Pulse·Gap·Sync·Chance) **백엔드 실데이터 전용** — `lib/api/dashboard.ts` + `hooks/useDashboard.ts`(TanStack Query). mock 폴백 제거, 실데이터 없으면 `PanelStatus` 에러.
- Gap·Chance **상세 페이지**도 `/api/insight/gap/{id}`·`/api/chance/opportunities/{id}` 연동(클라이언트 컴포넌트+훅).
- Pulse 탭은 라이브 섹터 카드만 유지(일러스트 mock viz 전부 제거).
- 커밋: `ca2051c`(연동)·`f472e5c`(mock 폴백 제거)·`8138a2a`(상세+viz 제거).

## 5. 추후 구현 (우선순위 순)

### A. Pulse 부가 서빙 (싼 것부터)
- **모멘텀 시계열·결정론 부가 서빙** ✅ — 구현·머지됨(커밋 `bbfb651`~`6d88ba3`, main). `GET /api/insight/pulse/overview`(속도계/주간지수·연간 모멘텀 시계열·섹터×시간 히트맵·관심 점유율)와 `GET /api/insight/pulse/{sector}/history` 추가, 프론트 `PulseTab`에 4개 섹션 라이브 복원. 순수함수 `domain/market_insight/hub/services/pulse_overview.py` + `PulseRepository.fetch_overview`/`fetch_history` + `scripts/pulse_overview_test.py`(20 checks). 히트맵 2번째 축은 **섹터×시간**으로 구현(섹터×축 히트맵은 별도 미구현으로 남김). 설계/계획: [pulse-deterministic-serving-design](../../../../docs/superpowers/specs/2026-06-25-pulse-deterministic-serving-design.md), [pulse-deterministic-serving plan](../../../../docs/superpowers/plans/2026-06-25-pulse-deterministic-serving.md).
- **부가 Gold 수직** 🟡 — 여전히 미구현, 다음 우선순위. `trending_keywords`(키워드 티커/클라우드 — `refined_innovation_signal.extracted_keywords` 활용), `economic_briefings`(3줄 브리핑, LLM), `causal_chains`(인과사슬, LLM), `crossover_metrics`(크로스오버 — "기존 vs 신흥" 데이터 정의 선결 필요). 프론트에서 제거된 mock 섹션들이 여기 대응.

### B. 엔티티 신호 활용
- `refined_innovation_signal`은 적재되나 **아무도 소비하지 않음**. Pulse 축 보강(토픽 가중) 또는 별도 "급상승 토픽" 서빙으로 연결 가능. `refined_signal_sources` N:M 리니지 활용처도 미정.

### C. 품질 튜닝 (코드 아닌 데이터/운영)
- **LLM 백필 미실행** — 모든 LLM 잡은 소량(8~60건)만 실호출로 검증. 전체 백필은 토큰 비용 → `run_job_now(...)` 수동 또는 일일 누적.
- **Pulse 모멘텀 백필 쏠림** — 카운트축 일별 시계열 미성숙으로 일부 섹터 과대 모멘텀. `min_history`·가산평활(`MOMENTUM_SMOOTHING`)로 1차 완화됨([silver-pulse-status] 메모리). 일별 누적으로 자연 분산 예정.
- **얇은 사용자 데이터** — Sync·Chance매칭은 `user_sync_profiles`(target_job·interest_keywords)만 사용. 실사용자 적어 품질은 데이터 확보 후 튜닝.

### D. 도메인 외 (별도 작업)
- **Roadmap·Coach** 탭은 `domain/hrowth_journey`·`domain/ai_coach`(스텁)에 의존 — 먼저 그 도메인 구현 필요. 프론트는 여전히 mock.

## 6. 함정 / 주의

- **asyncpg nullable 파라미터** — `:p IS NULL` 직접 사용 시 `AmbiguousParameterError`. `CAST(:p AS TEXT) IS NULL`로 캐스팅(서빙 쿼리 전반 적용됨).
- **JSONB 바인딩** — raw SQL `text()`에 리스트 직접 못 넣음. `json.dumps` 후 `CAST(:x AS JSONB)`.
- **halfvec 바인딩** — 임베딩 리스트는 `embed_repository.vec_literal`로 `'[..]'` 직렬화 후 `CAST(:e AS halfvec)`.
- **Chance Gold 안정 id** — `chance_opportunities`는 `UNIQUE(raw_table_ref, raw_id)` upsert(전체 재생성 아님). `user_chance_matches` FK 무결성 보존 위함. (Gap `gap_issues`는 전체 재생성이라 id 매일 바뀜 — 상세는 당일 유효.)
- **Pulse Gold 시계열** — `pulse_metrics_log`는 최신만이 아니라 전 날짜 보유(위 5-A).
- **prompt_version** — 각 LLM Silver 자연키에 포함. 프롬프트·파서 변경 시 bump해야 재처리됨.

## 7. 검증 방법

- 단위(무네트워크): `cd backend && python scripts/{pulse_scoring,pulse_text_axis,pulse_axis_normalize,llm_sector_classify,llm_entity_extract,llm_gap_extract,chance_extract_match,embed_helpers,sync_score}_test.py` → 전부 `FAIL=0`.
- 마이그레이션: `alembic upgrade head` (head `f8c2e6a0d3b7`).
- 실 잡(소량, LLM 토큰): `run_job_now("text_classify")` → `entity_extract` → `gap_refine` → `chance_refine`/`chance_match` → `document_embed`/`user_embed` → `pulse_refine` → `sync_refine`.
- 풀 렌더: 백엔드 `uvicorn main:app` + 프론트 `pnpm --dir www.yeotaeho.kr dev`(:3000). CORS는 localhost:3000 허용.
