# 한국 트렌드 분석 및 예측 엔진 — 데이터 수집 출처 가이드 (v3 · 통합본)

이 문서는 **기존 가이드와 v2 버전을 통합·중복 제거**해 정리한 최종본입니다.  
**1인 개발자**가 실제로 수집 가능하면서도 **선행 지표 가치**가 높은 출처만 선별했습니다.

> **구현·제약 현황 (2026-05-31 갱신):** NTIS / 네이버 금융 / The VC / Crunchbase 보류 사유, SMES·K-Startup·KVIC·P1 후보(보조금24·BOK ECOS·FSS) 연동 여부는  
> [`backend/domain/master/docs/ECONOMIC_DATA_SOURCE_STATUS.md`](../domain/master/docs/ECONOMIC_DATA_SOURCE_STATUS.md) 를 SSOT로 봅니다.  
> 정부 부처 보도자료 매핑 정책은 본 문서 **§1-2** 참조.

## ERD 매핑 (원천 테이블)

아래 출처는 `backend/docs/erd.md`에 정의된 원천 테이블에 적재하는 것을 전제로 합니다.

| 테이블 | 역할 |
|--------|------|
| `raw_economic_data` | 자본·예산·투자 등 **돈의 흐름** |
| `raw_innovation_data` | 특허·논문·오픈소스·기술 콘텐츠 등 **혁신의 흐름** |
| `raw_people_data` | 검색·채용·수요 지표 등 **사람·역량 수요** |
| `raw_discourse_data` | 뉴스·커뮤니티·담론 등 **이슈·리스크** |
| `raw_opportunity_data` | 채용·부트캠프·공모전·지원사업 등 **기회** (JOB / BOOTCAMP / CONTEST / GRANT) |

---

## 1. 돈의 흐름 (Economic Flow) — “자본은 미래로 먼저 움직인다”

한국 투자 동향과 정부 예산 흐름을 파악하는 핵심 카테고리입니다.

| 출처 | URL | 수집 방법 | 매핑 테이블 | 구현 | 비고 |
|------|-----|-----------|-------------|------|------|
| **The VC** | https://thevc.kr/browse/investments | BeautifulSoup + 페이지네이션 | `raw_economic_data` | ⏸️ Skip | 법·ToS — RSS+DART 대체 ([STATUS](../domain/master/docs/ECONOMIC_DATA_SOURCE_STATUS.md)) |
| **네이버 금융 뉴스** | https://finance.naver.com/news/ | 스크래핑 (M&A·투자 섹션) | `raw_economic_data` | ⏸️ Skip | **상업적 이용·ToS 🔴** — Wowtale·Platum·벤처스퀘어 RSS + DART 대체 ([STATUS](../domain/master/docs/ECONOMIC_DATA_SOURCE_STATUS.md) §2) |
| **Wowtale** | https://wowtale.net/feed/ | RSS | `raw_economic_data` | ✅ | `wowtale_collector.py` · 아카이브 `wowtale_archive_crawler.py` |
| **Platum** | https://platum.kr/archives/category/funding/feed | RSS | `raw_economic_data` | ✅ | `platum_collector.py` |
| **벤처스퀘어** | https://www.venturesquare.net/category/funding/feed | RSS | `raw_economic_data` | ✅ | `venturesquare_collector.py` |
| **스타트업레시피** | https://startuprecipe.co.kr/feed | RSS | `raw_economic_data` | ✅ | `startup_recipe_collector.py` — **`investment_amount` 미추출** |
| **DART — 주요사항보고(B)·지분공시(D)** | https://opendart.fss.or.kr/ | 공식 Open API | `raw_economic_data` | ✅ | `dart_collector.py` + `dart_detail_fetcher.py` — B(M&A·증자·시설투자 등) + **D(대량보유·의결권)** 병행 · `investment_amount` Phase 3 미완 ([DART 전략](../domain/master/docs/DART_ECONOMIC_ENHANCEMENT_STRATEGY.md)) |
| **DART — 정기공시(A)** | https://opendart.fss.or.kr/ | 공식 Open API (사업·분기·반기보고서) | `raw_economic_data` | ❌ P1 | **미구현** — R&D비·CAPEX·해외출자 등 **향후 3~5년 투자 계획** (B=결정된 투자 vs A=계획) · 별도 `DartRnDCollector` 검토 ([COLLECTOR_EXPANSION](../domain/master/docs/COLLECTOR_EXPANSION_REVIEW.md)) |
| **Yahoo Finance (Volume Surge)** | https://finance.yahoo.com/quote/091220.KS/history | yfinance | `raw_economic_data` | ✅ | 16종 급증일만 — `yahoo_finance_collector.py` |
| **Yahoo Finance (일별 OHLCV)** | (동일 16티커) | yfinance | **`raw_market_timeseries`** | ✅ | 연속 시계열 — `yahoo_market_timeseries_collector.py` |
| **Yahoo Macro (Price Surge)** | https://finance.yahoo.com/quote/USDKRW=X | yfinance | `raw_economic_data` | ✅ | 8종 Z-score — `yahoo_macro_collector.py` |
| **기획재정부** | https://www.moef.go.kr/ | **수동 업로드 API** | `raw_economic_data` | ✅ | `moef_local_pdf_collector.py` |
| **과기부 `mId=63` …** | (상동 URL) | HWPX 다운로드·파싱 | `raw_economic_data` | ✅ | `GOVT_MSIT_RND` |
| **과기부 `mId=307` 보도자료** | … | BS4 증분 | `raw_economic_data` | ✅ | `GOVT_MSIT_PRESS` |
| **과기부 `mId=311` 사업공고** | … | BS4 증분 | `raw_economic_data` | ✅ | `GOVT_MSIT_BIZ` |
| **NTIS (국가 R&D 통합) OpenAPI** | https://www.ntis.go.kr/ | 공식 Open API | `raw_economic_*` | ⏸️ Held | **기관 소속·키 발급** 필요 — MSIT·ALIO로 우회 ([STATUS](../domain/master/docs/ECONOMIC_DATA_SOURCE_STATUS.md)) |
| **ALIO 공공기관 사업정보** | https://www.data.go.kr/data/15125286/openapi.do | Open API | `raw_economic_data` | ✅ | `alio_public_inst_project_collector.py` — `investment_amount` 대부분 None |
| **한국벤처투자 (KVIC)** | https://www.kvic.or.kr/ | 보고서 PDF / **펀드현황 Open API**(정보공개) | `raw_economic_data` | ❌ | **쓸 가치 중간** (Economic **보조** P1) — VC 시장 **전체 규모·추세**; 개별 라운드·섹터 해상도 ❌ ([STATUS](../domain/master/docs/ECONOMIC_DATA_SOURCE_STATUS.md) §3.3·§3.4) |
| **크런치베이스 API** | https://www.crunchbase.com/ | 공식 API | `raw_economic_data` | ⏸️ Skip | 유료 라이선스 — RSS 3원 우선 |

### 1-1. Economic P1 후보 — 정량 거시 (미구현)

`BRONZE_ARCHITECTURE_DECISION.md` §6대 핵심 소스 중, **금액·지급주체·수혜자가 명시**되는 정량 Economic 축 후보입니다. NTIS·KONEPS·DART(상세)와 **같은 “돈의 흐름” 핵심축**이며, 구현 시 §1 본표로 승격합니다.

| 출처 | URL / API | 수집 방법 | 매핑 테이블 | 구현 | 비고 |
|------|-----------|-----------|-------------|------|------|
| **보조금24 통합조회** | https://www.gov24.go.kr/ (Open API) | 공식 Open API | `raw_economic_data` | ❌ P1 | 정부 → 기업/개인 **보조금 지급** · 전 산업 · 월 ~2,000건+ 예상 · `source_type` 예: `GOVT_SUBSIDY24_*` |
| **한국은행 ECOS API** | https://ecos.bok.or.kr/api/ | 공식 Open API | `raw_economic_data` | ❌ P1 | **거시 자금 흐름** — FDI·통화량·금리 시계열 · `investment_amount`는 None, 정량은 `raw_metadata` · `source_type` 예: `BOK_ECOS_*` |
| **금융감독원 사모펀드 공시** | https://dis.fss.or.kr/ | 전자공시 크롤/API | `raw_economic_data` | ❌ P1 | PE/VC **펀드 결성·운용** 분기 보고 · 민간→민간 자본 · `source_type` 예: `FSS_PE_FUND_*` · KVIC 거시 집계와 보완 |

**우선순위**: 보조금24 → BOK ECOS → FSS 사모펀드 (공공 API 우선, 크롤링은 FSS만 해당).

### 1-2. 정부 부처 보도자료 — Economic 보조축 (§4 Discourse 아님)

#### 매핑 정책 (2026-05-31)

| 질문 | 결정 |
|------|------|
| **§1 Economic vs §4 Discourse?** | **§1 Economic 보조축** — “돈이 흐르기 **전** 정책·산업 방향 신호” |
| **§4에 두지 않는 이유** | §4는 청년 커리어·이슈·커뮤니티 **담론**(나무위키·Theqoo·네이버 뉴스 OpenAPI 등). 부처 보도자료는 **정부 정책 선행 지표**로 Economic과 교차 분석 |
| **적재 테이블** | `raw_economic_data` (기본) — `investment_amount` 대부분 `None`, 본문·제목·`raw_metadata` 보존 |
| **Silver 활용** | MSIT/ALIO/KONEPS 등 **정량 소스와 시간 정렬** — “정책 발표 → 예산·입찰·집행” 파이프라인 검증 |
| **과기부 MSIT `mId=307`** | 이미 §1 본표 **`GOVT_MSIT_PRESS`** 로 Economic **정량 보조에 가깝게** 필터(연도+“시행”) 적용 — 일반 부처 보도자료 템플릿의 선행 사례 |

**22개 부처 전체 크롤링은 하지 않습니다.** ROI 대비 `BRONZE_ARCHITECTURE_DECISION.md` 기준 **핵심 7~8개만 P0/P1** 선별합니다.

| 우선순위 | 부처/기관 | URL (예) | `source_type` (안) | 신호 가치 | 구현 |
|----------|-----------|----------|----------------------|-----------|------|
| P0 | **한국은행 (BOK)** | bok.or.kr/portal/bbs/B0000220 | `GOVT_BOK_POLICY` | 금리·통화정책 → **선행 자금 흐름** | ❌ |
| P0 | **식약처 (MFDS)** | mfds.go.kr | `GOVT_MFDS_APPROVAL` | 신약·허가 → 바이오 자금 | ❌ |
| P0 | **KOCCA / KHIDI** | kocca.kr, khidi.or.kr | `GOVT_KOCCA_*`, `GOVT_KHIDI_*` | K-콘텐츠·헬스케어 정책 | ❌ |
| P1 | **금융위 (FSC)** | fsc.go.kr/no010101 | `GOVT_FSC_POLICY` | 금융 규제 → 자본 시장 | ❌ |
| P1 | **금융감독원 (FSS)** | fss.go.kr (보도자료) | `GOVT_FSS_PRESS` | 감독·공시 정책 (§1-1 사모펀드 공시와 별개) | ❌ |
| P1 | **산업통상자원부 (MOTIE)** | motie.go.kr | `GOVT_MOTIE_POLICY` | 제조·에너지 산업 정책 · 수동 PDF 업로드도 가능 ([GOVT_DOCS](../domain/master/docs/GOVT_DOCS_COLLECTION_STRATEGY.md)) | ❌ |
| P1 | **환경부 (ME)** | me.go.kr | `GOVT_ME_CARBON` | 탄소중립·녹색금융 · `GOVT_ME_PRESS` 보도자료 | ❌ |
| P1 | **보건복지부 (MOHW)** | mohw.go.kr | `GOVT_MOHW_PRESS` | 바이오·헬스 정책 | ❌ |
| P1 | **국토교통부 (MOLIT)** | molit.go.kr | `GOVT_MOLIT_PRESS` | SOC·부동산 정책 (시장 영향) | ❌ |
| P2 | **문화체육관광부·농림부·해수부·방사청 등** | 각 부처 게시판 | `GOVT_*_PRESS` | 산업별 보조 신호 | ❌ 보류 |

> **Discourse(§4)와의 경계**: 동일 기사 URL을 §4에 **중복 적재하지 않음**. 부처 보도는 Economic 보조축 단일 소스. 일반 경제 뉴스(연합·조선 등)는 §4 RSS 유지.

---

## 2. 혁신의 흐름 (Innovation Flow) — “기술적 가능성을 엿보다”

기술의 초기 움직임을 포착하는 카테고리입니다.

| 출처 | URL | 수집 방법 | 매핑 테이블 | 비고 |
|------|-----|-----------|-------------|------|
| **KIPRIS Plus Open API** | https://plus.kipris.or.kr/ | 공식 Open API (인증키 필요) | `raw_innovation_data` | 키워드별 특허 출원 추이 (핵심) |
| **NTIS (국가 R&D 통합)** | https://www.ntis.go.kr/ | Open API / RSS | `raw_innovation_data` | **국가 R&D 과제·논문·특허 통합** (강력 추천) |
| **arXiv (한국 저자 필터)** | https://export.arxiv.org/api/query | REST API | `raw_innovation_data` | AI·바이오 논문 추이 |
| **GitHub API** | https://api.github.com | REST API | `raw_innovation_data` | 한국 기여자·Star 수 추이 |
| **기업 기술 블로그** | 네이버 D2, 카카오 Tech, 쏘카 Tech 등 | RSS | `raw_innovation_data` | Top-tier 기업의 실제 기술 도입 트렌드 |
| **Velog / Tistory 트렌딩** | https://velog.io/ | RSS / 스크래핑 | `raw_innovation_data` | 개발자 학습 트렌드 (FastAPI, LangChain 등) |

---

## 3. 사람의 흐름 (Competency / Demand) — “대중의 관심과 학습 의지”

검색량, 채용, 학습 수요를 통해 수요를 파악합니다.

| 출처 | URL | 수집 방법 | 매핑 테이블 | 비고 |
|------|-----|-----------|-------------|------|
| **Naver DataLab** | https://datalab.naver.com/ | 웹 스크래핑 (CSV) | `raw_people_data` | 한국 검색량 추이 |
| **Google Trends (한국 필터)** | https://trends.google.com/ | PyTrends 라이브러리 | `raw_people_data` | 글로벌 vs 한국 비교 |
| **Wanted** | https://www.wanted.co.kr/ | **Playwright** + Network 탭 JSON | `raw_people_data` | IT/스타트업 채용 기술 스택 (강력 추천) |
| **사람인 OpenAPI** | https://www.saramin.co.kr/ | 공식 Open API | `raw_people_data` | 채용 공고 수량·기술 요구사항 |
| **JobPlanet** | https://www.jobplanet.co.kr/ | 스크래핑 | `raw_people_data` | 기업 리뷰·연봉·복지 (감성 분석) |
| **Blind (블라인드)** | https://www.teamblind.com/kr/ | **Playwright** (고난이도) | `raw_people_data` + `raw_discourse_data` | 직장인 실무 트렌드 (가장 생생) |

---

## 4. 담론의 흐름 (Discourse Flow) — “현재 이슈와 리스크”

커뮤니티와 뉴스를 통해 실시간 감성과 이슈를 파악합니다.

| 출처 | URL | 수집 방법 | 매핑 테이블 | 비고 |
|------|-----|-----------|-------------|------|
| **Yonhap News / Korea JoongAng Daily / Korea Herald** | 각 RSS | feedparser | `raw_discourse_data` | 공식 뉴스 |
| **나무위키 최근 변경 내역** | https://namu.wiki/ | GitHub Extractor 또는 Playwright | `raw_discourse_data` | **신조어·급부상 트렌드 가장 빠름** (강력 추천) |
| **Theqoo / 에펨코리아 / 디시인사이드** | 각 사이트 | **Playwright** | `raw_discourse_data` | 20~30대 실시간 반응 |
| **네이버 뉴스 OpenAPI** | https://openapi.naver.com/ | 공식 Open API | `raw_discourse_data` | 뉴스·블로그·카페 문서 발행량 |
| **YouTube Korea Trending** | YouTube Data API v3 | 공식 API | `raw_discourse_data` | 조회수·댓글 감성 분석 |

---

## 5. 기회 / 지원 (`raw_opportunity_data`) — 신규 전용 섹션

사용자에게 **직접 추천**할 채용·부트캠프·공모전·지원사업을 수집하는 테이블입니다.

| 구분 | 출처 | URL | 수집 방법 | 비고 |
|------|------|-----|-----------|------|
| **JOB** | Wanted | https://www.wanted.co.kr/ | Playwright + Network 탭 JSON | IT/스타트업 채용 표준 |
| **JOB** | 로켓펀치 | https://www.rocketpunch.com/ | BeautifulSoup | 초기 스타트업 채용 |
| **JOB** | 사람인 OpenAPI | data.go.kr 또는 사람인 개발자센터 | 공식 Open API | 채용 공고 수량·기술 요구사항 |
| **JOB** | **워크넷 정부지원일자리 OpenAPI** | https://www.data.go.kr/data/15058356/openapi.do | 공식 Open API | **정부 지원 일자리 공고** — 고용부 주관 |
| **JOB** | **재정경제부_공공기관 채용정보 OpenAPI** | https://www.data.go.kr/data/15125273/openapi.do | 공식 Open API (REST/JSON+XML) | **ALIO 기반 공공기관 채용 공고** — 직무명·지원기간·모집인원·선발단계·지원방법 |
| **BOOTCAMP** | **HRD-Net OpenAPI** | https://www.data.go.kr/data/15000000/openapi.do | 공식 Open API | **국가 지원 부트캠프 (K-Digital Training)** — 강력 추천 |
| **BOOTCAMP** | 부트텐트 / 링커리어 | https://www.boottent.com/ | 스크래핑 | 민간 부트캠프 모음 |
| **BOOTCAMP** | **워크넷 국민내일배움카드 훈련과정 OpenAPI** | https://openapi.work.go.kr/ | 공식 Open API | **국비 지원 훈련과정 (내일배움카드)** |
| **BOOTCAMP** | **워크넷 사업주훈련 훈련과정 OpenAPI** | https://openapi.work.go.kr/ | 공식 Open API | 기업 재직자 대상 직무 훈련 |
| **BOOTCAMP** | **워크넷 구직자취업역량 강화프로그램 OpenAPI** | https://openapi.work.go.kr/ | 공식 Open API | 구직자 대상 역량 강화 프로그램 |
| **BOOTCAMP** | **워크넷 국가인적자원개발 컨소시엄 훈련과정 OpenAPI** | https://openapi.work.go.kr/ | 공식 Open API | 중소기업 대상 훈련 지원 |
| **CONTEST** | 위비티 (Wevity) | https://www.wevity.com/ | 스크래핑 | 공모전·해커톤 최다 |
| **CONTEST** | 데브이벤트 (DevEvent) | https://github.com/DevEvent | GitHub `.md` / JSON 파싱 | 개발자 행사·해커톤 일정 |
| **GRANT** | **중소벤처기업부 사업공고 Open API** | https://www.data.go.kr/data/15113297/openapi.do | 공식 Open API | ✅ **`smes_collector.py`** → `raw_opportunity_data` · `SMES_SERVICE_KEY` · 일 스케줄 — **쓸 가치 높음** (Chance). Economic 직접 축 ❌ |
| **GRANT** | **중기부 지원사업 선정 결과 API** | data.go.kr (포털 검색: “중소벤처 선정”, “지원사업 선정 결과”) | 공식 Open API (추정 `getSelectionResult` 등) | ❌ P1 — **미구현** · 공고(`15113297`)와 `pblancId` JOIN · 선정 기업·금액 → Silver에서 Economic(RSS 투자) 교차 · ([COLLECTOR_EXPANSION](../domain/master/docs/COLLECTOR_EXPANSION_REVIEW.md) §SMES 확장 A) |
| **GRANT** | **중기부 지원금 집행(지급) 현황 API** | data.go.kr (포털 검색: “집행”, “지급 현황”) | 공식 Open API | ❌ P2 — **미구현** · 선정 ≠ 지급 완료 · `exctnAmt`·`exctnDt` → **정부 자본 실제 집행** 추적 · Economic 보조 (`raw_economic_data` 또는 Opportunity `raw_metadata` — Silver 설계 시 확정) · ([COLLECTOR_EXPANSION](../domain/master/docs/COLLECTOR_EXPANSION_REVIEW.md) §SMES 확장 B) |
| **GRANT** | **K-Startup 통합공고 OpenAPI** | https://www.data.go.kr/data/15125364/openapi.do | 공식 Open API | ❌ 미구현 — **쓸 가치 높음** (Opportunity P0, SMES 보완). Economic은 정책 방향 **보조**만 ([STATUS](../domain/master/docs/ECONOMIC_DATA_SOURCE_STATUS.md) §3.2·§3.4) |
| **GRANT** | **과학기술정보통신부 사업공고 OpenAPI** | https://www.data.go.kr/data/15074634/openapi.do | 공식 Open API | **과기부 R&D·기술 지원사업 공고** |
| **GRANT** | 기업마당 (Bizinfo) OpenAPI | https://www.bizinfo.go.kr/ | 공식 Open API | 중소벤처기업부 지원사업 종합 (개인 신청 제한) |
| **BID** | **조달청 나라장터(KONEPS) 입찰공고정보 OpenAPI** (`3073756`) | https://www.data.go.kr/data/3073756/openapi.do | 공식 Open API — 키워드·업종 화이트리스트 + 일 1회 증분 수집 (`watermark` = `published_at` + 공고번호) | **`raw_opportunity_data`(메인)**, **`raw_economic_data`(부)** — `raw_metadata`에 입찰 예산·낙찰가 등 정량값 보존. 정부·지자체·공공기관의 **모든 입찰·수주 공고 통합 SoT**; 스타트업·중소기업 사용자에게 **"돈을 벌 기회"** 핵심 신호이자 **정부 자본이 민간 산업으로 흘러가는** 거시 지표. 화이트리스트 키워드 예: AI, 데이터, 소프트웨어, ESG, R&D. |

---

### 5-1. 기업 마스터 데이터 (`verified_company_master`)

**정부 인증·선정 기업 명단** — 공고가 아닌 **기업 마스터 데이터**로 별도 테이블 적재

| 구분 | 출처 | URL | 수집 방법 | 갱신 주기 | 비고 |
|------|------|-----|-----------|---------|------|
| **VERIFIED** | **K-예비유니콘 선정 기업현황** | https://www.data.go.kr/data/15107549/fileData.do | CSV/XLSX 다운로드 | 연 1~2회 | **정부 선정 유망 스타트업** — 최고 신뢰도 |
| **VERIFIED** | **중소벤처기업부 벤처기업명단** | https://www.data.go.kr/data/15084581/fileData.do | CSV/XLSX 다운로드 | 매월 | **벤처기업 인증 전체 명단** — 사업자번호 포함 |
| **VERIFIED** | **공공기관 정보 조회 OpenAPI** | https://www.data.go.kr/data/15125287/openapi.do | 공식 Open API (REST/JSON+XML) | 상시 | **ALIO 기반 공공기관 기본 정보** — 기관명·유형·소재지·주요 사업 영역 (공공기관 마스터) |

---

### 5-2. 담론/우수사례 (`raw_discourse_data`)

**정성적 콘텐츠** — 지원사업 성공 사례, 정책 보고서 등

| 구분 | 출처 | URL | 수집 방법 | 비고 |
|------|------|-----|-----------|------|
| **REPORT** | **중소기업기술정보진흥원 지원사업 우수사례 현황** | https://www.data.go.kr/data/15129877/fileData.do | CSV/XLSX 다운로드 | 실제 지원받아 성공한 기업 우수사례 |
| **REPORT** | 워크넷 직업정보 OpenAPI | https://openapi.work.go.kr/ | 공식 Open API | 직업별 세부 정보 (연봉, 전망, 요구 역량) |
| **REPORT** | 워크넷 직무정보 OpenAPI | https://openapi.work.go.kr/ | 공식 Open API | 직무별 스킬셋 및 학습 경로 |

---

## 검토 후 보류한 소스

공공데이터포털 부처별 개별 R&D OpenAPI(`15094215`, `15106142`, `15104751`, `15104747`)는 **NTIS OpenAPI가 동일 데이터를 통합 스키마로 제공**하므로 도입하지 않습니다. 부처별 스키마 차이를 흡수하는 멀티 콜렉터를 추가해도 **중복 수집에 따른 이득이 없고** 운영 ROI만 커집니다. **R&D 과제·성과 데이터는 NTIS 단일 진입으로 통일**합니다. (향후 엔지니어의 재검토·중복 구현 방지용 기록)

---

## ALIO (공공기관 경영정보 공시시스템) 3종 API 묶음

ALIO(https://opendata.alio.go.kr/)는 **청년 일자리 올인원 지원 서비스** 일환으로 공공기관 데이터를 통합 제공합니다. 아래 3종은 같은 ALIO 데이터베이스를 다른 관점으로 노출한 API이므로 **한 묶음으로 함께 수집**하는 것이 효율적입니다. 단, 각각이 표현하는 데이터의 **본질이 달라** 매핑 테이블이 분리됩니다.

| ID | 명칭 | 매핑 테이블 | 데이터 본질 | 활용 시나리오 |
|----|------|----------|------------|------------|
| 15125273 | 공공기관 **채용정보** | `raw_opportunity_data` (JOB) | **신청형 기회** (사용자가 지원) | "공공기관 일자리" 추천 카드 |
| 15125286 | 공공기관 **사업정보** | `raw_economic_data` | **돈의 흐름** (정부 예산이 공공기관 통해 집행) | "기재부 예산 → 한국전력 신재생사업 1,200억 집행" 등 거시 흐름 추적 |
| 15125287 | 공공기관 **기본정보** | `verified_company_master` | **기관 마스터** | 위 2개 데이터의 `institution_id` ↔ 기관명 매핑 마스터 |

**왜 `15125286`이 GRANT가 아니라 Economic인가?**
- ALIO 기반 사업정보는 "**공공기관이 정부 예산을 받아 운영하는 사업**" 그 자체의 메타정보입니다.
- 사용자가 신청·접수해서 받을 수 있는 K-Startup·SMES 지원사업과는 **본질이 다릅니다** (사용자 액션 ❌, 조회만 ⭕).
- 이는 기재부 예산안(`GOVT_MOEF_BUDGET`)·과기부 R&D 예산과 같은 결의 **돈의 흐름** 데이터입니다.

**수집 순서 권장**:
1. `15125287` (기관 마스터) 먼저 수집 → `verified_company_master`에 적재
2. `15125273` (채용), `15125286` (사업) 수집 시 `institution_id` 외래키처럼 활용
3. 모두 동일한 인증키 1개로 호출 가능 (REST · JSON+XML, 개발용 1,000건/일 무료)

---

## 1인 개발자를 위한 수집 전략 (필수 적용 추천)

1. **API First 전략**  
   공공데이터포털(data.go.kr), KIPRIS, HRD-Net, K-Startup, 사람인 OpenAPI 등 **공식 JSON/XML**을 최우선으로 사용합니다.

2. **동적 사이트 크롤링**  
   Wanted, Blind, Theqoo 등 React 기반 사이트는 **Playwright**를 강력 추천합니다. (Selenium 대비 속도·안정성)

3. **스케줄러 분리**  
   수집 파이프라인은 FastAPI 메인 서버와 **완전히 분리**하고, Celery + Redis 또는 APScheduler로 **새벽 배치** 실행을 권장합니다.

4. **강력 추천 조합 (MVP 최소 세트)**  
   **Wowtale + HRD-Net + 나무위키 + KIPRIS + Wanted**  
   → 이 5개만 잘 연동해도 한국 트렌드의 약 **70~80%**를 커버할 수 있습니다.

---

## 다음 단계

**Data Collector 노드** 구현 시, 출처별로 다음을 분리하는 것을 권장합니다.

- 공통: HTTP 클라이언트, Rate limit, 재시도, 정규화 → `raw_*` 적재 전 어댑터
- 배치: 스케줄·실패 알림·데이터 품질 검증

특정 출처(예: HRD-Net OpenAPI, 나무위키, Wanted Playwright, KIPRIS 등)에 대한 **구체적인 Python 수집 코드**가 필요하면 해당 출처부터 우선순위를 정해 모듈 단위로 추가하면 됩니다.

---

## 관련 문서

- `backend/domain/master/docs/ECONOMIC_DATA_SOURCE_STATUS.md` — **제약·SMES/K-Startup/KVIC·구현 현황**
- `backend/domain/master/docs/BRONZE_ARCHITECTURE_DECISION.md` — 6대 정량 소스·부처 보도자료 매트릭스·두 축 전략
- `backend/domain/master/docs/COLLECTOR_EXPANSION_REVIEW.md` — DART(A)·SMES 선정/집행 API 확장 검토
- `backend/domain/master/docs/GOVT_DOCS_COLLECTION_STRATEGY.md` — MOEF·MSIT·MOTIE·ME 정부 문서 수집
- `backend/docs/erd.md` — 원천 테이블 DDL 및 도메인 정의
- `backend/docs/BACKEND_ARCHITECTURE_BLUEPRINT.md` — 백엔드 구조·역할 분리 참고
