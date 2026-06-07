# 한국 트렌드 분석 및 예측 엔진 — 데이터 수집 출처 가이드 (v3.2 · 2026-06-07 갱신)

이 문서는 **기존 가이드와 v2 버전을 통합·중복 제거**해 정리한 최종본입니다.  
**1인 개발자**가 실제로 수집 가능하면서도 **선행 지표 가치**가 높은 출처만 선별했습니다.

> **현재 구현·API·스케줄 SSOT:**
> [`backend/domain/master/docs/economic/core/MASTER_BRONZE_IMPLEMENTATION_STATUS.md`](../domain/master/docs/economic/core/MASTER_BRONZE_IMPLEMENTATION_STATUS.md)
> **과거 제약·의사결정 기록:**
> [`backend/domain/master/docs/economic/core/ECONOMIC_DATA_SOURCE_STATUS.md`](../domain/master/docs/economic/core/ECONOMIC_DATA_SOURCE_STATUS.md)

---

## ERD 매핑 (원천 테이블)

| 테이블 | 역할 |
|--------|------|
| `raw_economic_data` | 자본·예산·투자 등 **돈의 흐름** |
| `raw_innovation_data` | 특허·논문·오픈소스·기술 콘텐츠 등 **혁신의 흐름** |
| `raw_people_data` | 검색·채용·수요 지표 등 **사람·역량 수요** |
| `raw_discourse_data` | 뉴스·커뮤니티·담론 등 **이슈·리스크** |
| `raw_opportunity_data` | 채용·부트캠프·공모전·지원사업 등 **기회** |

> 이 표는 목표 논리 모델이다. 현재 master 구현은 KIPRIS, Naver DataLab,
> 검색 수요 신호는 Naver DataLab을 통해 `raw_economic_data`에 적재한다.
> 실제 물리 적재 위치는 구현 현황 SSOT를 따른다.

---

## 1. 돈의 흐름 (Economic Flow) — "자본은 미래로 먼저 움직인다"

### 1-A. 기업·시장 자본 흐름

| 출처 | source_type | 수집 방법 | 스케줄 | 구현 | 비고 |
|------|------------|-----------|--------|------|------|
| **Wowtale RSS** | `WOWTALE_*` | RSS + 아카이브 크롤러 | 일별 | ✅ | `wowtale_collector.py` + `wowtale_archive_crawler.py` |
| **Platum RSS** | `PLATUM_*` | RSS | 일별 | ✅ | `platum_collector.py` |
| **벤처스퀘어 RSS** | `VSQUARE_*` | RSS | 일별 | ✅ | `venturesquare_collector.py` |
| **스타트업레시피 RSS** | `STARTUPRECIPE_*` | RSS | 일별 | ✅ | `startup_recipe_collector.py` — `investment_amount` 미추출 |
| **DART 주요사항보고(B)·지분공시(D)** | `DART_*` | Open API | 일별 | ✅ | `dart_collector.py` — M&A·증자·대량보유 |
| **DART 정기공시(A)** | `DART_PERIODIC_*` | Open API | 주별 | ✅ | `dart_periodic_collector.py` — 사업보고서 R&D/CAPEX |
| **DART 발행공시(C) — IPO** | `DART_IPO_DISCLOSURE` | Open API | 일별 | ✅ | `dart_ipo_collector.py` — 증권신고서(지분증권) 접수 → 상장 2~3개월 전 신호 |
| **국민연금공단 포트폴리오** | `NPS_PORTFOLIO_DART` | DART D-type | 일별 | ✅ | `nps_dart_collector.py` — 대량보유 변동 = 최대 기관투자자 움직임 |
| **Yahoo Finance ETF·주식 (Volume Surge)** | `YAHOO_ETF_*` `YAHOO_STOCK_KR_*` | yfinance | 주별 | ✅ | `yahoo_finance_collector.py` — 16종 거래량 급증일 |
| **Yahoo Finance (일별 OHLCV)** | `raw_market_timeseries` | yfinance | 일별 | ✅ | `yahoo_market_timeseries_collector.py` — 연속 시계열 |
| **Yahoo Macro (Price Surge)** | `YAHOO_FX_*` `YAHOO_RATE_*` 등 | yfinance | 주별 | ✅ | `yahoo_macro_collector.py` — FX·금리·원자재·BTC Z-score |
| **The VC** | — | — | — | ⏸️ Skip | ToS — RSS+DART 대체 |
| **네이버 금융 뉴스** | — | — | — | ⏸️ Skip | 상업적 이용·ToS 🔴 |
| **크런치베이스** | — | — | — | ⏸️ Skip | 유료 라이선스 |

### 1-B. 정부·공공 자금 흐름

| 출처 | source_type | 수집 방법 | 스케줄 | 구현 | 비고 |
|------|------------|-----------|--------|------|------|
| **한국은행 ECOS** | `BOK_ECOS_*` | Open API | 주별 | ✅ | `bok_ecos_collector.py` — FDI·통화량·기준금리 시계열 |
| **기획재정부 예산안·재정운용계획** | `GOVT_MOEF_*` | 수동 업로드 API | 수동 | ✅ | `moef_local_pdf_collector.py` |
| **과기부 mId=63 R&D 예산** | `GOVT_MSIT_RND` | HWPX 다운로드·파싱 | 일별 | ✅ | `msit_publicinfo_63_collector.py` |
| **과기부 mId=307 보도자료** | `GOVT_MSIT_PRESS` | BS4 증분 | 일별 | ✅ | `msit_bbs_collector.py` |
| **과기부 mId=311 사업공고** | `GOVT_MSIT_BIZ` | BS4 증분 | 일별 | ✅ | `msit_bbs_collector.py` |
| **식약처(MFDS) 보도자료** | `GOVT_MFDS_APPROVAL` | BS4 증분 | 일별 | ✅ | `mfds_bbs_collector.py` — 허가·임상 바이오 선행 신호 |
| **중소벤처기업부(MSS) 보도자료** | `GOVT_MSS_PRESS` | BS4 증분 | 일별 | ✅ | `mss_bbs_collector.py` |
| **ALIO 공공기관 사업정보** | `ALIO_*` | Open API | 주별 | ✅ | `alio_public_inst_project_collector.py` |
| **보조금24(Subsidy24)** | `GOVT_SUBSIDY24` | Open API | 일별 | ✅ | `subsidy24_collector.py` — 정부→민간 보조금 서비스 목록 |
| **NTIS (국가 R&D 통합)** | — | — | — | ⏸️ Held | 기관 소속·키 발급 필요 — MSIT·ALIO로 우회 |
| **한국벤처투자(KVIC)** | — | — | — | ❌ | 완전 SPA, JS 렌더링 필수 |
| **금융감독원 사모펀드 공시** | `FSS_PE_FUND_*` | 공시 크롤 | — | ❌ P1 | PE/VC 펀드 결성·운용 분기 보고 |

### 1-C. 정부 부처 보도자료 — 미구현 P0·P1

| 우선순위 | 부처 | source_type | 신호 가치 | 구현 |
|---------|------|------------|---------|------|
| P0 | 한국은행(BOK) | `GOVT_BOK_POLICY` | 금리·통화정책 선행 | ❌ |
| P0 | KOCCA / KHIDI | `GOVT_KOCCA_*` | K-콘텐츠·헬스케어 정책 | ❌ |
| P1 | 금융위(FSC) | `GOVT_FSC_POLICY` | 금융 규제 → 자본 시장 | ❌ |
| P1 | 산업통상자원부(MOTIE) | `GOVT_MOTIE_POLICY` | 제조·에너지 산업 정책 | ❌ |
| P1 | 환경부(ME) | `GOVT_ME_CARBON` | 탄소중립·녹색금융 | ❌ |

---

## 2. 혁신의 흐름 (Innovation Flow) — "기술적 가능성을 엿보다"

| 출처 | source_type | 수집 방법 | 스케줄 | 구현 | 비고 |
|------|------------|-----------|--------|------|------|
| **KIPRIS PLUS — 특허 출원 트렌드** | `PATENT_KIPRIS_TREND` | Open API (`ServiceKey`) | 주별 | ✅ | 논리 분류 Innovation, 현재는 `raw_economic_data` 적재 |
| **NTIS (국가 R&D 통합)** | `INNOVATION_NTIS_*` | Open API / RSS | — | ❌ P1 | 국가 R&D 과제·논문·특허 통합 |
| **arXiv (한국 저자 필터)** | `INNOVATION_ARXIV_*` | REST API | — | ❌ | AI·바이오 논문 추이 |
| **GitHub Trending (한국)** | `INNOVATION_GITHUB_*` | REST API | — | ❌ | Star 급증 오픈소스 탐지 |
| **기업 기술 블로그 RSS** | `INNOVATION_TECHBLOG_*` | RSS | — | ❌ | 네이버D2·카카오Tech·쏘카 등 |

> **KIPRIS API 핵심 파라미터**: 인증 파라미터명 `ServiceKey` (대소문자 정확히), 날짜 `applicationDate=YYYYMMDD~YYYYMMDD` (틸다 구분). IPC 코드 필터(`ipcCpc` 등)는 미동작 — `inventionTitle` 키워드 방식으로 대체.

---

## 3. 사람의 흐름 (Competency / Demand) — "대중의 관심과 학습 의지"

| 출처 | source_type | 수집 방법 | 스케줄 | 구현 | 비고 |
|------|------------|-----------|--------|------|------|
| **네이버 DataLab 검색량** | `DISCOURSE_NAVER_DATALAB` | Open API | 주별 | ✅ | 논리 분류 People/Demand, 현재는 `raw_economic_data` 적재 |
| **Google Trends (한국)** | `PEOPLE_GTRENDS_*` | PyTrends | — | ❌ | 글로벌 vs 한국 비교 |
| **원티드 채용 공고** | `PEOPLE_WANTED_*` | Playwright | — | ❌ P1 | IT/스타트업 기술 스택 수요 |
| **사람인 OpenAPI** | `PEOPLE_SARAMIN_*` | Open API | — | ❌ | 채용 공고 수량·요구 기술 |

> **DataLab vs 뉴스 기사 수 차이**: DataLab = 사용자 검색 **수요**(선행), 뉴스 기사 수 = 언론 **공급**(후행). 두 시계열을 Silver에서 교차하면 "검색 급증 → 뉴스 급증" 패턴 탐지 가능.
> **DataLab backfill**: `start_date` 파라미터로 최대 1년치 과거 수집 가능.

---

## 4. 담론의 흐름 (Discourse Flow) — "현재 이슈와 리스크"

| 출처 | 수집 방법 | 매핑 테이블 | 구현 | 비고 |
|------|-----------|-------------|------|------|
| Yonhap / JoongAng Daily RSS | feedparser | `raw_discourse_data` | ❌ | 공식 뉴스 |
| 나무위키 최근 변경 | GitHub Extractor / Playwright | `raw_discourse_data` | ❌ | 신조어·급부상 트렌드 빠름 (강력 추천) |
| Theqoo / 에펨코리아 | Playwright | `raw_discourse_data` | ❌ | 20~30대 실시간 반응 |
| YouTube Korea Trending | YouTube Data API v3 | `raw_discourse_data` | ❌ | 조회수·댓글 감성 |

> **§1 Economic과의 경계**: 부처 보도자료는 §1 Economic 보조축 단일 적재. 동일 URL을 §4에 중복 적재하지 않음.

---

## 5. 기회 / 지원 (`raw_opportunity_data`)

| 구분 | 출처 | 수집 방법 | 구현 | 비고 |
|------|------|-----------|------|------|
| **GRANT** | 중소벤처기업부 사업공고 | Open API | ✅ | `smes_collector.py` |
| **GRANT** | K-Startup 통합공고 | Open API | ❌ P0 | SMES 보완 |
| **GRANT** | 중기부 선정 결과 API | Open API | ❌ P1 | 선정 기업·금액 → Economic 교차 |
| **BOOTCAMP** | HRD-Net (K-Digital) | Open API | ❌ P1 | 국가 지원 부트캠프 |
| **JOB** | ALIO 공공기관 채용정보 | Open API | ❌ P1 | 공공기관 채용 공고 |
| **JOB** | 워크넷 정부지원일자리 | Open API | ❌ | 고용부 주관 |
| **JOB** | 원티드 | Playwright | ❌ P1 | IT/스타트업 채용 |
| **CONTEST** | 위비티(Wevity) | 스크래핑 | ❌ | 공모전·해커톤 최다 |
| **BID** | 조달청 나라장터(KONEPS) | Open API | ❌ P1 | 정부 입찰 공고 통합 — "정부 자본이 민간으로 흐르는" 거시 지표 |

---

## 6. 기업 마스터 (`verified_company_master`)

| 출처 | 수집 방법 | 구현 | 비고 |
|------|-----------|------|------|
| K-예비유니콘 선정 기업현황 | CSV 다운로드 | ❌ | 정부 선정 유망 스타트업 |
| 중소벤처기업부 벤처기업명단 | CSV 다운로드 | ❌ | 벤처인증 전체 명단 |
| ALIO 공공기관 기본정보 | Open API | ❌ | 기관 마스터 |

---

## 7. "돈의 흐름" 데이터 품질 종합 평가 (2026-06-07 기준)

### 7-1. 신호 선행성 타임라인

```
T-24개월  특허 출원 급증        KIPRIS ✅ → AI·바이오·에너지 R&D 투자 2~3년 전 신호
T-12개월  정부 예산안 발표       MOEF PDF ✅ · BOK 금리 변화 ✅
T-6개월   DART 사업보고서         R&D·CAPEX 계획 (dart_periodic) ✅
T-3개월   IPO 증권신고서 접수    DART IPO ✅ → 상장 기업·섹터 선행
T-6주     검색량 급증             Naver DataLab ✅ → 소비자 관심 폭발 직전
T-2주     NPS 포트폴리오 변동    NPS DART ✅ → 국민연금 매수/매도 방향
T-현재    Yahoo 거래량 급증       Yahoo Finance ✅ · Yahoo Macro ✅
T+수일    스타트업 투자 뉴스      Wowtale / Platum / Venturesquare ✅
```

### 7-2. 분야별 커버리지 평가

| 자금 흐름 분야 | 현황 | 점수 | 설명 |
|--------------|------|:----:|------|
| **정부→공공기관 예산 집행** | BOK ECOS + MOEF + MSIT + Subsidy24 + ALIO | **9/10** | 거의 완전 커버. FDI·통화량·기준금리·R&D예산·보조금 확보 |
| **기관투자자 동향** | NPS via DART D-type | **7/10** | 최대 기관투자자(국민연금) 추적 가능. 다른 연기금·공제회 미구현 |
| **IPO·자본 조달** | DART IPO (증권신고서) | **7/10** | 상장 선행 포착. KOSPI 상장 후 결과(KRX 직접)는 미구현 |
| **VC·스타트업 투자** | Wowtale + Platum + Venturesquare + StartupRecipe | **5/10** | 건수 파악 가능. 금액 정확도 낮음, 시리즈·섹터 해상도 제한 |
| **기술 혁신 R&D 투자** | KIPRIS 특허 + DART 정기공시 R&D | **6/10** | 주간 특허 출원 건수·사업보고서 R&D 금액 확보. NTIS 미구현 |
| **거시경제 지표** | BOK ECOS + Yahoo Macro (FX·금리·원자재) | **8/10** | 금리·환율·원자재 Z-score 확보. 세계 자금 흐름 연계 |
| **검색 수요** | Naver DataLab | **7/10** | 5개 핵심 경제 분야의 주간 검색 관심도 |
| **공개시장 자금 이동** | Yahoo Finance 16종 (ETF·주식 Volume Surge) | **7/10** | 거래량 급증 탐지. 한국 특화 종목 커버리지 제한 |
| **PE/사모펀드 자금** | 미구현 (FSS 사모펀드 공시 P1) | **2/10** | 중요 사각지대 — VC 펀드 결성·LP 자금 흐름 공백 |
| **부동산·건설 자금** | 미구현 | **1/10** | 서비스 타깃(청년 커리어)과 관련성 낮아 의도적 미구현 |

### 7-3. 전체 "돈의 흐름" 파악 수준

```
 ██████████████████░░  약 6.5~7 / 10
```

**현재의 강점:**
- 정부 자금 흐름 파이프라인(예산 발표 → 집행 → 보조금)이 잘 연결됨
- 공개 API 기반이라 안정적·법적 리스크 없음
- 선행~후행 다층 신호 확보 (특허→IPO→뉴스 순)

**주요 공백 (우선순위 순):**
1. **VC 펀드 결성 데이터** (KVIC SPA 접근 불가, FSS 사모펀드 공시 미구현) → 스타트업 투자 시장 전체 규모 파악 불가
2. **스타트업 투자 금액 정확도** (RSS 파싱 불완전) → 개별 라운드 금액 신뢰도 낮음
3. **나라장터(KONEPS) 입찰 공고** 미구현 → 정부 자본이 민간 산업으로 흘러가는 실시간 추적 불가
4. **글로벌→한국 FDI 세부 흐름** (KOTRA SPA 접근 불가) → BOK ECOS 집계치만 보유, 섹터별 FDI 파악 불가
5. **연기금·공제회 포트폴리오** (국민연금 외 교직원공제회·사학연금 등) 미구현

### 7-4. Silver 레이어에서 가능한 분석

현재 Bronze 데이터만으로 Silver에서 구현 가능한 분석:

| 분석 | 활용 소스 | 신뢰도 |
|------|----------|:------:|
| 섹터별 투자 모멘텀 점수 | Yahoo ETF + DART B + NPS + DataLab | ★★★★ |
| IPO 파이프라인 현황 | DART IPO C-type | ★★★★ |
| 정부 정책 → 민간 자금 선행 상관관계 | MSIT/MSS 보도 + DART B/A 시차 분석 | ★★★ |
| 기술 분야별 혁신 속도 | KIPRIS 특허 출원 증감율 | ★★★ |
| 검색 급증 → 뉴스 급증 → 투자 유입 패턴 | DataLab + Naver 뉴스 + RSS VC 뉴스 | ★★★ |
| 국민연금 섹터 로테이션 감지 | NPS DART 대량보유 변동 집계 | ★★★★ |
| 거시 금리 변화 → ETF 거래량 반응 | BOK ECOS 금리 + Yahoo Finance ETF | ★★★ |

---

## ALIO 3종 API 관계

| data.go.kr ID | 명칭 | 매핑 테이블 | 데이터 본질 |
|--------------|------|----------|------------|
| 15125273 | 공공기관 **채용정보** | `raw_opportunity_data` | 신청형 기회 |
| 15125286 | 공공기관 **사업정보** | `raw_economic_data` | 돈의 흐름 (정부 예산 집행) |
| 15125287 | 공공기관 **기본정보** | `verified_company_master` | 기관 마스터 |

---

## 관련 문서

- [`MASTER_BRONZE_IMPLEMENTATION_STATUS.md`](../domain/master/docs/economic/core/MASTER_BRONZE_IMPLEMENTATION_STATUS.md) — 현재 구현·API·스케줄 SSOT
- [`ECONOMIC_DATA_SOURCE_STATUS.md`](../domain/master/docs/economic/core/ECONOMIC_DATA_SOURCE_STATUS.md) — 과거 제약·우선순위 기록
- [`BRONZE_ARCHITECTURE_DECISION.md`](../domain/master/docs/economic/core/BRONZE_ARCHITECTURE_DECISION.md) — 6대 정량 소스·두 축 전략
- [`COLLECTOR_EXPANSION_REVIEW.md`](../domain/master/docs/economic/core/COLLECTOR_EXPANSION_REVIEW.md) — DART(A)·SMES 확장 검토
- [`GOVT_DOCS_COLLECTION_STRATEGY.md`](../domain/master/docs/economic/government/GOVT_DOCS_COLLECTION_STRATEGY.md) — 정부 문서 수집 전략
- [`erd.md`](erd.md) — 원천 테이블 DDL
