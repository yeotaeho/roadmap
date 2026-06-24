# Silver — 자유 텍스트 LLM 섹터 분류 (economic_text · discourse 축)

> 작성 2026-06-25. Pulse Silver 파이프라인에 LLM 섹터 분류 단계를 삽입한 작업의 설계·구현·후속 로드맵 기록.

## 1. 배경 — 왜

Pulse Silver는 `market_insight` 도메인에서 결정론적 통계 정규화로 가동 중이지만, **자유 텍스트가 원천인 두 축이 빠져 있었다**.

- `raw_discourse_data`(뉴스·보도자료)는 `fetch_axis_signals()`에 아예 들어가지 않았다.
- `raw_economic_data`도 `raw_metadata`에 코드 필드(`industry_sector`/`group_name`)가 있는 행만 잡혔다. Wowtale·Platum·MSIT 보도자료 같은 VC/정책 뉴스는 섹터가 제목·본문 텍스트에만 녹아 있어 **섹터 무귀속으로 버려졌다**.

**원칙** — 수치 정제는 결정론 그대로 두고, LLM은 *비정형 텍스트를 `sector_slug`로 번역하는 역할만* 한다. LLM 출력은 점수가 아니라 분류 결과(섹터 + confidence)로 떨어뜨려 기존 결정론 융합에 합류시킨다. 비용·재현성을 지키기 위해 분류 결과를 `raw_id` 기준으로 영속 캐싱하고 멱등 잡으로 점진 처리한다.

## 2. 데이터 흐름

```
raw_economic_data / raw_discourse_data  (자유 텍스트, 최근 90일 · 미분류)
        │
        ▼
[_job_text_classify] TextSectorClassifyService ── LlmClient(gpt-4o-mini) ──▶ {sector_slug|null, confidence}
        │  on-conflict-skip upsert (멱등, 자연키 = raw_table_ref·raw_id·prompt_version)
        ▼
refined_text_sector_class
        │  confidence ≥ min, sector_slug NOT NULL, COUNT(DISTINCT raw_id) per (sector, date)
        ▼
[_job_pulse_refine] fetch_axis_signals() ── economic_text·discourse 축 합류 ──▶ fuse_signals ──▶ Silver ──▶ Gold
```

분류 잡(`text_classify`)이 정제 잡(`pulse_refine`) **앞**에 실행되고, `_run_job` try/except로 격리되어 LLM 실패가 결정론 Pulse를 막지 않는다.

## 3. 구현한 것 (2026-06-25)

| 컴포넌트 | 위치 | 역할 |
|---|---|---|
| `LlmClient` + `_parse_classification` | `core/llm/client.py` | AsyncOpenAI 얇은 래퍼. `classify_sector(text, sector_list) → {sector_slug|null, confidence}`. openai 는 사용 시점 lazy import. 파서는 무네트워크 순수 함수. ai_coach 재사용 가능 |
| settings 키 3개 | `core/config/settings.py` | `openai_api_key`, `llm_classify_model`(기본 gpt-4o-mini), `llm_classify_confidence_min`(기본 0.6) |
| `refined_text_sector_class` ORM·마이그레이션 | `models/bases/refined_text_sector_class.py`, `alembic/.../b2d4f6a8c0e1_*.py` | Silver 분류 결과. 자연키 `UNIQUE(raw_table_ref, raw_id, prompt_version)`. `sector_slug` nullable(무귀속 허용) |
| `TextSectorClassifyService` | `hub/services/text_sector_classify_service.py` | 미분류 행 조회 → LLM 분류 → 멱등 upsert. `PROMPT_VERSION="v1"`, `ACTIVE_WINDOW_DAYS=90`, `SECTOR_SLUGS`(12개) |
| repo SQL | `hub/repositories/pulse_repository.py` | 미분류 조회, upsert, `_TEXT_SECTOR_AXIS_SQL`(economic_text·discourse 집계), `fetch_axis_signals` 통합 |
| 융합 가중치 | `hub/services/pulse_pipeline.py` | `DEFAULT_AXIS_WEIGHTS` 에 `economic_text=1.0`, `discourse=0.5` |
| 스케줄러 잡 | `core/scheduler.py` | `_job_text_classify`(키 없으면 skip), `_DAILY_JOBS` 에서 `pulse_refine` 앞에 등록 |
| 테스트 | `scripts/llm_sector_classify_test.py`, `scripts/pulse_text_axis_test.py` | 파서 검증(14), 가중치·통약·융합 검증(8) |

### 이중 집계 차단 (핵심 설계)

기존 `_ECONOMIC_AXIS_SQL`은 `WHERE (raw_metadata ? 'industry_sector' OR raw_metadata ? 'group_name')` 로 코드 필드가 있는 행만 집계한다. LLM 분류 대상을 그 **여집합**(`(... OR ...) IS NOT TRUE`)으로 한정해, `economic` 축과 `economic_text` 축이 행 단위 disjoint가 되어 중복 카운트가 구조적으로 불가능하다. `economic_text`는 기존 `economic`을 대체가 아니라 **보완**한다.

### 멱등·비용 제어

- **멱등** — 자연키 `ON CONFLICT DO NOTHING`. 이미 분류된 행은 재호출 안 함.
- **캐싱 키** — `input_hash`(분류 입력 sha256) + `prompt_version`. 프롬프트·파서가 바뀌면 `PROMPT_VERSION` bump으로 버전 격리.
- **윈도우 한정** — 최근 `ACTIVE_WINDOW_DAYS`(90일) 미분류 행만 대상.
- **confidence 게이트** — 축 집계 시 `confidence ≥ llm_classify_confidence_min`.
- **abstain** — LLM이 확신 없으면 `sector_slug=null`. 강제 매핑 금지(프로젝트 "섹터 강제 매핑 = 날조" 원칙).
- **입력 상한** — `MAX_INPUT_CHARS=2000`. 섹터 판별엔 제목+리드로 충분, 토큰 비용 절감.

### 검증 결과 (토큰 비용 0)

- 단위 테스트 — 신규 `14 + 8` PASS, 회귀(`pulse_axis_normalize` 16, `pulse_scoring` 25) 전부 PASS.
- 마이그레이션 — Neon 적용 완료(head `b2d4f6a8c0e1`), 단일 head·체인 정상.
- 실 스키마 SQL — 미분류 조회가 90일 내 economic·discourse 행을 정상 반환(jsonb `?`·`IS NOT TRUE` 여집합·캐스팅 동작), `fetch_axis_signals(text_prompt_version='v1')`이 기존 4축을 회귀 없이 반환하고 텍스트 축 UNION도 무에러 실행.
- **미실행** — 실 LLM 분류 잡(`refined_text_sector_class` 적재)은 토큰 비용이 발생해 보류. `OPENAI_API_KEY` 설정 시 `run_job_now("text_classify")` 또는 일일 스케줄러로 가동.

## 4. 운영

- 일일 스케줄러가 `text_classify` → `pulse_refine` 순으로 실행(09:00 KST 기본).
- 수동 트리거 — `run_job_now("text_classify")`, `run_job_now("pulse_refine")`.
- `OPENAI_API_KEY` 미설정 시 분류 잡은 경고 로그 후 skip(Pulse는 기존 분류분으로 진행).

## 5. 추후 Silver 구현 로드맵

이번 작업은 "분류만" 범위였다. 다음은 같은 패턴(축 집계 → 통약 → compute → 멱등 replace) 위에 얹을 후속 과제다.

### A. 실 분류 가동·품질 모니터링
- 실 LLM 백필(최근 90일)을 가동하고 분류 분포·confidence 분포·`unknown` 비율을 점검한다.
- confidence 임계(0.6)와 축 가중치(economic_text 1.0 / discourse 0.5)를 실측으로 튜닝한다.

### B. 엔티티·키워드 추출 단계 (분류 다음 수직)
- 투자 주체·대상·금액·핵심 기술 토픽을 LLM으로 추출한다.
- 이때 현재 **DDL만 있고 미사용**인 `refined_innovation_signal` + `refined_signal_sources`(N:M 리니지: `raw_table_ref`·`raw_id`·`contribution_weight`)가 제 용처를 찾는다. 분류 grain과 달리 "집계된 signal topic" grain이므로 추출 결과 적재에 적합하다.

### C. 다중 섹터 가중 매핑
- 한 뉴스가 여러 섹터에 기여하는 현실 반영. 행당 top-k 섹터 + `contribution_weight`로 확장한다(현재는 단일 최선 섹터).

### D. 다른 Silver 수직으로 패턴 재사용
- **Gap** — discourse 본문에서 미해결 문제(`gap_issues.problem_summary`)·기회(`chance_summary`)를 LLM 추출.
- **Sync** — 사용자 페르소나 × 섹터 신호로 `refined_sync_inputs` → `sync_scores_daily` 산출.

### E. 이상치 해석용 LLM (탐지 ≠ 해석)
- 이상 **탐지**는 결정론 통계(3σ·결측·중복)로, 이상 **해석**(급등이 실제 이벤트인지 데이터 오류인지)은 관련 discourse를 LLM이 읽어 판단. 무딘 `min_history`·`MOMENTUM_CAP` 게이트를 맥락 기반 판단으로 보강한다.

### F. 비용·성능
- 행 단위 순차 호출을 배치·동시성 cap으로 전환, 캐시 TTL/재분류 정책 정교화, 모델 선택(분류=mini, 추출=상위 티어) 분리.

## 6. 관련 파일

- 파이프라인 — `hub/services/pulse_pipeline.py`, `pulse_refine_service.py`, `text_sector_classify_service.py`
- 리포지토리 — `hub/repositories/pulse_repository.py`
- 모델 — `models/bases/refined_text_sector_class.py`, `refined_pulse_metric_silver.py`, `pulse_metrics_log.py`
- 공용 — `core/llm/client.py`, `core/config/settings.py`, `core/scheduler.py`
- 전략 — [SILVER_PULSE_STRATEGY.md](./SILVER_PULSE_STRATEGY.md)
