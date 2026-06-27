# KIAT 수요기술 → Gap 청년 기회 신호 (Phase 2)

- **작성일** 2026-06-27
- **상태** 설계 승인, 구현 대기
- **범위** Phase 2 — KIAT 수요기술을 Gap 기회 신호로 변환. Phase 1(Pulse `tech_demand` 축, `2026-06-27-kiat-pulse-tech-demand-design.md`)의 분류 결과 재사용.

---

## 1. 배경 / 문제

Phase 1 에서 KIAT(`INNOVATION_KIAT_TECH_DEMAND`)·KISTEP 을 LLM 섹터 분류해 `refined_text_sector_class`(`raw_table_ref='raw_innovation_data'`)에 적재하고 Pulse `tech_demand` 축으로 연결했다. 그러나 이 분류는 현재 Pulse 트렌드 점수에만 쓰이고, KIAT 가 담은 "기업이 필요로 하나 아직 확보 못 한 수요기술"이라는 의미는 활용되지 않는다.

KIAT 수요기술은 본질적으로 **시장의 미해결 갭**이다 — 기업이 원하는 기술 역량이 부족하다는 신호. 이를 "청년이 그 역량을 키우면 잡을 기회"로 변환하면 Gap 탭(시장 미해결 기회 시각화)의 신규 신호원이 된다.

## 2. 목표 / 비목표

**목표**
- KIAT(+KISTEP) 분류 결과를 입력으로 "기업 미확보 수요기술 → 청년 기회"를 LLM 추출해 `refined_gap_insights` Silver 에 적재한다.
- 청년 개인이 진입 불가한 항목(B2B 설비·자본집약 기술 등)을 `youth_fit` 점수 게이트로 Gold 에서 배제한다.
- 기존 discourse Gap 경로에 회귀를 만들지 않는다.

**비목표**
- KIAT 외 신규 innovation 소스 추출(ArXiv·GitHub 등은 생산 신호라 Gap 의미와 다름).
- youth_fit 임계 자동 최적화(수동 캘리브레이션으로 충분).
- Gap 탭 프론트엔드 UI 변경(소스 구분은 evidence_type 으로 데이터에 보존, UI 적용은 별도).

## 3. 설계

### 3.1 구현 구조 — 별도 서비스 + 공유 repo·모델

- 신규 `TechDemandGapService` 를 두어 KIAT 전용 추출·프롬프트를 격리한다. discourse 전용 `GapRefineService` 는 무수정.
- Silver(`refined_gap_insights`)·Gold(`gap_issues`·`issue_evidences`)·`GapRepository` 는 공유한다. 모델은 `raw_table_ref`·`data_role`·자연키(`raw_table_ref, raw_id, prompt_version`)로 이미 소스 중립이라 재사용 가능.
- *기각안* — `GapRefineService` 소스 파라미터화: 두 프롬프트·두 fetch 가 한 메서드에 섞여 discourse 회귀 위험 ↑.

### 3.2 입력 — Phase 1 분류 재사용 (소스 disjoint)

신규 `GapRepository.fetch_unprocessed_tech_demand` SQL:
- `refined_text_sector_class c` (`c.raw_table_ref='raw_innovation_data'`, `c.sector_slug IS NOT NULL`, `c.confidence >= :conf_min`)
- `JOIN raw_innovation_data i ON i.id = c.raw_id` — `i.source_type IN ('INNOVATION_KIAT_TECH_DEMAND','INNOVATION_KISTEP_REPORT')` (이중집계 방지·ArXiv 등 생산 신호 제외).
- `LEFT JOIN refined_gap_insights g ON g.raw_table_ref='raw_innovation_data' AND g.raw_id=c.raw_id AND g.prompt_version=:pv` → `g.id IS NULL`(미처리).
- 추출 입력 텍스트: `title + E'\n' + COALESCE(abstract_text,'') + E'\n' + COALESCE(raw_metadata->>'keyword','')`.
- window 필터: `COALESCE(i.published_at::date, i.collected_at::date) >= CURRENT_DATE - :win` (KIAT 는 published_at 없어 collected_at 폴백).

### 3.3 LLM 추출 — 신규 프롬프트 + youth_fit

`LlmClient.extract_tech_demand_gap(text)` + `_TECH_DEMAND_GAP_SYSTEM_PROMPT` + `_parse_tech_demand_gap` 신설.
- 의미: 입력은 기업의 수요기술 설명. "그 기술 역량이 부족해 생긴 미해결 갭(problem)"과 "청년이 그 역량을 키워 잡을 기회(opportunity)"를 추출.
- `youth_fit` 0~1 — 청년 개인이 학습·진입 가능한 정도. B2B 대규모 설비·자본집약·라이선스 진입장벽 기술이면 낮게.
- 수요기술로 보기 어렵거나 무의미하면 `problem=null`(억지 생성 금지).
- 반환 형식: `{problem, opportunity, detail, stakeholders, next_actions, youth_fit}`. discourse `extract_gap` 과 동일 구조 + `youth_fit`.

### 3.4 Silver 적재 — 전량 보존

- `data_role='TECH_DEMAND_SIGNAL'`, `raw_table_ref='raw_innovation_data'`.
- `youth_fit` 점수를 신규 컬럼 `youth_fit_score`(FLOAT, nullable)에 보존 — 임계 미만도 적재. 임계 재튜닝 시 LLM 재실행 없이 Gold 만 재사영.
- `GapRepository.upsert_silver` 를 `data_role`·`raw_table_ref`·`youth_fit_score` 파라미터화(현재 discourse 값 하드코딩 → 인자화, discourse 호출부는 기존값 전달로 무회귀).

### 3.5 Gold 사영 — 소스-인지 일반화 + youth_fit 게이트

`GapRepository.project_to_gold`(`_FETCH_SILVER_FOR_GOLD`) 일반화:
- evidence 를 소스별로 채운다 — `LEFT JOIN raw_discourse_data d ON d.id=g.raw_id AND g.raw_table_ref='raw_discourse_data'`, `LEFT JOIN raw_innovation_data i ON i.id=g.raw_id AND g.raw_table_ref='raw_innovation_data'`. evidence title/url = `COALESCE(d.headline, i.title)` / `COALESCE(d.source_url, i.source_url)`.
- `evidence_type` 분기: discourse → `'NEWS'`, innovation → `'TECH_DEMAND'` (`_INSERT_EVIDENCE` 의 type 을 raw_table_ref 로 도출).
- youth_fit 게이트: `WHERE extracted_problem IS NOT NULL AND (g.raw_table_ref <> 'raw_innovation_data' OR g.youth_fit_score >= :fit_min)`. discourse 는 NULL 이라 무조건 통과.
- 임계 `fit_min` = `settings.tech_demand_youth_fit_min`(기본 0.5) 신규.

### 3.6 스케줄러

- 신규 `_job_tech_demand_gap` — 키 없으면 스킵(기존 패턴). `gap_refine` 다음에 등록.
- `project_to_gold` 가 `gap_issues` 전체 삭제 후 **전 소스(discourse+tech_demand) 재조립**이라, 마지막 실행 잡이 완전한 Gold 를 만든다(순서 안전·멱등).

## 4. 데이터 흐름

```
raw_innovation_data (KIAT/KISTEP)
  └ refined_text_sector_class (Phase1 분류, sector_slug + confidence)   ← 입력 재사용
        ↓ TechDemandGapService (신규)
        ↓ LlmClient.extract_tech_demand_gap (신규 프롬프트, youth_fit 0~1)
  refined_gap_insights (data_role='TECH_DEMAND_SIGNAL', youth_fit_score) ← Silver 전량
        ↓ GapRepository.project_to_gold (소스-인지 + youth_fit 게이트)
  gap_issues / issue_evidences (evidence_type='TECH_DEMAND')            ← Gold, Gap 탭 통합
```

## 5. 변경 파일

| 파일 | 변경 |
|---|---|
| `core/llm/client.py` | `extract_tech_demand_gap` · `_TECH_DEMAND_GAP_SYSTEM_PROMPT` · `_parse_tech_demand_gap` 신설 |
| `models/bases/refined_gap_insights.py` + Alembic | `youth_fit_score FLOAT nullable` 컬럼 추가 |
| `core/config/settings.py` | `tech_demand_youth_fit_min`(기본 0.5) 추가 |
| `hub/repositories/gap_repository.py` | `fetch_unprocessed_tech_demand` 신설 · `upsert_silver` 파라미터화 · `_FETCH_SILVER_FOR_GOLD` 소스-인지 · `_INSERT_EVIDENCE` type 도출 · Gold youth_fit 게이트 |
| `hub/services/tech_demand_gap_service.py` | 신규 서비스 — fetch→extract→silver(전량)→project_to_gold 공유 |
| `core/scheduler.py` | `_job_tech_demand_gap` 신설 · `gap_refine` 다음 등록 |
| `scripts/` 테스트 | KIAT fetch disjoint · youth_fit 게이트 · discourse 무회귀 케이스 |

## 6. 백필

- 1차 — `limit=100~200` 소규모. 추출 품질·`youth_fit` 분포·Gold 통합·B2B 게이트 동작 육안 확인.
- 프롬프트·임계 튜닝 후 전체 백필(window 확대). 자연키 멱등이라 재실행 안전.
- 증분(일별 신규 KIAT)은 daily 파이프라인 text_classify → tech_demand_gap 잡이 흡수.
- **비용** — `gpt-4o-mini` × (분류 통과 KIAT 행 수) 추출 1회성. 1차 배치는 100~200 호출.

## 7. 성공 기준 / 검증

- **단위** — `fetch_unprocessed_tech_demand` 가 KIAT/KISTEP innovation 행만 반환(소스 disjoint), `youth_fit_score < fit_min` 행이 Silver 엔 있고 Gold 엔 없음, discourse gap 경로 무회귀.
- **통합** — 소규모 배치 후 `gap_issues` 에 `evidence_type='TECH_DEMAND'` evidence 존재, B2B 설비류가 게이트로 배제됨 육안 확인.
- **회귀** — 기존 gap 테스트 + `pulse_scoring_test`(Phase1 무영향) 통과.

## 8. 리스크 / 완화

- **youth_fit 주관성** — 소규모 배치로 임계 캘리브레이션, `settings` 분리로 LLM 재실행 없이 재튜닝.
- **KIAT keyword 짧음** — title+abstract+keyword 합쳐 입력, confidence 게이트 선통과분만 추출.
- **Gold 이중 사영**(gap_refine·tech_demand 각각 project_to_gold) — 멱등·전소스 재조립이라 무해. 구현 시 단일 사영 잡 통합 여부 검토.
- **KIAT source_url 결측 가능** — evidence url nullable 허용(기존 discourse 도 nullable).
