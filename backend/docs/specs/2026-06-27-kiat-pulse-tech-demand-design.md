# KIAT 수요기술 → Pulse `tech_demand` 축 연결 (Phase 1)

- **작성일** 2026-06-27
- **상태** 설계 승인, 구현 대기
- **범위** Phase 1 (Pulse 트렌드 연결). Gap 기회 신호는 Phase 2 — 본 문서 범위 밖.

---

## 1. 배경 / 문제

Bronze 결측 측정(`scripts/bronze_null_audit.py`) 결과, `raw_innovation_data` 11,671건 중 **KIAT(`INNOVATION_KIAT_TECH_DEMAND`)가 11,226건(96%)**을 차지한다. 그런데 `market_insight` 전체에서 KIAT 를 소비하는 코드는 **0건**이다.

- Pulse innovation 축([pulse_repository.py](../../domain/market_insight/hub/repositories/pulse_repository.py) `_INNOVATION_SIGNAL_SQL`)은 `sector_source_map` 으로 매핑되는 ArXiv·Customs·Techblog·GitHub 만 사용하고, 주석에 "분류 필드 없는 KIAT/KISTEP 제외"로 명시되어 있다.
- KIAT 는 keyword 가 자유 텍스트라 `sector_source_map` 고정 매핑이 불가능해 제외됐다.

결과적으로 innovation 96%가 수집 비용만 쓰고 활용되지 않는 dead data 다. (참고: KIAT API 는 `published_at` 필드 자체가 없음을 라이브로 확인 — 날짜 결측은 소스 한계이며 Pulse 는 `COALESCE(published_at, collected_at)` 폴백으로 이미 무해 처리.)

## 2. 목표 / 비목표

**목표**
- KIAT(+KISTEP) 를 LLM 섹터 분류해 Pulse 의 신규 `tech_demand` 축으로 소비한다.
- dead data 96%를 트렌드 신호로 전환한다.
- 기존 economic/discourse 분류·축에 회귀를 만들지 않는다.

**비목표 (Phase 2 이후)**
- Gap 기회 신호 변환(수요기술 → 문제·기회 추출).
- KIAT 적합도 필터(B2B 설비 기술 등 청년 무관 항목 배제).

## 3. 설계

### 3.1 분류 대상 — 이중집계 방지
- `raw_innovation_data` 중 **KIAT·KISTEP source_type 만** 분류한다. GitHub·ArXiv·Customs·Techblog 는 이미 innovation 축에 있으므로 제외(`_FETCH_UNCLASSIFIED_ECONOMIC` 의 disjoint 패턴과 동일).
- 분류 입력 텍스트: `title + abstract_text + (raw_metadata->>'keyword')`.
- 기존 인프라 재사용: [text_sector_classify_service.py](../../domain/market_insight/hub/services/text_sector_classify_service.py) `_TARGET_TABLES` 에 `raw_innovation_data` 추가 + 전용 fetch SQL.

### 3.2 신규 `_FETCH_UNCLASSIFIED_INNOVATION` SQL
- `raw_innovation_data` 에서 `source_type IN ('INNOVATION_KIAT_TECH_DEMAND','INNOVATION_KISTEP_REPORT')` 이고 `refined_text_sector_class` 에 미적재인 행.
- window 필터는 `collected_at::date`(KIAT 는 published_at 없음).
- `refined_text_sector_class` 멱등 적재는 기존 `_UPSERT_TEXT_SECTOR`(`raw_table_ref='raw_innovation_data'`) 그대로 사용.

### 3.3 신규 `tech_demand` 축 — innovation 과 분리
- Pulse text axis 집계 SQL 에 `raw_table_ref='raw_innovation_data'` 분류 결과를 **새 축 `tech_demand`** 로 UNION 추가한다.
- innovation 축(생산: 논문·특허·코드)과 **분리**한다 — KIAT 는 "기업의 기술 수요"라 생산 신호와 의미가 다르다. 합치면 신호 해석이 흐려진다.
- `reference_date = COALESCE(published_at, collected_at)::date` (기존 패턴 일관, KIAT 는 collected_at).
- **축 가중치 0.5** 제안(수요는 생산 신호의 보조). 추후 실데이터로 튜닝 — 기존 가중치도 heuristic.

### 3.4 백필
- 기존 11,226건을 1회 분류한다(분류 window 를 확대해 실행). `refined_text_sector_class` 자연키(`raw_table_ref, raw_id, prompt_version`) 멱등이라 재실행 안전.
- 증분(일별 신규 KIAT)은 기존 daily refine 파이프라인의 text_classify 단계가 흡수한다.
- **비용** — `gpt-4o-mini` × ~11,226회 분류(1회성). 본 작업의 유일한 실비용.

## 4. 데이터 흐름

```
raw_innovation_data (KIAT/KISTEP)
   ↓ TextSectorClassifyService (LLM, 신규 대상)
refined_text_sector_class (raw_table_ref='raw_innovation_data')
   ↓ Pulse text axis SQL (신규 tech_demand 축, weight 0.5)
refined_pulse_metric_silver → pulse_metrics_log (Gold)
```

## 5. 변경 파일

| 파일 | 변경 |
|---|---|
| `text_sector_classify_service.py` | `_TARGET_TABLES` 에 `raw_innovation_data` 추가 |
| `pulse_repository.py` | `_FETCH_UNCLASSIFIED_INNOVATION` 신설 · `fetch_unclassified_text_rows` 분기 · text axis SQL 에 `tech_demand` UNION · 축 가중치 |
| `scripts/bronze_expansion_parse_test.py` · `scripts/pulse_scoring_test.py` | KIAT 분류 fetch·disjoint(parse_test), `tech_demand` 축 집계·회귀(pulse_test) |

## 6. 성공 기준 / 검증

- **단위** — KIAT 분류 fetch SQL 이 KIAT/KISTEP 만 반환(이중집계 방지), `tech_demand` 축 집계가 섹터별 건수 산출, 기존 economic/discourse 분류 무회귀.
- **백필 검증** — 실행 후 `refined_text_sector_class` 의 `raw_innovation_data` 분류 건수 확인, `bronze_null_audit` 재측정으로 활용률 전환 확인.
- **회귀** — 기존 pulse 테스트(`pulse_scoring_test`·`pulse_axis_normalize_test`) 통과.

## 7. 리스크 / 완화

- **LLM 분류 정확도** — KIAT keyword 가 짧아 섹터 오분류 가능. `confidence` 임계(`llm_classify_confidence_min`)로 저신뢰 제외, 기존 분류와 동일 게이팅.
- **백필 비용·시간** — 1회성. limit 배치로 분할 실행.
- **축 가중치 미검증** — 0.5 는 heuristic. 백필 후 Pulse 점수 분포로 튜닝.

## 8. Phase 2 예고 (범위 밖)

분류된 KIAT(`refined_text_sector_class`)를 재사용해 Gap 기회 신호로 변환. `gap_refine_service` 가 KIAT 를 입력으로 받아 "기업 미확보 기술 → 청년 기회" 추출 + 적합도 필터. 별도 spec.
