# raw_economic_data 수집 가이드 (경제 도메인 - 자본 흐름)

## 문서 목적

`raw_economic_data` 테이블은 **한국 시장의 자본 흐름**을 추적하는 Bronze Layer의 핵심 테이블입니다.  
이 문서는 6개 출처의 **실제 웹 구조·API 특성·크롤링 난이도·구현 우선순위**를 실무 기준으로 정리합니다.

---

## 테이블 구조 (참조: `backend/docs/erd.md`)

```sql
CREATE TABLE raw_economic_data (
    id BIGSERIAL PRIMARY KEY,
    source_type VARCHAR(50) NOT NULL,        -- DART, THEVC, WOWTALE 등
    source_url VARCHAR(255),                  -- 원문/출처 URL
    target_company_or_fund VARCHAR(100),      -- 투자 대상 기업/펀드
    investment_amount BIGINT,                 -- 투자/유입 금액 (원)
    collected_at TIMESTAMPTZ DEFAULT now()    -- 수집 시각
);
```

---

## 수집 출처 6개 - 구현 현황

### 구현 순서 및 상태

| 순서 | 출처 | 상태 | 비고 |
|------|------|------|------|
| 1 | DART | ✅ 완료 | `dart_collector.py` |
| 2 | Wowtale | ✅ 완료 | `wowtale_collector.py` |
| 3 | **스타트업레시피 (Startup Recipe)** | ✅ **완료** | `startup_recipe_collector.py` — RSS / `[AI서머리]` 묶음글 전용 처리 |
| 4 | **Yahoo Finance (Volume Surge)** | ✅ **완료** | `yahoo_finance_collector.py` — 16종(한국 ETF 5 + 한국 대형주 5 + 글로벌 ETF 6) × VWAP 근사 |
| 4-B | **Yahoo Macro (Price Surge)** | ✅ **완료** | `yahoo_macro_collector.py` — 8종(FX 3 + 금리 2 + 원자재 2 + 가상자산 1) × Z-score |
| 5 | The VC | 📋 예정 | Playwright 동적 크롤링 |
| 6 | 정부문서 | 📋 예정 | PDF/HWP 파싱 |

> 참고: 중소벤처기업부 사업공고 OpenAPI 는 사용자 행동 가치(직접 추천·알림)가 더 크다고 판단되어
> `raw_opportunity_data` 로 분류 이관되었습니다 (`smes_collector.py` 구현 완료).
> 자세한 사유는 `DATA_COLLECTION_SOURCES_GUIDE_V3.md` § 5 (기회 / 지원) 참조.

---

### 🏛️ 그룹 1: 공식 Open API (최우선 구현 - 가장 안정적)

웹 구조 변경(CSS/XPath)에 영향을 받지 않으므로 **가장 먼저 구현**해야 할 핵심 소스입니다.

---

#### 1. DART (전자공시시스템) OpenAPI ✅ 구현 완료

**URL**: https://opendart.fss.or.kr/

**구현 파일**: `backend/domain/master/hub/services/collectors/economic/dart_collector.py`

**구조 파악**:
- 완벽하게 정형화된 JSON/XML 형태의 REST API 제공
- 상장사의 공시 사항을 실시간으로 구조화된 데이터로 제공

**구현 상세**: `backend/domain/master/docs/DART_ECONOMIC_ENHANCEMENT_STRATEGY.md` 참조

**수집 전략**:

**옵션 A (권장): `dart-fss` 라이브러리 사용**
```python
# requirements.txt
dart-fss>=0.3.0

# collectors/economic/dart_collector.py
import dart_fss as dart
from datetime import datetime, timedelta

class DartCollector:
    def __init__(self, api_key: str):
        dart.set_api_key(api_key)
    
    async def collect(self) -> List[EconomicCollectDto]:
        """타법인 주식 및 출자증권 취득결정 공시 수집"""
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y%m%d')
        
        # 주요사항보고서 중 투자 관련 공시만 필터링
        corp_list = dart.get_corp_list()
        
        dtos = []
        for corp in corp_list:
            reports = corp.search_report(
                bgn_de=yesterday,
                pblntf_ty='C001'  # 타법인 주식 취득 공시
            )
            
            for report in reports:
                dtos.append(EconomicCollectDto(
                    source_type="DART_INVESTMENT",
                    source_url=f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={report.rcp_no}",
                    target_company_or_fund=report.corp_name,
                    investment_amount=self._parse_amount(report),  # XML에서 추출
                ))
        
        return dtos
```

**옵션 B: 직접 REST API 호출**
```python
async def collect_direct_api(self):
    """DART OpenAPI 직접 호출"""
    async with aiohttp.ClientSession() as session:
        params = {
            "crtfc_key": self.api_key,
            "bgn_de": "20260101",
            "pblntf_ty": "C001",  # 타법인 주식 취득
        }
        async with session.get(
            "https://opendart.fss.or.kr/api/list.json",
            params=params
        ) as resp:
            data = await resp.json()
            # ... 파싱 로직
```

**타겟 데이터**:
- '주요사항보고서(타법인 주식 및 출자증권 취득결정)' 공시
- 대기업이 어떤 스타트업·기술에 투자했는지 정확한 금액과 함께 수집

**주의점**:
- ⚠️ **일일 호출 한도: 10,000회**
- `bronze_scheduler.py`에서 **하루 1번 새벽**에 전일자 공시만 수집
- 응답이 XML인 경우 `xmltodict` 사용

**난이도**: ⭐ (가장 쉬움)

---

#### 2. 중소벤처기업부 사업공고 Open API

**URL**: https://www.data.go.kr/data/15113297/openapi.do

**구조 파악**:
- 공공데이터포털을 통한 REST API
- JSON보다 **XML 응답이 기본**인 경우가 많음

**수집 전략**:

```python
import aiohttp
import xmltodict

class SmesOpenAPICollector:
    BASE_URL = "http://apis.data.go.kr/..."
    
    def __init__(self, service_key: str):
        self.service_key = service_key
    
    async def collect(self) -> List[EconomicCollectDto]:
        """중소벤처기업부 지원사업 공고 수집"""
        async with aiohttp.ClientSession() as session:
            params = {
                "serviceKey": self.service_key,
                "numOfRows": "100",
                "pageNo": "1",
            }
            
            async with session.get(self.BASE_URL, params=params) as resp:
                xml_text = await resp.text()
                data = xmltodict.parse(xml_text)
                
                items = data['response']['body']['items']['item']
                if not isinstance(items, list):
                    items = [items]
                
                dtos = []
                for item in items:
                    dtos.append(EconomicCollectDto(
                        source_type="SMES_GRANT",
                        source_url=item.get('url', ''),
                        target_company_or_fund=item.get('pblancNm', ''),  # 공고명
                        investment_amount=self._parse_budget(item.get('budget')),
                    ))
                
                return dtos
    
    def _parse_budget(self, text: str) -> int | None:
        """'1,000백만원' → 1000000000"""
        if not text:
            return None
        # 정규식으로 숫자 추출
        import re
        match = re.search(r'([\d,]+)', text)
        if match:
            number = int(match.group(1).replace(',', ''))
            if '백만' in text:
                return number * 1_000_000
            elif '억' in text:
                return number * 100_000_000
        return None
```

**주의점**:
- ⚠️ **공공 API는 서버 불안정**: Timeout 자주 발생
- `http_client.py`에 **Tenacity 라이브러리 활용 Retry 로직** 필수

```python
# spokes/infra/http_client.py
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10)
)
async def fetch_with_retry(url: str, params: dict):
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params, timeout=30) as resp:
            return await resp.json()
```

**난이도**: ⭐⭐ (XML 파싱 필요)

---

### 📰 그룹 2: RSS 피드 (가성비 최고)

복잡한 스크래핑 로직 없이 실시간 뉴스를 가져올 수 있는 최고의 수단입니다.

---

#### 3. 와우테일 (Wowtale) ✅ 구현 완료

**URL**: https://wowtale.net/feed

**구현 파일**: `backend/domain/master/hub/services/collectors/economic/wowtale_collector.py`

**구조 파악**:
- **워드프레스(WordPress) 기반** 스타트업 투자 뉴스 전문 미디어
- 표준 **RSS 2.0 피드** 완벽 지원
- 하루 3~10건의 투자 뉴스 실시간 업데이트

**구현 상세**: `backend/domain/master/docs/WOWTALE_RSS_COLLECTION_GUIDE.md` 참조

**수집 전략**:

```python
import feedparser
from datetime import datetime
from bs4 import BeautifulSoup
import aiohttp

class WowtaleCollector:
    FEED_URL = "https://wowtale.net/feed"
    
    async def collect(self) -> List[EconomicCollectDto]:
        """RSS 피드 + 본문 스크래핑 2-Step"""
        feed = feedparser.parse(self.FEED_URL)
        
        dtos = []
        for entry in feed.entries:
            # Step 1: RSS에서 기본 정보 추출
            title = entry.title
            link = entry.link
            summary = entry.summary
            published = datetime(*entry.published_parsed[:6])
            
            # Step 2: 본문 전문이 필요하면 링크 타고 들어가기
            if '투자' in title or '펀딩' in title:
                full_text = await self._fetch_full_content(link)
                investment_info = self._extract_investment_info(full_text)
                
                dtos.append(EconomicCollectDto(
                    source_type="WOWTALE",
                    source_url=link,
                    target_company_or_fund=investment_info['company'],
                    investment_amount=investment_info['amount'],
                ))
        
        return dtos
    
    async def _fetch_full_content(self, url: str) -> str:
        """RSS 링크 → 본문 전문 스크래핑"""
        async with aiohttp.ClientSession() as session:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            async with session.get(url, headers=headers) as resp:
                html = await resp.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                # 워드프레스 기본 본문 클래스
                content = soup.find('div', class_='entry-content')
                return content.get_text() if content else ""
    
    def _extract_investment_info(self, text: str) -> dict:
        """본문에서 '○○, 시리즈A 100억원 투자 유치' 파싱"""
        import re
        
        # 정규식으로 회사명 + 금액 추출
        pattern = r'([가-힣a-zA-Z0-9]+),?\s*(?:시리즈\s?[A-Z])?\s*([\d,]+)\s*억'
        match = re.search(pattern, text)
        
        if match:
            return {
                'company': match.group(1),
                'amount': int(match.group(2).replace(',', '')) * 100_000_000
            }
        return {'company': None, 'amount': None}
```

**RSS vs 본문 스크래핑 선택 기준**:

| 필요 데이터 | 전략 | 이유 |
|-------------|------|------|
| 제목·링크·발행일만 | RSS만 | 빠르고 안정적 |
| 투자 금액·상세 내용 | RSS + 본문 2-Step | RSS 요약은 불완전 |

**주의점**:
- RSS 피드는 최신 10-20개 항목만 제공 → **매일 수집** 권장
- 본문 스크래핑 시 **User-Agent 헤더** 필수 (봇 차단 우회)

**난이도**: ⭐ (RSS만) / ⭐⭐ (본문 2-Step)

---

### 🕸️ 그룹 3: 동적 웹페이지 (난이도 높음)

가장 유용하지만 수집하기 가장 까다로운 곳입니다.

---

#### 4. The VC (더브이씨)

**URL**: https://thevc.kr/browse/investments

**구조 파악**:
- 표면상으로는 일반 웹사이트처럼 보이지만, 내부적으로는 **React/Vue 같은 SPA (Single Page Application)**
- `requests` + `BeautifulSoup`로 HTML을 긁으면 **빈 화면만 보임**

**크롤링 전략 (2가지 중 택 1)**:

**전략 A (숨은 API 찾기 - 강력 추천)**:

```python
# 1. 크롬 개발자 도구(F12) → Network 탭 → Fetch/XHR 필터
# 2. 페이지 넘기면서 실제 데이터 가져오는 API 찾기
# 예: https://api.thevc.kr/investments?page=1&limit=20

class TheVCCollector:
    API_URL = "https://api.thevc.kr/investments"  # 실제 API (예시)
    
    async def collect(self) -> List[EconomicCollectDto]:
        """숨은 백엔드 API 직접 호출 (HTML 파싱 불필요)"""
        async with aiohttp.ClientSession() as session:
            headers = {
                "User-Agent": "Mozilla/5.0...",
                "Referer": "https://thevc.kr/",  # 필수
            }
            
            dtos = []
            for page in range(1, 6):  # 최근 5페이지만
                params = {"page": page, "limit": 20}
                async with session.get(
                    self.API_URL,
                    params=params,
                    headers=headers
                ) as resp:
                    data = await resp.json()
                    
                    for item in data['investments']:
                        dtos.append(EconomicCollectDto(
                            source_type="THEVC",
                            source_url=f"https://thevc.kr/investments/{item['id']}",
                            target_company_or_fund=item['company_name'],
                            investment_amount=item['amount'],
                        ))
            
            return dtos
```

**전략 B (Playwright 활용)**:

숨은 API에 인증 토큰이 빡빡하거나 찾기 어려우면 `playwright_pool.py` 사용

```python
from domain.master.spokes.infra.playwright_pool import PlaywrightPool
from domain.master.spokes.infra.selector_fallback import extract_with_fallback

class TheVCPlaywrightCollector:
    URL = "https://thevc.kr/browse/investments"
    
    SELECTORS = {
        "company": [
            "h3.investment-title",
            "div.card-title",
            "span[data-field='company']"
        ],
        "amount": [
            "span.amount-krw",
            "div.investment-amount"
        ]
    }
    
    async def collect(self) -> List[EconomicCollectDto]:
        """Playwright로 렌더링 후 HTML 파싱"""
        context = await PlaywrightPool.get_context()
        page = await context.new_page()
        
        await page.goto(self.URL)
        await page.wait_for_selector('div.investment-card')  # 로딩 대기
        
        # Selector Fallback 체인 활용
        companies = extract_with_fallback(page, self.SELECTORS["company"])
        amounts = extract_with_fallback(page, self.SELECTORS["amount"])
        
        if not companies:
            raise CollectionError("The VC: 모든 셀렉터 실패")
        
        dtos = []
        for company, amount in zip(companies, amounts):
            dtos.append(EconomicCollectDto(
                source_type="THEVC",
                source_url=self.URL,
                target_company_or_fund=company,
                investment_amount=self._parse_amount(amount),
            ))
        
        await page.close()
        return dtos
```

**난이도**: ⭐⭐⭐⭐ (전략 A) / ⭐⭐⭐⭐⭐ (전략 B)

---

### 📊 그룹 4: 외부 특화 라이브러리

---

#### 5. Yahoo Finance (Volume Surge — 16종) ✅ 구현 완료

**URL**: https://finance.yahoo.com/quote/091220.KS/history

**구현 파일**: `backend/domain/master/hub/services/collectors/economic/yahoo_finance_collector.py`

**전략 검토 문서**:
- 초안: `backend/domain/master/docs/YAHOO_FINANCE_ETF_COLLECTION_GUIDE.md`
- 리뷰/A안 조정: `backend/domain/master/docs/YAHOO_FINANCE_ETF_STRATEGY_REVIEW.md`
- 확장 검토(Option B): `backend/domain/master/docs/YAHOO_FINANCE_EXPANSION_REVIEW.md`

**Option B 확장 (2026-05-12)** — 거래량 시계열 적용 범위가 16종으로 확장:

| 그룹 | 종목 수 | source_type prefix | 핵심 가치 |
|------|--------|--------------------|----------|
| 한국 테마 ETF | 5 | `YAHOO_ETF_*` | 테마별 자본 유입 |
| **한국 대형주 (신규)** | 5 | `YAHOO_STOCK_KR_*` | 삼성전자/SK하이닉스/LG에너지솔루션/삼성바이오/NAVER의 **직접 신호** |
| **글로벌 ETF (신규)** | 6 | `YAHOO_GLOBAL_*` | SPY/QQQ/SMH/ARKK/LIT/XLE — **한국 시장 6~12시간 선행 지표** |

**운영 보강**:
- NaN 후행 행 안전 처리 (yfinance가 한국 시장 마감 전 NaN을 줄 수 있음)
- 티커 간 `time.sleep(0.5s)` IP 차단 방어 (16종 × 0.5s ≒ 8초)
- DTO `currency` 필드로 자산별 통화(KRW/USD) 정확히 기록

**A안에서 확정된 핵심 차별점 (구현 시 반영됨)**:

1. **티커 리스트 재편** — 신호 품질 우선
   - ❌ 블록체인 (투기성), ❌ 중국 바이오 (한국 시장과 무관),
     ❌ 메타버스 (유동성 저하) **모두 제외**
   - ✅ TIGER AI(`091220.KS`) / KODEX 2차전지(`441680.KS`) /
     KODEX 바이오(`244620.KS`) / KODEX K-신재생(`261140.KS`) /
     TIGER K-푸드(`332620.KS`)

2. **멀티 레벨 임계값** — ETF별 변동성 차이 흡수
   - 거래량 풍부한 ETF (AI / 2차전지): **2.0배**
   - 변동성 큰 ETF (바이오 / 신재생): **2.5배**
   - 중간 (K-푸드): **2.2배**

3. **VWAP 근사 계산** — `volume × close` → `volume × (high+low+close)/3`
   - 종가만 쓸 때보다 일중 유입 추정 오차 절반 감소
   - 구현은 한 줄 (HLCC/3)

**핵심 알고리즘 요약**:

```python
# domain/master/hub/services/collectors/economic/yahoo_finance_collector.py
ETF_TARGETS = (
    EtfTarget("091220.KS", "TIGER 글로벌AI액티브",  "AI/반도체",       "YAHOO_ETF_AI",        2.0),
    EtfTarget("441680.KS", "KODEX 2차전지산업",      "2차전지/배터리",  "YAHOO_ETF_BATTERY",   2.0),
    EtfTarget("244620.KS", "KODEX 바이오",            "한국 바이오/제약", "YAHOO_ETF_BIO",       2.5),
    EtfTarget("261140.KS", "KODEX K-신재생에너지",    "재생에너지",       "YAHOO_ETF_RENEWABLE", 2.5),
    EtfTarget("332620.KS", "TIGER K-푸드",             "K-푸드/농식품",   "YAHOO_ETF_KFOOD",     2.2),
)

# 마지막 거래일의 거래량이 (이전 20일 평균 × threshold) 이상이면 Bronze 적재
ratio = last_volume / avg_volume_20d
if ratio >= target.threshold:
    vwap = (high + low + close) / 3   # HLCC/3 근사
    inflow_amount_krw = int(round(last_volume * vwap))
    # → EconomicCollectDto 생성 (source_type=YAHOO_ETF_*, currency='KRW')
```

**저장 스키마 매핑**:

| 필드 | 값 |
|------|-----|
| `source_type` | `YAHOO_ETF_AI` / `_BATTERY` / `_BIO` / `_RENEWABLE` / `_KFOOD` |
| `source_url`  | `https://finance.yahoo.com/quote/<ticker>/history?period1=YYYY-MM-DD` (티커+거래일 유일) |
| `raw_title`   | "TIGER 글로벌AI액티브(091220.KS) 거래량 2.34배 급증 (2026-05-11, 추정 유입액 1,050억원)" |
| `investor_name` | `None` (ETF는 다수 익명 투자자) |
| `target_company_or_fund` | ETF 이름 |
| `investment_amount` | `volume × VWAP(HLCC/3)` (원 단위) |
| `currency` | `KRW` |
| `published_at` | 마지막 거래일 KST 자정 |
| `raw_metadata` | `ticker / theme / volume / avg_volume_20d / volume_ratio / threshold / ohlc / vwap_approx / inflow_amount_krw / calculation_method` |

**실패 격리**:
- 일부 티커의 `yfinance` 다운로드 실패는 `logger.exception`으로 흡수
- 다른 티커는 정상 진행 (파이프라인 전체 중단 없음)
- Service 계층에서도 `try-except` 로 collector 예외를 한 번 더 감싼다

**주의점**:
- `yfinance`는 비공식 라이브러리 → Yahoo 구조 변경 시 깨질 수 있음 (Phase 2: 네이버 금융 Fallback 검토)
- **너무 자주 호출하면 IP 차단** → 하루 1회 새벽 배치 권장
- 신규 거래일이 만들어지지 않은 휴장일에는 신호 0건이 정상

**API 엔드포인트**: `POST /api/master/bronze/economic/yahoo-finance`

**통합 테스트**: `backend/scripts/yahoo_finance_integration_test.py`

**난이도**: ⭐⭐ (라이브러리 의존)

---

#### 5-B. Yahoo Macro (Price Surge — 거시 지표 Z-score) ✅ 구현 완료

**구현 파일**: `backend/domain/master/hub/services/collectors/economic/yahoo_macro_collector.py`

**왜 별도 Collector인가?**
- 환율(`USDKRW=X`), 미 국채 금리(`^TNX`), 원자재(`GC=F`) 등은 **거래량 개념이 무의미** (실측: `Volume=0`).
- 따라서 "거래량 급증"이 아닌 **"가격 변동률의 통계적 이상치(Z-score)"** 가 자본 흐름 변화의 신호.

**알고리즘**:
```
r_t  = (close_t / close_{t-1}) - 1            (일간 수익률)
σ_20 = std(r over previous 20 trading days)   (마지막 행 제외)
Z    = |r_t| / σ_20
Z >= threshold → Bronze 적재
```

**대상 자산 (8종)**:

| 카테고리 | 티커 | source_type | Z 임계값 | 핵심 가치 |
|---------|------|------------|---------|----------|
| FX | `USDKRW=X` | `YAHOO_FX_USDKRW` | 2.0 | 외국인 자본 유출입 핵심 신호 |
| FX | `EURKRW=X` | `YAHOO_FX_EURKRW` | 2.0 | 유럽 자본 흐름 |
| FX | `JPYKRW=X` | `YAHOO_FX_JPYKRW` | 2.0 | 일본 자본 흐름 |
| RATE | `^TNX` (10Y) | `YAHOO_RATE_US10Y` | 2.0 | 글로벌 무위험 수익률 |
| RATE | `^IRX` (13W) | `YAHOO_RATE_US3M` | 2.0 | 단기 유동성 |
| COMMODITY | `GC=F` | `YAHOO_COMMODITY_GOLD` | 2.0 | 안전자산 |
| COMMODITY | `CL=F` | `YAHOO_COMMODITY_OIL` | 2.0 | 산업 비용 / 인플레 |
| CRYPTO | `BTC-USD` | `YAHOO_COMMODITY_BTC` | 2.5 | 위험자산 극단 (변동성↑) |

**저장 스키마 매핑**:

| 필드 | 값 |
|------|-----|
| `source_type` | `YAHOO_FX_*` / `YAHOO_RATE_*` / `YAHOO_COMMODITY_*` |
| `source_url` | `https://finance.yahoo.com/quote/<ticker>/history?period1=YYYY-MM-DD` |
| `raw_title` | "원/달러 환율(USDKRW=X) 급등 +1.32% (Z=2.31, 2026-05-11, 종가 1,470원/USD)" |
| `target_company_or_fund` | 자산 표시명 (예: "원/달러 환율") |
| `investment_amount` | **`None`** (가격 변동은 흐름량 직접 측정 불가) |
| `currency` | `KRW` / `USD` / `PCT` (금리) |
| `published_at` | 마지막 거래일 KST |
| `raw_metadata` | `ticker / category / unit / close / prev_close / daily_return(_pct) / std_20d / z_score / threshold / direction / calculation_method` |

**API 엔드포인트**: `POST /api/master/bronze/economic/yahoo-macro`

**통합 테스트**: `backend/scripts/yahoo_macro_integration_test.py`

**실측 결과 (2026-05-12 첫 실행)**:
> EURKRW 일간 +1.56% 급등, Z=2.58 (평소 σ=0.6% 대비 통계적 이상치). 외국인 자본의 한국 시장
> 흐름 변화 신호로 해석 가능.

**난이도**: ⭐⭐ (yfinance 의존 + 통계 알고리즘)

---

### 📑 그룹 5: 비정형 정부 문서 (최고 난이도)

가장 선행적인 거시경제 지표지만 데이터화가 어렵습니다.

---

#### 6. 기획재정부 & 과학기술정보통신부

**URL**:
- 기획재정부: https://www.moef.go.kr/
- 과학기술정보통신부: https://www.msit.go.kr/

**구조 파악**:
- 웹페이지에는 글이 없고, 주로 **PDF나 HWP(한글) 파일 첨부** 형태로 예산안 업로드
- 정형화된 필드가 없음

**수집 전략 (3단계)**:

```python
import aiohttp
import pdfplumber
from pathlib import Path

class GovtBudgetCollector:
    BASE_URL = "https://www.moef.go.kr/nw/nes/detailNesDtaView.do"
    
    async def collect(self) -> List[EconomicCollectDto]:
        """정부 예산안 문서 수집"""
        # Step 1: 게시판 리스트에서 최신 글의 첨부파일 링크 찾기
        attachments = await self._fetch_attachment_links()
        
        dtos = []
        for att in attachments:
            if att['url'].endswith('.pdf'):
                # Step 2: 파일 다운로드
                pdf_path = await self._download_file(att['url'])
                
                # Step 3: PDF → 텍스트 추출
                full_text = self._extract_pdf_text(pdf_path)
                
                # ⚠️ 정형화된 컬럼에 맞추기 어려움
                # → Silver Layer에서 LLM으로 정제 예정
                dtos.append(EconomicCollectDto(
                    source_type="GOVT_BUDGET",
                    source_url=att['url'],
                    target_company_or_fund="2026년 예산안",  # 임시
                    investment_amount=None,  # 본문에서 추출 불가
                    raw_document_text=full_text,  # 별도 컬럼 필요
                ))
        
        return dtos
    
    async def _fetch_attachment_links(self) -> List[dict]:
        """게시판 리스트 페이지 크롤링"""
        # BeautifulSoup으로 <a href="/download/...pdf"> 추출
        pass
    
    async def _download_file(self, url: str) -> Path:
        """파일 다운로드 → 임시 폴더 저장"""
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                content = await resp.read()
                path = Path(f"/tmp/{url.split('/')[-1]}")
                path.write_bytes(content)
                return path
    
    def _extract_pdf_text(self, path: Path) -> str:
        """PDF → 텍스트 추출"""
        with pdfplumber.open(path) as pdf:
            text = ""
            for page in pdf.pages:
                text += page.extract_text()
            return text
```

**HWP 파일 처리**:

```python
# requirements.txt
pyhwp>=0.1.0

from pyhwp import HWPReader

def extract_hwp_text(path: Path) -> str:
    """한글(HWP) → 텍스트 추출"""
    hwp = HWPReader(path)
    return hwp.read_text()
```

**실무 기법**:
- 이 테이블의 정형화된 컬럼(`investment_amount` 등)에 직접 넣기는 **거의 불가능**
- 일단 **문서 전체 텍스트를 별도 컬럼/테이블에 저장**
- **Silver Layer**에서 **LLM(Groq/Gemini)** 활용:
  ```
  프롬프트: "다음 예산안 문서에서 AI 관련 예산 규모를 숫자로 추출해 줘"
  ```

**주의점**:
- PDF/HWP 파싱은 **레이아웃 깨짐·표 추출 실패** 가능성 높음
- **표(Table) 전용 라이브러리** 고려:
  - `camelot-py` (PDF 표 추출 특화)
  - `tabula-py` (Java 기반, 무거움)

**난이도**: ⭐⭐⭐⭐⭐ (가장 어려움)

---

## 💡 Bronze Layer 핵심 기법 요약

### 1. 가짜 브라우저 행세 (User-Agent 주입)

**문제**: The VC나 뉴스 사이트는 봇(Bot)을 차단합니다.

**해결**:

```python
# spokes/infra/http_client.py
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
}

async def get_http_client():
    return aiohttp.ClientSession(headers=DEFAULT_HEADERS)
```

---

### 2. Selector Fallback 체인 적극 활용

**문제**: 언론사·스타트업 사이트는 UI 리뉴얼이 잦음

**해결**: `selector_fallback.py`로 1순위 → 2순위 → 3순위 시도

```python
# 예시: The VC 투자 리스트
SELECTORS = {
    "company": [
        "h3.investment-title",          # 1순위 (현재)
        "div.card-title",               # 2순위 (2025년 리뉴얼 후)
        "span[data-field='company']"    # 3순위 (최후 백업)
    ]
}

companies = extract_with_fallback(page, SELECTORS["company"])
if not companies:
    # 모든 후보 실패 → 알림 + 수동 확인
    await send_alert("The VC 셀렉터 모두 실패 - 수동 업데이트 필요")
```

---

### 3. 트래픽 예의 지키기 (Rate Limiting)

**문제**: 비동기(`asyncio.gather`)로 0.1초에 100번 요청 → IP 차단

**해결**:

```python
import asyncio

async def collect_with_rate_limit(collectors: List[Collector]):
    """소스 간 1초 간격 유지"""
    results = []
    for collector in collectors:
        result = await collector.collect()
        results.append(result)
        await asyncio.sleep(1)  # 서버 부담 줄이기
    return results
```

---

### 4. 재시도 (Retry) 로직 필수

**문제**: 공공 API·뉴스 사이트는 Timeout 자주 발생

**해결**: Tenacity 라이브러리

```python
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import aiohttp

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(aiohttp.ClientError)
)
async def fetch_with_retry(url: str):
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=30) as resp:
            return await resp.json()
```

---

### 5. 중복 제거 (URL 해시)

**문제**: 같은 기사·공시를 여러 번 적재

**해결**: Repository에서 `source_url` 기준 중복 체크

```python
# hub/repositories/economic_repository.py
async def bulk_insert(self, dtos: List[EconomicCollectDto]):
    for dto in dtos:
        if await self._exists(dto.source_url):
            logger.debug(f"중복 URL 스킵: {dto.source_url}")
            continue
        
        entity = RawEconomicData(**dto.dict())
        self.session.add(entity)
    
    await self.session.commit()

async def _exists(self, url: str) -> bool:
    result = await self.session.execute(
        select(RawEconomicData.id)
        .where(RawEconomicData.source_url == url)
        .limit(1)
    )
    return result.scalar_one_or_none() is not None
```

---

## 구현 우선순위 (Phase 1 - 1주)

| 순위 | 출처 | 난이도 | 예상 소요 | 비고 |
|------|------|--------|-----------|------|
| 1 | **DART OpenAPI** | ⭐ | 3시간 | `dart-fss` 라이브러리 활용 |
| 2 | **Wowtale RSS** | ⭐ | 2시간 | `feedparser` 한 줄 |
| 3 | **중소벤처 OpenAPI** | ⭐⭐ | 4시간 | XML 파싱 + Retry 로직 |
| 4 | **Yahoo Finance** | ⭐⭐ | 3시간 | `yfinance` 라이브러리 |
| 5 | **The VC** | ⭐⭐⭐⭐ | 1일 | 숨은 API 찾기 (Network 탭 분석) |
| 6 | **정부 문서** | ⭐⭐⭐⭐⭐ | 2일 | Silver Layer로 미루기 권장 |

**권장 착수 순서**: 1 → 2 → 3 → (테스트·배포) → 4 → 5 → 6

---

## 의존성 (requirements.txt 추가)

```txt
# Bronze Layer - raw_economic_data 전용
dart-fss>=0.3.0           # DART OpenAPI 래퍼
feedparser>=6.0.0         # RSS 파싱
xmltodict>=0.13.0         # XML → dict 변환
yfinance>=0.2.0           # Yahoo Finance
pdfplumber>=0.10.0        # PDF 텍스트 추출
pyhwp>=0.1.0              # HWP 텍스트 추출
tenacity>=8.0.0           # Retry 로직
```

---

## 다음 단계

1. **DART Collector 구현** (가장 쉬움)
2. **Wowtale RSS Collector 구현** (가성비 최고)
3. **통합 테스트** (`bronze_ingest_service.py`에서 두 소스 병렬 실행)
4. **스케줄러 등록** (`bronze_scheduler.py` - 매일 새벽 3시)
5. **API 엔드포인트** (수동 트리거·상태 조회)

---

## 관련 문서

- `BRONZE_ARCHITECTURE_DECISION.md` — 전체 아키텍처 결정 사항
- `DATA_COLLECTION_STRATEGY.md` — 일반 수집 전략
- `DATA_COLLECTION_SOURCES_GUIDE_V3.md` — 전체 출처 목록
- `backend/docs/erd.md` — 테이블 DDL
