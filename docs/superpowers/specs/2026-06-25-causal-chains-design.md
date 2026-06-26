# causal_chains (인과사슬) — 설계 (Spec)

> 작성 2026-06-25. market_insight 도메인. PulseTab에 "거시 이벤트 → 산업 영향 → 청년 기회" 3단 인과 카드를 채운다. gap 수직과 동일한 완전 메달리온(Silver→Gold), prod 마이그레이션 2테이블. 전략: [PULSE_REMAINING_VERTICALS_STRATEGY.md](../../../backend/docs/PULSE_REMAINING_VERTICALS_STRATEGY.md).

## 0. 목표 & 성공 기준
- `GET /api/insight/causal-chains` 가 섹터별 최신 1개 인과사슬을 반환.
- 순수 파서 `_parse_causal` 무DB 테스트 `FAIL=0`.
- 일별 잡 `causal_refine`(멱등, 미처리 분류 economic만 LLM). 환각 완화: 3요소 모두 있어야 유효.
- 프론트 PulseTab CausalChainCards 섹션 라이브, `tsc` 통과.

## 1. 데이터 흐름 (gap 패턴 미러)
분류된 `raw_economic_data`(refined_text_sector_class, sector+confidence≥임계) → LLM extract_causal_chain(macro_event, industry_impact, youth_chance) → `refined_causal_chain_insights`(Silver, 멱등 raw_id/pv) → `causal_chains`(Gold, 섹터×최신 1개 full-replace 사영).

## 2. 마이그레이션 (Silver+Gold, 수동 revision)
- `refined_causal_chain_insights`: id, sector_slug(FK), macro_event/industry_impact/youth_chance(nullable), reference_date, raw_table_ref/raw_id, model_name/prompt_version/input_hash, processed_at. UNIQUE(raw_table_ref, raw_id, prompt_version).
- `causal_chains`(ERD §6.1): id, sector_slug(FK), macro_event/industry_impact/youth_chance(NOT NULL), published_date, is_active, created_at.
- autogenerate는 sectors ORM 미등록으로 실패 → 수동 op.create_table. down_revision = a7d3f1b9c2e4.

## 3. LLM (core/llm/client.py)
- `_CAUSAL_SYSTEM_PROMPT`: 거시 이벤트→산업 영향→청년 기회 3단 추출, 셋 다 명확할 때만(억지 생성 금지). JSON `{"macro_event","industry_impact","youth_chance"}`(불명확 시 각 null).
- `_parse_causal(raw) -> dict`(순수): 3요소 모두 비어있지 않아야 유효, 하나라도 없으면 전부 None.
- `LlmClient.extract_causal_chain(text)`.

## 4. 리포지토리·서비스 (gap 미러)
- `CausalChainRepository`: `fetch_unprocessed`(분류 economic, causal 미처리), `upsert_silver`(ON CONFLICT DO NOTHING), `project_to_gold`(causal_chains 전체삭제 후 섹터×최신 유효 1개 재생성), `fetch_chains`(서빙 — 섹터명·accent JOIN).
- `CausalChainRefineService.refine_and_serve(window_days, limit)`: 미처리 → LLM → upsert_silver → project_to_gold. confidence 임계 = settings.llm_classify_confidence_min.

## 5. 엔드포인트·스케줄러
- `GET /api/insight/causal-chains` → `{success, chains:[{sector_slug, sector_name, accent_color, macro_event, industry_impact, youth_chance, published_date}]}`.
- `POST /api/insight/causal-chains/refine` 수동 트리거.
- `_job_causal_refine` → `_DAILY_JOBS`의 gap_refine 다음(같은 분류 economic 입력).

## 6. 프론트 (PulseTab)
`dashboard.ts` `fetchCausalChains` + 타입. `useDashboard` `useCausalChains`. PulseTab CausalChainCards 섹션 — 섹터별 3단(거시→산업→청년) 하향 화살표 카드, PanelStatus.

## 7. 테스트
- `scripts/causal_test.py`(무DB): `_parse_causal`(정상 3요소/불완전→None/bad json→None). `FAIL=0`.
- `tsc` + prod(마이그레이션 적용 + refine 1회 → GET 검증).

## 8. 비범위
crossover(완료)·economic_briefings(완료). prompt_version v1 고정. 섹터 드릴다운 노출은 메인 섹션으로 충분.
