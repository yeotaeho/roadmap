# Economic / Opportunity 데이터 소스 — 제약·구현 이력 (2026-05-31)

> **상태: 역사 문서**
>
> 이 문서의 “미구현” 표기는 2026-05-31 당시 판단이다.
> BOK ECOS, 보조금24, DART 정기공시, MFDS/MSS, DART IPO, NPS,
> Naver DataLab과 KIPRIS는 이후 구현되었다.
> 현재 구현 여부는
> [`MASTER_BRONZE_IMPLEMENTATION_STATUS.md`](./MASTER_BRONZE_IMPLEMENTATION_STATUS.md)를 SSOT로 사용한다.

Roadmap Bronze 수집 전략에서 **접근이 막히거나 비용이 큰 소스**, **P1 후보**, **이미 코드로 연동된 소스**를 한곳에 정리합니다.  
출처 목록 SSOT: [`backend/docs/DATA_COLLECTION_SOURCES_GUIDE_V3.md`](../../../../../docs/DATA_COLLECTION_SOURCES_GUIDE_V3.md) §1·§1-1·§1-2·§5.
**본 문서**는 당시 제약과 우선순위 판단을 보존하는 기록이다.

---

## 1. 요약 — “돈의 흐름” 분석 성숙도

| 레이어 | 수준 (5단계) | 비고 |
|--------|-------------|------|
| Bronze **수집** | **3 / 5** | 정부·RSS·Yahoo·시계열 파이프라인 구축 |
| Bronze **분석·집계** | **~1.5 / 5** | Silver/Gold·`funding_volume_growth` 미구현 |
| 제품 목표 (`TREND_ANALYSIS.md`) | **~20%** | 5대 선행 지표 중 Economic 축만 부분 커버 |

**지금 할 수 있는 것:** 뉴스·공고·급증·(적재 시) ETF 일별 거래대금의 **원천 적재·수동 SQL 분석**  
**아직 어려운 것:** 섹터별 유입 증가율 Pulse, 민간 금액 ground truth, NTIS급 정부 R&D 정량 단일원

---

## 2. 접근 제약 소스 (Held / Skip)

의도적으로 **지금 단계에서 넣지 않거나**, **조건이 충족될 때만** 여는 소스입니다.

| 소스 | 제약 | 프로젝트 스탠스 | Unlock 조건 | 대체 (현재) |
|------|------|----------------|-------------|-------------|
| **NTIS OpenAPI** | 기관 소속·승인 후 API 키 발급이 일반적 | **Held** — MVP 필수 아님 | 대학·TIPS·법인·연구과제 등으로 키 확보 | MSIT mId=63·보도/사업공고, [ALIO 15125286](https://www.data.go.kr/data/15125286/openapi.do) |
| **네이버 금융 뉴스** | 상업적 이용·ToS 🔴 | **Skip** | 공식 API·제휴·비상업 범위 명확화 | DART, Wowtale·Platum·벤처스퀘어 RSS |
| **The VC** | 크롤링·DB권·상업 이용 리스크 | **Skip** | 라이선스·제휴 | RSS 3원 + DART + (예정) `verified_company_master` CSV |
| **Crunchbase API** | Full API는 **견적·연 라이선스** (웹 Pro ≠ 데이터 API) | **Skip** (P2 이후) | Silver dedup 설계 + 연 예산 확보 | 국내 RSS + 정규식 금액 |

### 2.1 공통 원칙

- 막힌 소스 때문에 “돈의 흐름”을 포기하는 것이 아니라 **프록시 조합**으로 간다.  
  - **이벤트(민간):** RSS 3원 + DART(B·D)  
  - **정부 정량:** MSIT·ALIO·MOEF · (P1) 보조금24  
  - **정부 정성 보조:** 부처 보도자료 → `raw_economic_data` ([V3 §1-2](../../../../../docs/DATA_COLLECTION_SOURCES_GUIDE_V3.md))
  - **시장:** Yahoo 급증 + `raw_market_timeseries` · (P1) BOK ECOS  
- NTIS·Crunchbase는 **“있으면 게임이 바뀌는 업그레이드”**, MVP **필수 조건 아님**.
- **네이버 금융 뉴스**는 V3 §1 표에 **Skip** 등록 — [§2](#2-접근-제약-소스-held--skip)와 동일.

---

## 3. 공공 API·기관 사이트 — 구현 여부 (질문 대응)

### 3.1 중소벤처기업부 사업공고 — [15113297](https://www.data.go.kr/data/15113297/openapi.do)

| 항목 | 내용 |
|------|------|
| **사용 여부** | ✅ **이미 사용 중** |
| **코드** | `smes_collector.py` → `BronzeOpportunityIngestService.ingest_smes()` |
| **적재 테이블** | **`raw_opportunity_data`** (GRANT — Chance 탭·지원사업) |
| **Economic?** | ❌ `raw_economic_data` 아님 — **신청형 지원 “기회”** 축 |
| **환경변수** | `SMES_SERVICE_KEY` (또는 `SMES_API_KEY`) |
| **스케줄** | 일일 `smes_opportunity` (`core/scheduler.py`) |
| **API** | `POST /api/master/bronze/opportunity/smes` (라우터 확인) |
| **트래픽** | 개발계정 일 100건 수준 ([포털 명세](https://www.data.go.kr/data/15113297/openapi.do)) — 페이지네이션·`max_items`로 관리 |

**어떻게 보나:** Economic(자본 **흐름** 관측)보다 **Opportunity(돈을 받을 공고)** 에 가깝습니다. 다만 정부가 **어디에 예산을 쏟는지** 거시 신호로는 Silver에서 Economic과 교차 분석 가능.

---

### 3.1-b 중기부 지원사업 **선정·집행** API (15113297 확장)

공고 API(`15113297`)만으로는 **“누가 실제로 받았는가”**·**“언제 지급됐는가”**를 알 수 없습니다. V3 §5 GRANT 보조 행 · [COLLECTOR_EXPANSION_REVIEW.md](./COLLECTOR_EXPANSION_REVIEW.md) §SMES 확장 참조.

| API (후보) | 사용 여부 | 적재 | Economic? | 우선순위 |
|------------|-----------|------|-----------|----------|
| **선정 결과** (추정 `getSelectionResult` 등) | ❌ 미구현 | `raw_opportunity_data` + `raw_metadata` (`slctnAmt`, `slctnEntrpsNm`) | Silver에서 RSS·DART와 **교차** — “정부가 고른 기업” 시그널 | **P1** |
| **집행(지급) 현황** (`exctnAmt`, `exctnDt`) | ❌ 미구현 | 테이블 Silver 설계 시 확정 (Opportunity 메타 또는 Economic 보조) | **실제 자본 집행** 추적 | **P2** |

**구현 부담:** `smes_collector.py` 패턴 재사용 · data.go.kr 포털에서 API 명세·키 추가 신청 필요 (1~2영업일).

---

### 3.2 K-Startup 통합공고 — [15125364](https://www.data.go.kr/data/15125364/openapi.do)

| 항목 | 내용 |
|------|------|
| **사용 여부** | ❌ **미구현** (가이드에만 “우선 추천”) |
| **권장 테이블** | `raw_opportunity_data` (GRANT) |
| **SMES와 관계** | 창업진흥원 vs 중기부 — **공고 중복 가능** → Silver에서 dedup |
| **트래픽** | 개발계정 **10,000건/일** ([포털 명세](https://www.data.go.kr/data/15125364/openapi.do)) — SMES보다 여유 |
| **우선순위** | SMES 다음 **Opportunity 확장 P0** (동일 `data.go.kr` 키로 활용 가능한 경우 많음) |

#### Economic 관점에서 “쓸 가치” 있나?

**결론: Economic 메인은 아니지만, 구현할 가치는 높음 (Opportunity 축).**

| 질문 | 답 |
|------|-----|
| **의미 없는 데이터?** | ❌ 아님 — 다만 **`raw_economic_data`에 넣는 소스가 아님** |
| **데이터 본질** | 창업진흥원 **사업 공고** (모집·지원대상·신청) = “돈을 **받을** 기회” |
| **Economic과의 관계** | 직접 “유치 300억” 이벤트 ❌ / **정부·창업 정책이 어느 분야로 쏠리는지** 선행 신호 ⭕ |
| **안 넣으면** | 지원 공고가 [SMES 15113297](https://www.data.go.kr/data/15113297/openapi.do) 쪽에 치우칠 수 있음 |
| **제품** | **Chance·지원사업 매칭** — 타깃 유저(청년·스타트업)와 직결 |
| **구현 부담** | SMES 컬렉터 패턴 복사 수준 — 공공 API·무료 |

---

### 3.3 한국벤처투자 (KVIC) — [kvic.or.kr](https://www.kvic.or.kr/)

| 항목 | 내용 |
|------|------|
| **사용 여부** | ❌ **미구현** (코드·스케줄 없음) |
| **사이트 성격** | 모태펀드·출자·민간 VC 생태계 **공식 통계** (홈에 조성액·투자규모·상장 배출 등 집계) |
| **개방 채널 (홈페이지 기준)** | **발간자료** (벤처금융레터, [KVIC MarketWatch](https://www.kvic.or.kr/)), **보고서**, 정보공개 → **공공데이터 개방 · 펀드현황 Open API** (별도 신청·명세 확인 필요) |
| **Economic 매핑 후보** | |
| | • **거시 집계:** 분기별 출자·투자 규모 → `raw_economic_data` (`GOVT_KVIC_AGG`, `investment_amount` + `raw_metadata`) |
| | • **이벤트 아님:** 개별 스타트업 라운드 DB는 The VC·RSS 영역 |
| **TREND_ANALYSIS 연결** | 가이드에 “KVIC 보고서” 언급 — **PDF/보고서 주기 수집** 또는 **펀드 Open API**가 NTIS 없을 때 **민간↔정부 벤치마크 분모** 보완 |
| **우선순위** | **P1 (Economic 보조)** — NTIS Held일 때 **정부·모태펀드 축 정량** 보강 |

**어떻게 보나:** SMES/K-Startup과 달리 **“공고”가 아니라 “벤처 생태계 집계·리서치”** 소스. Crunchbase 대체는 아니고, **“한국 VC 시장 전체 규모·추세”** 용.

#### Economic 관점에서 “쓸 가치” 있나?

**결론:** Economic 보조 축으로 쓸 가치 있음 — 당장 필수는 아님 (P1).

| 질문 | 답 |
|------|-----|
| **의미 없는 데이터?** | ❌ 아님 — **해상도가 거친 거시 지표**일 뿐 |
| **잘 맞는 용도** | NTIS·Crunchbase 없을 때 **“한국 VC 시장 전체 온도”** (모태펀드 출자·민간 투자 규모 추세) |
| **안 맞는 용도** | 섹터별·기업별 “누가 얼마 받았나” — Wowtale·DART 영역 |
| **안 넣어도** | RSS 3원 + Yahoo 시계열로 **Economic MVP는 가능** |
| **넣으면** | “뉴스만 뜨는데 시장은 실제로 식었다” 같은 **맥락·벤치마크** 개선 |
| **구현 부담** | 펀드 Open API 명세·인증 또는 MarketWatch PDF 파이프라인 — RSS보다 큼 |

---

### 3.4 K-Startup vs KVIC — Economic 관련 한눈에

```
                    Economic 핵심도 ↑
    Wowtale/Platum/VS  DART  Yahoo + raw_market_timeseries  MSIT/ALIO
                         │
         ────────────────┼────────────────
                         │
              KVIC (거시 집계, 보조)     K-Startup (공고 → Opportunity)
                         ↓
                  테이블·제품 축이 다름
```

| 소스 | **쓸 가치** | **지금 당장** | **주로 맞는 축** | **Economic만 보면** |
|------|------------|--------------|-----------------|---------------------|
| **K-Startup 15125364** | ✅ **높음** | SMES 다음 **추천 구현** | **Opportunity** (Chance) | 정책·공고 **방향** 보조 |
| **KVIC** | ✅ **중간** | backfill·Silver 여유 후 | **Economic 보조** (거시) | 시장 **전체 규모·추세** |
| **SMES 15113297** | ✅ 높음 | ✅ 이미 구현 | **Opportunity** | (K-Startup과 유사) |

**요약 (2026-05-31):**

- 둘 다 **“Economic에 쓸모없다”가 아님**.
- **K-Startup** → Economic보다 **Opportunity P0**가 맞고, **넣는 이득이 큼**.
- **KVIC** → **있으면 Economic 품질이 한 단 올라가는 선택 옵션**, MVP 필수는 아님.

---

### 3.5 Economic P1 후보 — 정량 거시 (미구현)

[V3 §1-1](../../../../../docs/DATA_COLLECTION_SOURCES_GUIDE_V3.md) · `BRONZE_ARCHITECTURE_DECISION.md` §6대 핵심 소스. **금액·지급주체·수혜자**가 명시되는 “진짜 자본 흐름” 축.

| 소스 | URL / API | 매핑 | `source_type` (안) | 상태 | 비고 |
|------|-----------|------|----------------------|------|------|
| **보조금24 통합조회** | [gov24.go.kr](https://www.gov24.go.kr/) Open API | `raw_economic_data` | `GOVT_SUBSIDY24_*` | ❌ P1 | 정부→기업/개인 보조금 · 월 ~2,000건+ 예상 |
| **한국은행 ECOS** | [ecos.bok.or.kr/api](https://ecos.bok.or.kr/api/) | `raw_economic_data` | `BOK_ECOS_*` | ❌ P1 | FDI·통화량·금리 시계열 · `investment_amount`=None |
| **FSS 사모펀드 공시** | [dis.fss.or.kr](https://dis.fss.or.kr/) | `raw_economic_data` | `FSS_PE_FUND_*` | ❌ P1 | PE/VC 펀드 결성·운용 · KVIC 거시와 보완 |

**우선순위:** 보조금24 → BOK ECOS → FSS 사모펀드.

---

### 3.6 DART 확장 — 정기공시(A)

| 항목 | 내용 |
|------|------|
| **현재 구현** | ✅ **주요사항보고(B)** + ✅ **지분공시(D)** — `dart_collector.py` + `dart_detail_fetcher.py` |
| **미구현** | ❌ **정기공시(A)** — 사업·분기·반기보고서의 R&D비·CAPEX·해외출자 **계획** |
| **B vs A** | B = **이미 결정된** M&A·증자·시설투자 / A = **향후 3~5년** 투자·R&D 계획 |
| **우선순위** | **P1** — 별도 `DartRnDCollector` 검토 ([COLLECTOR_EXPANSION_REVIEW.md](./COLLECTOR_EXPANSION_REVIEW.md)) |
| **품질 이슈** | B·D 상세 파싱 후에도 `investment_amount` **Phase 3 미완** — P2로 유지 |

---

### 3.7 정부 부처 보도자료 — Economic 보조축

[V3 §1-2](../../../../../docs/DATA_COLLECTION_SOURCES_GUIDE_V3.md) · `GOVT_DOCS_COLLECTION_STRATEGY.md` · `BRONZE_ARCHITECTURE_DECISION.md` 두 축 전략.

| 질문 | 결정 (2026-05-31) |
|------|-------------------|
| **§1 vs §4?** | **`raw_economic_data` Economic 보조축** — §4 Discourse(담론·커뮤니티) **아님** |
| **역할** | “돈이 흐르기 **전**” 정책·산업 방향 신호 — Silver에서 MSIT/ALIO/KONEPS **정량과 시간 정렬** |
| **선행 사례** | ✅ **`GOVT_MSIT_PRESS`** (`mId=307`, 연도+“시행” 필터) — 이미 일 스케줄 |
| **범위** | 22개 부처 전체 ❌ — BOK·MFDS·KOCCA/KHIDI(P0), FSC·MOTIE·ME·MOHW·MOLIT(P1) 등 **7~8개만** |
| **구현** | ❌ 전부 미구현 (보도자료 크롤러·`GOVT_*_PRESS` 템플릿) |
| **중복 금지** | 동일 URL을 §4에 **이중 적재하지 않음** |

---

## 4. Economic Bronze — 구현 완료 vs 공백 (2026-05-31)

### 4.1 `raw_economic_data` — 구현됨

| 소스 | 컬렉터 | 스케줄 | 비고 |
|------|--------|--------|------|
| DART **B·D** | `dart_collector.py` + `dart_detail_fetcher.py` | 일 `dart` | 지분공시(D) 기본 포함 · A(정기공시) ❌ |
| Wowtale / Platum / Venturesquare | `*_collector.py` | 일 | RSS 금액 정규식 추출 ⭕ |
| Wowtale 아카이브 | `wowtale_archive_crawler.py` | 수동/backfill | |
| StartupRecipe | `startup_recipe_collector.py` | 일 | 금액 추출 ❌ |
| MSIT 보도/사업/R&D | `msit_*` | 일 | 보도=부처 보조축 **선행 사례** |
| ALIO 사업 | `alio_public_inst_project_collector.py` | 주 `alio_projects` | |
| MOEF PDF | `moef_local_pdf_collector.py` | 수동 업로드 | `GOVT_MOEF_BUDGET` / `GOVT_MOEF_FISCAL` |
| Yahoo Volume Surge | `yahoo_finance_collector.py` | 주 | |
| Yahoo Macro | `yahoo_macro_collector.py` | 주 | |

### 4.2 `raw_market_timeseries` — 구현됨 (별 테이블)

| 소스 | 컬렉터 | 스케줄 |
|------|--------|--------|
| Yahoo 16티커 OHLCV | `yahoo_market_timeseries_collector.py` | 일 `yahoo_market_ts` |

API: `POST /api/master/bronze/market-timeseries/yahoo`  
DDL: `backend/docs/erd.md` §4

### 4.3 Economic / Opportunity — 미구현·약함

| 항목 | 상태 | § 참조 |
|------|------|--------|
| NTIS | Held | §2 |
| The VC / **네이버 금융** / Crunchbase | Skip | §2 · V3 §1 |
| **보조금24 / BOK ECOS / FSS 사모펀드** | ❌ P1 미구현 | §3.5 · V3 §1-1 |
| **DART 정기공시(A)** | ❌ P1 미구현 | §3.6 |
| **부처 보도자료** (BOK·FSC·MOTIE 등) | ❌ 미구현 | §3.7 · V3 §1-2 |
| KONEPS 입찰 → economic 메타 | ❌ 미구현 | V3 §5 BID |
| KVIC 집계·Open API | ❌ P1 | §3.3 |
| DART `investment_amount` Phase 3 | 🟡 미완 (B·D 상세 fetcher 있음) | §3.6 |
| ALIO `investment_amount` | 대부분 `None` | NTIS/KONEPS 보완 예정 |
| K-Startup API | ❌ Opportunity P0 | §3.2 |
| **SMES 선정 결과 API** | ❌ P1 | §3.1-b |
| **SMES 집행 현황 API** | ❌ P2 | §3.1-b |

---

## 5. 우선순위 (제약을 고려한 로드맵, 2026-05-31)

| 순위 | 작업 | 축 | 이유 |
|------|------|-----|------|
| **P0** | DB backfill + `SCHEDULER_ENABLED=true` | 공통 | 코드만으로는 데이터 없음 |
| **P0** | **K-Startup 15125364** 컬렉터 | Opportunity | SMES와 complementary · 일 10,000건 여유 |
| **P1** | **보조금24 OpenAPI** | Economic 정량 | 6대 핵심 소스 · 월 ~2,000건+ |
| **P1** | **BOK ECOS API** | Economic 정량 | 거시 FDI·통화량 선행 지표 |
| **P1** | **FSS 사모펀드 공시** | Economic 정량 | PE/VC · KVIC 보완 |
| **P1** | **DART 정기공시(A)** | Economic | R&D·CAPEX 계획 · B와 상호 보완 |
| **P1** | **SMES 선정 결과 API** | Opportunity→Silver | “정부가 고른 기업” · 공고 JOIN |
| **P1** | **KVIC** 펀드 Open API 또는 MarketWatch PDF | Economic 보조 | NTIS 대체 거시 VC 지표 |
| **P1** | Silver: RSS dedup + 주간 섹터 건수/금액 | Silver | Bronze → “흐름” 가시화 |
| **P1** | **부처 보도자료 P0** (BOK·MFDS·KOCCA/KHIDI) | Economic 보조 | MSIT_PRESS 템플릿 확장 |
| **P2** | DART `investment_amount` Phase 3 완성 | Economic | B·D 상세 파싱 커버리지 확대 |
| **P2** | **SMES 집행 현황 API** | Economic/Opportunity | 선정≠지급 · 실질 집행 추적 |
| **P2** | 부처 보도자료 P1 (FSC·MOTIE·ME·MOHW·MOLIT) | Economic 보조 | 산업별 정책 신호 |
| **Held** | NTIS | Economic | 키 확보 시 P0 승격 |
| **Held** | Crunchbase | Economic | 예산·Silver 후 |
| **Skip** | 네이버 금융·The VC | — | §2 · V3 §1 |

---

## 6. 관련 문서

- [`backend/docs/DATA_COLLECTION_SOURCES_GUIDE_V3.md`](../../../../../docs/DATA_COLLECTION_SOURCES_GUIDE_V3.md) — 출처 목록 SSOT (§1-1 P1 후보 · §1-2 부처 보도 · §5 SMES 확장)
- [`COLLECTOR_EXPANSION_REVIEW.md`](./COLLECTOR_EXPANSION_REVIEW.md) — DART(A)·SMES 선정/집행 API 확장 검토
- [`GOVT_DOCS_COLLECTION_STRATEGY.md`](../government/GOVT_DOCS_COLLECTION_STRATEGY.md) — MOEF·MSIT·MOTIE·ME · `source_type` 정의
- [`DART_ECONOMIC_ENHANCEMENT_STRATEGY.md`](../dart/DART_ECONOMIC_ENHANCEMENT_STRATEGY.md) — DART B·D·A 로드맵
- [`WOWTALE_YAHOO_ENHANCEMENT_STRATEGY.md`](../market/WOWTALE_YAHOO_ENHANCEMENT_STRATEGY.md) — Wowtale/Yahoo 확충 (상단 스냅샷 구버전 — 본 문서·IMPL 우선)
- [`YAHOO_VENTURESQUARE_IMPL.md`](../market/YAHOO_VENTURESQUARE_IMPL.md) — Yahoo Macro backfill·벤처스퀘어
- [`WOWTALE_ARCHIVE_CRAWLER_IMPL.md`](../startup_media/WOWTALE_ARCHIVE_CRAWLER_IMPL.md) — 아카이브 backfill
- [`BRONZE_ARCHITECTURE_DECISION.md`](./BRONZE_ARCHITECTURE_DECISION.md) — 6대 정량 소스·부처 매트릭스·품질 진단
- [`SMES_OPENAPI_COLLECTION_GUIDE.md`](../opportunity/SMES_OPENAPI_COLLECTION_GUIDE.md) — 15113297 상세
