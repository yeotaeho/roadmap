# 한국 트렌드 분석 및 예측 엔진 — 데이터 수집 출처 가이드 (v3 · 통합본)

이 문서는 **기존 가이드와 v2 버전을 통합·중복 제거**해 정리한 최종본입니다.  
**1인 개발자**가 실제로 수집 가능하면서도 **선행 지표 가치**가 높은 출처만 선별했습니다.

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

| 출처 | URL | 수집 방법 | 매핑 테이블 | 비고 |
|------|-----|-----------|-------------|------|
| **The VC** | https://thevc.kr/browse/investments | BeautifulSoup + 페이지네이션 | `raw_economic_data` | 한국 VC 투자 최신 리스트 (가장 실용적) |
| **Wowtale** | https://wowtale.net/feed/ | RSS | `raw_economic_data` | **한국 스타트업 투자 뉴스 중 가장 빠른 업데이트** — **구현 완료** `wowtale_collector.py` |
| **스타트업레시피** | https://startuprecipe.co.kr/feed | RSS | `raw_economic_data` | `[AI서머리]` 묶음글 위주 (digest) — **구현 완료** `startup_recipe_collector.py` |
| **DART (전자공시시스템) OpenAPI** | https://opendart.fss.or.kr/ | 공식 Open API | `raw_economic_data` | 상장사 출자·R&D 투자 공시 (가장 선행적 지표) — **구현 완료** `dart_collector.py` |
| **Yahoo Finance (Volume Surge)** | https://finance.yahoo.com/quote/091220.KS/history | yfinance 라이브러리 | `raw_economic_data` | 한국 ETF 5 + 한국 대형주 5 + 글로벌 ETF 6 = **16종** 거래량 급증 — **구현 완료** `yahoo_finance_collector.py` |
| **Yahoo Macro (Price Surge)** | https://finance.yahoo.com/quote/USDKRW=X | yfinance 라이브러리 | `raw_economic_data` | 환율 3 + 미 국채금리 2 + 원자재 2 + 가상자산 1 = **8종** Z-score 이상치 — **구현 완료** `yahoo_macro_collector.py` |
| **기획재정부** | https://www.moef.go.kr/ | **수동 다운로드 + 파일 업로드 API** (연 1~2회) | `raw_economic_data` | 예산안 및 국가재정운용계획 — **반자동화 전략** (하이브리드) |
| **과기부 `mId=63` 예산/결산 (사전정보공표)** | https://www.msit.go.kr/publicinfo/detailList.do?sCode=user&mId=63&mPid=62&formMode=L&pageIndex=&publictSeqNo=295&searchSeCd=&searchMapngCd=&searchOpt=ALL&searchTxt=%EC%98%88%EC%82%B0 | **자동: 연도 상세 진입 → `ul.down_file` `.hwpx` POST 다운로드 → 비동기 파싱** (주 1회) | `raw_economic_data` (`GOVT_MSIT_RND`) | "20XX년 예산 및 기금운용계획 개요" 본문 |
| **과기부 `mId=307` 보도자료** | https://www.msit.go.kr/bbs/list.do?sCode=user&mPid=208&mId=307 | **BeautifulSoup 크롤링** (일 1회, 증분) — **2026 + 제목 "시행"** | `raw_economic_data` (`GOVT_MSIT_PRESS`) | 시행계획·종합시행계획 보도 본문 |
| **과기부 `mId=311` 사업공고** | https://www.msit.go.kr/bbs/list.do?sCode=user&mPid=121&mId=311 | **BeautifulSoup 크롤링** (일 1회, 증분) — **2026 + 제목 "모집"** | `raw_economic_data` (`GOVT_MSIT_BIZ`) | 모집공고·신규모집 본문·첨부 |
| **NTIS (국가 R&D 통합) OpenAPI** | https://www.ntis.go.kr/ | 공식 Open API | `raw_economic_data` + `raw_innovation_data` | **정부 R&D 집행 팩트의 단일 진실원**(전 부처·과제·기관·금액·분야 구조화 데이터)으로 **핵심 경제 원천**이며, **분야별·연도별 자본 배분의 정량·다년 시계열 지표**이자 **민간 투자 통계의 거시 벤치마크 분모** — **과기부 발표 신호의 후행 팩트체크**(교차 검증) |
| **공공기관 사업정보 조회 OpenAPI** | https://www.data.go.kr/data/15125286/openapi.do | 공식 Open API (REST/JSON+XML) | `raw_economic_data` | **ALIO 기반 공공기관이 운영하는 국가사업·공공서비스** — 정부 예산이 공공기관 통해 집행되는 사업 메타정보 (신청형 지원사업 ❌, 사업 운영 정보 ⭕) |

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
| **GRANT** | **중소벤처기업부 사업공고 Open API** | https://www.data.go.kr/data/15113297/openapi.do | 공식 Open API | 정부 지원사업 공고 (창업·R&D·수출·스케일업 등) — **구현 완료** `smes_collector.py` |
| **GRANT** | **K-Startup 통합공고 OpenAPI** | https://www.data.go.kr/data/15125364/openapi.do | 공식 Open API | **창업진흥원 지원사업 통합 (공고+선정결과 일부 포함)** — 우선 추천 |
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

- `backend/docs/erd.md` — 원천 테이블 DDL 및 도메인 정의
- `backend/docs/BACKEND_ARCHITECTURE_BLUEPRINT.md` — 백엔드 구조·역할 분리 참고
