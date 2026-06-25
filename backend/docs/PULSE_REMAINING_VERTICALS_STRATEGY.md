# 남은 Pulse 수직 전략 & 태스크 분해

> 작성 2026-06-25. PulseTab에 아직 없는 3개 섹션(economic_briefings·causal_chains·crossover_metrics) + #1 빈약 섹터 신규 소스(2-A)의 전략·접근법·태스크를 병렬 설계로 도출. 빌드 순서·결정 포인트 포함.

## 0. ⚠️ 사실 정정 (설계 착수 전 필독)
1. **세 Gold 테이블 모두 미생성** — `economic_briefings`·`crossover_metrics`·`causal_chains`는 `erd.md §6.1`에 DDL *스펙만* 있고 어떤 alembic 마이그레이션에도 물리 생성돼 있지 않다(코드 참조 0건). 세 기능 모두 신규 마이그레이션이 필요하다(즉석 집계로 우회 시 예외 — crossover 참조).
2. **economic 축 섹터 매핑은 `sector_source_map`이 아니라 파이썬 `_SECTOR_CODE_MAP`** (`pulse_repository.py`)이다. `FINTECH/MOBILITY/CONTENT_MEDIA/EDUTECH`가 이미 등록돼 있고 KIPRIS 수집기가 `group_name`을 이미 기록 중 → 2-A의 "sector_source_map 시드 INSERT"는 economic 축에 **no-op**. innovation 축만 `sector_source_map`(arxiv_category/customs_group/tech_category/github_topic)을 JOIN한다.

## 1. 권장 빌드 순서
**2-A(토대) → economic_briefings(체감 최고) → crossover 1단계(결정론) → causal_chains(최대 리스크, 마지막)**.
- 2-A가 섹터 신호 공백을 메우면 Briefing·causal의 입력 품질이 함께 개선됨(공유 입력: 당일 raw_economic + pulse top섹터 + gap).
- Briefing이 깔아둔 LLM 파서·멱등키(SHA256/자연키)·prompt_version 자산을 causal이 물려받음.

## 2. 항목별 전략·태스크

### 2-A. 빈약 섹터 신규 신호 (effort S, 리스크 최저)
- **데이터원천**: 기존 prod 수집기(KIPRIS 특허 group_name, 관세 customs_group, Yahoo 시장 티커) — 추가 수집 불필요, 매핑/티커만.
- **권장**: (1) **KIPRIS 수율 read-only audit**(group_name 분포·최근 수율) — 게이팅 사실. (2) 관세 `COSMETICS→beauty-fashion` 시드 이미 존재 → 검증만. (3) **Yahoo ETF 티커 추가**(금융·모빌리티) + `_MARKET_SOURCE_MAP` 2건 — 유일한 실코드.
- **태스크**: ① KIPRIS audit(prod read) ② (필요시) 매핑 점검 ③ Yahoo 티커 2개 + `_MARKET_SOURCE_MAP` 추가 ④ 수집기 실행(prod write) ⑤ Pulse 엔드포인트로 섹터 점수 변화 검증.
- **결정**: 어느 Yahoo ETF부터(은행주 우선 권장). KIPRIS 수율 낮으면 2-B(부처 보도자료)로.

### economic_briefings (effort M, 가치 최고)
- **데이터원천**: 당일 raw_economic_data + pulse_metrics_log top3 섹터 + refined_gap_insights → LLM 3줄 생성.
- **접근**: ① LLM 생성(gpt-4o-mini, prompt v1, 40자/줄, trend_icon) + SHA256 멱등 + 템플릿 fallback ② 결정론 템플릿(즉석·무LLM·저품질) ③ 하이브리드. **권장 = ①** (fallback 템플릿 우선 출시 후 LLM 보강 가능).
- **마이그레이션 필요**: `refined_briefing_insights`(Silver) + `economic_briefings`(Gold).
- **태스크**: 마이그레이션 → ORM → LLM 프롬프트·순수 파서(+무DB 테스트) → Repo/RefineService(gap 패턴) → 엔드포인트 GET/POST `/insight/briefing` → 스케줄러 잡(일 10시) → 프론트 BriefingThreeLines → 테스트.
- **결정**: LLM vs 템플릿 우선, 희소 데이터(0~2건/일) 처리, trend_icon 매핑.

### crossover_metrics 1단계 (effort M, 결정론·환각 0)
- **데이터원천**: pulse_metrics_log(이미 라이브). 12섹터를 legacy/emerging 이원 분류 → 그룹별 일평균 score 시계열 → 교차점.
- **접근**: ① 섹터 이원 분류(권장, 결정론) ② 신호 data_role 비교(refined_innovation_signal, 희소) ③ 채용/검색 수요(raw_people_data, LLM 분류). **권장 = ① + ② 하이브리드(1단계는 ①만)**.
- **마이그레이션**: Gold 테이블 가능하나, **즉석 집계(pulse_overview/keywords 패턴)로 우회하면 마이그레이션·prod 쓰기 0** — 1단계 권장 경로.
- **태스크**: M1 전통/신흥 분류 정의(데이터로 교차점 실재 확인) → M2 즉석 집계 SQL+순수함수(+무DB 테스트) → M3 엔드포인트 → M4 프론트 _CrossoverLineChart 라이브 교체.
- **결정**: **전통/신흥 섹터 분류 기준**(고정 vs 동적 기울기), 교차점 정의(선형보간 vs 임계값).

### causal_chains (effort M-최대, 환각 리스크 최고)
- **데이터원천**: raw_economic_data → text_sector_classify(가동 중) → LLM 인과 추출(거시→산업→청년기회), 섹터×주간 1개.
- **접근**: ① Gold 직접(최소) ② **완 메달리온**(refined_causal_chain_insights→causal_chains, 권장·ERD 정합) ③ 클러스터링+규칙(LLM 최소).
- **마이그레이션 필요**: Silver + Gold.
- **태스크**: 마이그레이션 → ORM → LLM 프롬프트 extract_causal_chain(gap 패턴) → Repo/RefineService(섹터×주간 최신 1개) → 주간 스케줄러 잡 → 엔드포인트 → 프론트 CausalChainCards → 테스트.
- **결정**: confidence 임계값, 주간 vs 일간, 섹터 귀속 신뢰도, 노출 위치.

## 3. 공통(cross-cutting) 재사용·함정
- LLM 인프라: `core/llm/client.py`의 classify_sector/extract_* + `_parse_*` 순수 파서 패턴 확장.
- 서비스: `gap_refine_service`의 upsert_silver→project_to_gold(prompt_version)·confidence 임계 = Briefing/causal 청사진. `pulse_overview.py`·`keyword_trends.py`(즉석 집계) = crossover 1단계 청사진.
- 프론트: PulseTab.tsx TanStack Query 훅 + PanelStatus 컨벤션 재사용.
- 함정: economic 축 섹터 매핑은 `_SECTOR_CODE_MAP`(파이썬), innovation 축만 `sector_source_map`(JOIN). 신규 매핑 시 경로 먼저 확인.

## 4. prod 작업 경계
- 2-A audit = prod read. Briefing·causal = 마이그레이션 적용(스키마 변경) + LLM 잡 실행(쓰기·토큰 비용). crossover 1단계(즉석) = prod 무관.
- 모든 prod 쓰기는 비용·되돌리기 영향 있음 — 실행 전 확인.
