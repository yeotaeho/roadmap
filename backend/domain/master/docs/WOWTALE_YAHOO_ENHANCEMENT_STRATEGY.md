# Wowtale / Yahoo Finance 시계열 데이터 확충 전략

## 📋 문서 개요

- **작성일**: 2026-05-14
- **목적**: `BRONZE_ARCHITECTURE_DECISION.md` 문제점 3번(HIGH)에 대한 구체적 해결 방안 제시
- **범위**: Wowtale RSS 및 Yahoo Finance 시계열 데이터 부족 문제 진단 및 개선안

---

## 🔍 현재 상태 진단

### 1. Wowtale RSS 수집기

#### 현재 구현 상태 (`wowtale_collector.py`)

```python
# 현재 설정
RSS_URL = "https://wowtale.net/feed/"
def collect(*, max_items: int = 50):  # 라우터 기본값
    feed = feedparser.parse(self.RSS_URL)
    # 키워드 필터링 후 DTO 생성
    # investment_amount = None  ← 금액 정보 미추출
    # investor_name = _extract_investor_from_title(title)  ← 제목에서만 간단 추출
```

#### 확인된 문제점

| 문제 | 현재 상태 | 영향도 |
|------|----------|--------|
| **수집 건수 부족** | 2건 수집 (이론상 10~20건 가능) | 🔴 High |
| **투자 금액 누락** | `investment_amount=None` 고정 | 🔴 Critical |
| **투자자 정보 부정확** | 제목 첫 토큰만 추출 (정확도 ~40%) | 🟡 Medium |
| **시계열 한계** | RSS는 최신 ~50개만, 과거 데이터 접근 불가 | 🔴 High |
| **본문 미활용** | RSS `content:encoded` 또는 `summary`만 저장, 실제 기사 페이지 크롤링 없음 | 🟡 Medium |

#### 데이터 품질 분석

**RSS 피드 자체의 한계:**
- RSS는 최근 게시물 **최대 50개** 정도만 제공 (사이트 정책에 따라 다름)
- Wowtale은 일 3~10건 게시 → RSS만으로는 **최근 5~7일치**만 확보
- 과거 데이터를 가져오려면 **아카이브 페이지 크롤링** 필요

**투자 금액 추출 가능성:**
Wowtale 기사 본문 예시:
```
"[투자] 핀테크 스타트업 A사, 시리즈B 300억원 유치...
카카오벤처스·알토스벤처스 공동 투자"
```
→ 정규식 또는 NLP로 **"300억원"** / **"카카오벤처스"** / **"시리즈B"** 추출 가능

### 2. Yahoo Finance 수집기

#### 현재 구현 상태 (`yahoo_finance_collector.py` + `yahoo_macro_collector.py`)

```python
# yahoo_finance_collector.py
VOLUME_SURGE_TARGETS = 16개 ticker
  - 한국 ETF: 5종 (AI, 2차전지, 바이오, 재생에너지, K-푸드)
  - 한국 대형주: 5종 (삼성전자, SK하이닉스, LG에너지솔루션, 삼성바이오, NAVER)
  - 글로벌 ETF: 6종 (SPY, QQQ, SMH, ARKK, LIT, XLE)

_HISTORY_PERIOD = "60d"  ← 60일치만
threshold: 1.5 ~ 2.5배 (거래량 급증 임계값)

# yahoo_macro_collector.py
MACRO_TARGETS = 8개 ticker
  - FX: USDKRW=X, EURKRW=X, JPYKRW=X (환율)
  - RATE: ^TNX, ^IRX (미국채 금리)
  - COMMODITY: GC=F, CL=F (금, 원유)
  - CRYPTO: BTC-USD (비트코인)

_HISTORY_PERIOD = "60d"
threshold: 2.0 ~ 2.5 (Z-score)
```

#### 확인된 문제점

| 문제 | 현재 상태 | 영향도 |
|------|----------|--------|
| **시계열 기간 짧음** | 60일치만 수집 (최소 1년 권장) | 🔴 Critical |
| **수집 빈도 부족** | 수동 실행만 (스케줄러 구축 완료, 활성화 필요) | 🟡 Medium |
| **Ticker 일부만 신호 발생** | 16개 중 5개만 임계값 초과 (정상 동작이나 데이터 부족) | 🟢 Low |
| **Macro 컬렉터 미활용** | 별도로 구현되어 있으나 라우터에 미등록 | 🟡 Medium |
| **과거 데이터 미보충** | Backfill 전략 없음 | 🔴 High |

#### 데이터 품질 분석

**Yahoo Finance의 강점:**
- ✅ **무료 오픈 데이터** (yfinance 라이브러리 사용)
- ✅ **과거 데이터 접근 가능** (`period="max"` 지원 — 수년 ~ 수십년)
- ✅ **글로벌 자산** 커버리지 (ETF, 주식, 환율, 원자재, 암호화폐)
- ✅ **일별 OHLCV** 데이터 (Open, High, Low, Close, Volume)

**현재 수집 전략의 한계:**
- ⚠️ **"급증" 감지만** 수집 — 평상시 데이터는 누락
  - 예: 삼성전자 거래량이 평균 수준이면 **수집 안 함**
  - → "돈의 흐름" 분석에는 **전체 시계열**이 필요 (급증뿐만 아니라 평상시 흐름도)
- ⚠️ **60일만** 가져옴 → **4.5개월**치만 확보
  - 분기별/연간 트렌드 분석 불가능

---

## 🎯 개선 전략

### Phase 1: Wowtale 데이터 확충 (3일)

#### A. RSS 수집 극대화 (우선순위: P0)

**목표**: RSS 제공 최대치 (50개) 전부 수집

```python
# bronze_economic_ingest_service.py
async def ingest_wowtale(self, *, max_items: int = 50) -> dict[str, Any]:
    # 현재: 기본값 50 → 유지
    # 라우터에서도 기본값 50으로 설정 확인
```

**예상 효과**: 2건 → **10~20건** (5~10배 증가)

#### B. 투자 금액 NLP 추출 (우선순위: P0)

**방법 1: 정규식 패턴 매칭 (빠른 구현)**

```python
# wowtale_collector.py에 추가

import re

_AMOUNT_PATTERNS = [
    # "300억원", "50억 원", "10억"
    r'(\d+(?:,\d{3})*)\s*억\s*원?',
    # "3000만원", "5000만 원"
    r'(\d+(?:,\d{3})*)\s*만\s*원?',
    # "30조원"
    r'(\d+(?:,\d{3})*)\s*조\s*원?',
]

def _extract_investment_amount(text: str) -> int | None:
    """본문 텍스트에서 투자 금액 추출 (단위: 원)."""
    for pattern in _AMOUNT_PATTERNS:
        match = re.search(pattern, text)
        if match:
            number_str = match.group(1).replace(',', '')
            number = int(number_str)
            
            # 단위 변환
            if '조' in match.group(0):
                return number * 1_000_000_000_000
            elif '억' in match.group(0):
                return number * 100_000_000
            elif '만' in match.group(0):
                return number * 10_000
    return None

# collect() 메서드에서 사용
html_content = _extract_html_content(entry)
full_text = _html_to_text(html_content)
amount = _extract_investment_amount(full_text)  # 🆕

dtos.append(EconomicCollectDto(
    ...
    investment_amount=amount,  # 🟢 금액 매핑
    ...
))
```

**예상 성공률**: 70~80% (정규식 매칭)

**방법 2: LLM 프롬프트 (Phase 2 — Silver 단계에서 구현 권장)**

```python
# Silver 단계에서 GPT-4/Claude에 프롬프트:
# "다음 투자 뉴스에서 투자 금액, 투자자, 피투자사, 라운드를 JSON으로 추출하세요"
```

#### C. 본문 크롤링 추가 (우선순위: P1)

**배경**: RSS의 `content:encoded`가 전문이 아닌 요약일 수 있음

```python
# wowtale_collector.py에 추가

import httpx
from bs4 import BeautifulSoup

async def _fetch_article_body(self, url: str) -> str:
    """Wowtale 기사 페이지를 직접 방문해 전문 크롤링."""
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, headers={"User-Agent": "..."})
            resp.raise_for_status()
            
        soup = BeautifulSoup(resp.text, "html.parser")
        
        # Wowtale은 WordPress 기반 → 일반적인 article 태그 사용
        article = soup.select_one("article .entry-content")
        if article:
            return article.get_text(separator=" ", strip=True)
    except Exception:
        logger.warning("Wowtale 본문 크롤링 실패: %s", url)
    return ""

# collect() 메서드에서 사용
for entry in feed.entries[:max_items]:
    ...
    # RSS 본문이 짧으면 크롤링 시도
    if len(full_text) < 200:
        full_text = await self._fetch_article_body(link)
```

**예상 효과**: 금액 추출 성공률 80% → **90%+**

#### D. 과거 데이터 Backfill — Wowtale 아카이브 크롤링 (우선순위: P2)

**목표**: 최근 1년치 기사 수집 (약 1,000~3,000건)

**Wowtale 아카이브 구조 확인 필요:**
```
https://wowtale.net/category/투자/
https://wowtale.net/2025/12/
https://wowtale.net/page/2/
```

**구현 예시:**

```python
# backend/domain/master/hub/services/collectors/economic/wowtale_archive_crawler.py (신규)

class WowtaleArchiveCrawler:
    """Wowtale 과거 기사 아카이브 페이지 크롤링."""
    
    BASE_URL = "https://wowtale.net"
    CATEGORY_URL = f"{BASE_URL}/category/투자/"  # 투자 카테고리
    
    async def crawl_category_pages(
        self, 
        *,
        max_pages: int = 50,  # 페이지당 ~20건 → 50페이지 = 1,000건
    ) -> list[EconomicCollectDto]:
        """카테고리 아카이브 페이지를 순회하며 기사 목록 수집."""
        dtos: list[EconomicCollectDto] = []
        
        for page_num in range(1, max_pages + 1):
            page_url = f"{self.CATEGORY_URL}page/{page_num}/"
            
            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.get(page_url, timeout=30)
                    resp.raise_for_status()
                
                soup = BeautifulSoup(resp.text, "html.parser")
                
                # WordPress 표준 구조: <article class="post"> 리스트
                articles = soup.select("article.post")
                if not articles:
                    break  # 더 이상 페이지 없음
                
                for article in articles:
                    title_elem = article.select_one("h2.entry-title a")
                    if not title_elem:
                        continue
                    
                    title = title_elem.get_text(strip=True)
                    link = title_elem.get("href")
                    
                    # 투자 관련 키워드 필터
                    if not _is_investment_relevant(title, []):
                        continue
                    
                    # 날짜 추출
                    date_elem = article.select_one("time.entry-date")
                    published_at = None
                    if date_elem and (dt_str := date_elem.get("datetime")):
                        published_at = datetime.fromisoformat(dt_str)
                    
                    # 기사 본문 크롤링 (별도 요청)
                    full_text = await self._fetch_article_body(link)
                    amount = _extract_investment_amount(full_text)
                    
                    dtos.append(EconomicCollectDto(
                        source_type=_classify_source_type(title, []),
                        source_url=link,
                        raw_title=title[:500],
                        investor_name=_extract_investor_from_title(title),
                        target_company_or_fund=None,
                        investment_amount=amount,
                        raw_metadata={"content_text": full_text[:5000]},
                        published_at=published_at,
                    ))
                
                await asyncio.sleep(1)  # 서버 부하 방지
                
            except Exception:
                logger.exception("Wowtale 아카이브 페이지 %s 크롤링 실패", page_num)
                break
        
        return dtos
```

**예상 공수**: 2일 (크롤링 로직 + 테스트 + 라우터 통합)
**예상 효과**: 2건 → **1,000~3,000건** (최근 1년치)

---

### Phase 2: Yahoo Finance 시계열 확충 (2일)

#### A. 과거 데이터 Backfill (우선순위: P0)

**목표**: 60일 → **1년 (365일)** 데이터 수집

```python
# yahoo_finance_collector.py 수정

_HISTORY_PERIOD = "1y"  # "60d" → "1y" 변경

# 또는 더 긴 기간 (3년 또는 전체)
# _HISTORY_PERIOD = "3y"
# _HISTORY_PERIOD = "max"  # 상장일 ~ 현재 (수년 ~ 수십년)
```

**Backfill 전용 스크립트 작성:**

```python
# backend/scripts/yahoo_backfill.py (신규)

"""Yahoo Finance 과거 1년치 데이터 일괄 Backfill."""

async def backfill_yahoo_finance():
    """16개 ticker × 365일 = 약 5,840건 예상 (임계값 초과 건만)"""
    from domain.master.hub.services.collectors.economic.yahoo_finance_collector import (
        YahooFinanceEtfCollector,
    )
    
    collector = YahooFinanceEtfCollector()
    
    # period="1y"로 1년치 데이터 수집
    # 하지만 현재 collect()는 "마지막 거래일"만 확인
    # → 일별로 돌면서 각 날짜의 급증 여부 확인 필요
    
    # 🆕 수정 필요: collect() 메서드를 "전체 시계열" 모드로 변경
    dtos, _ = await collector.collect_all_history(period="1y")
    
    # DB 적재
    async with AsyncSessionLocal() as session:
        repo = EconomicRepository(session)
        inserted = await repo.insert_many_skip_duplicates(dtos)
        logger.info(f"Yahoo Backfill 완료: {inserted}건 적재")

if __name__ == "__main__":
    asyncio.run(backfill_yahoo_finance())
```

**컬렉터 수정 — 전체 시계열 모드 추가:**

```python
# yahoo_finance_collector.py에 추가

def _compute_all_surges(
    target: VolumeSurgeTarget,
    hist: DataFrame,
) -> list[EconomicCollectDto]:
    """전체 거래일에 대해 급증 여부 확인 (Backfill용)."""
    hist = _drop_trailing_nan(hist)
    
    if hist is None or hist.empty or len(hist) < _MA_WINDOW + 1:
        return []
    
    dtos: list[EconomicCollectDto] = []
    
    # 윈도우 + 1 행부터 마지막까지 순회
    for i in range(_MA_WINDOW, len(hist)):
        # i번째 행을 "마지막 거래일"로 간주
        window_hist = hist.iloc[: i + 1]
        dto = _compute_inflow_dto(target, window_hist)
        if dto:
            dtos.append(dto)
    
    return dtos

class YahooFinanceEtfCollector:
    ...
    
    async def collect_all_history(
        self, 
        *, 
        period: str = "1y"
    ) -> tuple[list[EconomicCollectDto], int]:
        """전체 시계열 기간에 대해 급증 신호 수집 (Backfill 전용)."""
        out: list[EconomicCollectDto] = []
        skipped = 0
        
        for i, target in enumerate(self._targets):
            if i > 0:
                await asyncio.sleep(self._sleep_sec)
            
            try:
                hist = await asyncio.to_thread(
                    lambda: yf.Ticker(target.ticker).history(period=period, auto_adjust=False)
                )
            except Exception:
                logger.exception("Yahoo[%s] 다운로드 실패", target.ticker)
                skipped += 1
                continue
            
            try:
                surges = await asyncio.to_thread(_compute_all_surges, target, hist)
                out.extend(surges)
            except Exception:
                logger.exception("Yahoo[%s] 전체 시계열 급증 계산 실패", target.ticker)
                skipped += 1
        
        logger.info(
            "Yahoo 전체 시계열 수집: %s건 신호 / %s개 스킵",
            len(out),
            skipped,
        )
        return out, skipped
```

**예상 공수**: 1일 (컬렉터 수정 + 스크립트 작성 + 실행)
**예상 효과**: 5건 → **200~500건** (1년치, 16 ticker × 365일 중 급증일만)

#### B. 평상시 시계열 데이터 수집 (우선순위: P1)

**배경**: 현재는 "급증"만 감지 → **일별 전체 데이터**도 수집하면 더 풍부한 분석 가능

**전략**: 
1. **급증 감지용** 컬렉터는 유지 (현재 로직)
2. **시계열 전체용** 별도 테이블 또는 컬렉터 추가

```python
# 옵션 1: raw_economic_data에 모든 거래일 적재 (급증 여부 상관없이)
# → investment_amount = volume * vwap (급증 아니어도 일별 유입액 기록)

# 옵션 2: 별도 테이블 `raw_market_timeseries` 생성
# → OHLCV 원본 데이터 저장 (Silver 단계에서 가공)
```

**권장**: 옵션 2 — Bronze 단계에서 원본 시계열 저장, Silver에서 급증 분석

**예상 공수**: 2일 (테이블 설계 + 마이그레이션 + 컬렉터 수정)
**예상 효과**: **16 ticker × 365일 = 5,840건** (전체 시계열)

#### C. Macro 컬렉터 라우터 등록 (우선순위: P1)

**현재 상태**: `yahoo_macro_collector.py` 구현 완료, 라우터 미등록

```python
# master_routor.py에 추가

@router.post("/bronze/economic/yahoo-macro")
async def run_yahoo_macro_economic_bronze(
    db: AsyncSession = Depends(get_db),
):
    """Yahoo Finance 거시 지표(FX, Rate, Commodity, Crypto) 가격 변동 급증 수집."""
    svc = BronzeEconomicIngestService(db, None)
    try:
        return await svc.ingest_yahoo_macro()
    except Exception:
        logger.exception("Yahoo Macro Bronze ingest 실패")
        raise HTTPException(
            status_code=502,
            detail="Yahoo Macro 수집 중 오류가 발생했습니다.",
        ) from None
```

**스케줄러에도 추가** (이미 포함됨):
```python
# core/scheduler.py
_WEEKLY_JOBS = (
    ...
    ("yahoo_macro", _job_yahoo_macro),  # ✅ 이미 존재
)
```

**예상 공수**: 0.5일 (라우터만 추가)
**예상 효과**: **환율/금리/원자재 8종** 데이터 추가 → 거시 경제 지표 확보

---

### Phase 3: 대체 소스 확보 (5일)

#### A. Platum (플래텀) RSS + 크롤링 (우선순위: P0)

**배경**: Wowtale보다 **더 전문적인 스타트업 투자 미디어**

**RSS 피드**:
```
https://platum.kr/feed
https://platum.kr/archives/category/funding/feed
```

**구현**:
```python
# backend/domain/master/hub/services/collectors/economic/platum_collector.py (신규)

class PlatumEconomicCollector:
    """Platum 스타트업 투자 뉴스 RSS 수집.
    
    Wowtale과 거의 동일한 로직, RSS URL만 변경.
    """
    
    RSS_URL = "https://platum.kr/archives/category/funding/feed"
    
    # Wowtale 로직 재사용
    # - _is_investment_relevant
    # - _extract_investment_amount
    # - _extract_investor_from_title
```

**예상 공수**: 1일 (Wowtale 패턴 복사 + 테스트)
**예상 효과**: **20~30건/일** (Wowtale 대비 2~3배 많음)

#### B. 벤처스퀘어 RSS + 크롤링 (우선순위: P1)

**RSS 피드**:
```
https://www.venturesquare.net/feed
https://www.venturesquare.net/category/funding/feed
```

**예상 공수**: 1일
**예상 효과**: **10~20건/일**

#### C. 네이버 금융 뉴스 크롤링 (우선순위: P1)

**목적**: **산업 다양성 확보** (IT 외 제조/바이오/에너지 등)

**크롤링 대상**:
```
https://finance.naver.com/news/mainnews.nhn  # 증권 메인 뉴스
https://finance.naver.com/news/news_list.nhn?mode=LSS2D&section_id=101&section_id2=258  # M&A
https://finance.naver.com/news/news_list.nhn?mode=LSS2D&section_id=101&section_id2=259  # 투자
```

**구현 전략**:
- BeautifulSoup로 목록 페이지 크롤링
- 각 기사 본문 수집 (네이버 금융은 본문 요약만 제공 → 원문 링크 따라가기)
- LLM으로 투자 금액/투자자 추출

**예상 공수**: 2일
**예상 효과**: **30~50건/일** (산업 다양성 ↑)

#### D. 크런치베이스 API 연동 (우선순위: P2)

**배경**: **글로벌 VC 투자 데이터베이스** (한국 포함)

**API**: `https://www.crunchbase.com/`
- 무료 플랜: 월 200건
- 유료 플랜: 월 $29~$99 (월 5,000~50,000건)

**데이터 품질**:
- ✅ 투자 금액 **100% 정확** (DB 기반)
- ✅ 투자자·피투자사·라운드 **구조화**
- ✅ 글로벌 커버리지 (한국 스타트업도 포함)

**구현**:
```python
# backend/domain/master/hub/services/collectors/economic/crunchbase_collector.py (신규)

import httpx

class CrunchbaseCollector:
    BASE_URL = "https://api.crunchbase.com/api/v4"
    
    def __init__(self, api_key: str):
        self._api_key = api_key
    
    async def collect_recent_funding(
        self, 
        *, 
        country_code: str = "KOR",
        lookback_days: int = 30
    ) -> list[EconomicCollectDto]:
        """최근 N일간 한국 스타트업 투자 라운드 수집."""
        endpoint = f"{self.BASE_URL}/searches/funding_rounds"
        params = {
            "user_key": self._api_key,
            "field_ids": ["identifier", "announced_on", "money_raised", "investor_identifiers"],
            "query": [
                {
                    "type": "predicate",
                    "field_id": "funded_organization_location",
                    "operator_id": "includes",
                    "values": [country_code],
                },
                {
                    "type": "predicate",
                    "field_id": "announced_on",
                    "operator_id": "gte",
                    "values": [(datetime.utcnow() - timedelta(days=lookback_days)).strftime("%Y-%m-%d")],
                },
            ],
        }
        
        async with httpx.AsyncClient() as client:
            resp = await client.post(endpoint, json=params)
            resp.raise_for_status()
            data = resp.json()
        
        dtos: list[EconomicCollectDto] = []
        for item in data.get("entities", []):
            props = item.get("properties", {})
            
            amount_usd = props.get("money_raised", {}).get("value_usd")
            amount_krw = int(amount_usd * 1300) if amount_usd else None  # USD → KRW 환산
            
            investors = [inv.get("value") for inv in props.get("investor_identifiers", [])]
            
            dtos.append(EconomicCollectDto(
                source_type="CRUNCHBASE_FUNDING",
                source_url=f"https://www.crunchbase.com/funding_round/{props.get('identifier', {}).get('uuid')}",
                raw_title=f"{props.get('funded_organization_identifier', {}).get('value')} {props.get('funding_type')} 라운드",
                investor_name=", ".join(investors[:3]) if investors else None,
                target_company_or_fund=props.get("funded_organization_identifier", {}).get("value"),
                investment_amount=amount_krw,
                currency="KRW",
                raw_metadata=props,
                published_at=datetime.fromisoformat(props.get("announced_on")),
            ))
        
        return dtos
```

**예상 공수**: 1일 (API 연동 + 테스트)
**예상 효과**: **월 200~5,000건** (플랜에 따라)

---

## 📊 예상 효과 종합

### Phase 1 완료 후 (Wowtale 확충)

| 지표 | 현재 | Phase 1 후 |
|------|------|-----------|
| **Wowtale 건수** | 2건 | **1,000~3,000건** (1년치 backfill) |
| **투자 금액 채움률** | 0% | **70~80%** (정규식 추출) |
| **투자자 정확도** | ~40% | **60~70%** (본문 크롤링) |

### Phase 2 완료 후 (Yahoo Finance 확충)

| 지표 | 현재 | Phase 2 후 |
|------|------|-----------|
| **Yahoo Finance 건수** | 5건 | **200~500건** (1년 backfill, 급증일만) |
| **시계열 기간** | 60일 (2개월) | **365일 (1년)** |
| **Macro 지표** | 0건 | **월 10~30건** (환율/금리/원자재 급변동) |
| **전체 시계열 (옵션)** | 0건 | **5,840건** (16 ticker × 365일 전체) |

### Phase 3 완료 후 (대체 소스 확보)

| 지표 | 현재 | Phase 3 후 |
|------|------|-----------|
| **스타트업 투자 뉴스** | 2건 | **일 50~80건** (Wowtale + Platum + 벤처스퀘어) |
| **산업 다양성** | IT 70% | **IT 40% + 비IT 60%** (네이버 금융 뉴스 추가) |
| **글로벌 VC 투자** | 0건 | **월 200~5,000건** (크런치베이스) |

### 전체 데이터 증가 예상

| 항목 | 현재 (4.5개월) | 개선 후 (1년) |
|------|---------------|-------------|
| **총 레코드 수** | 131건 | **15,000~20,000건** |
| **일평균 신규 수집** | 0건 (수동) | **50~100건** (자동화) |
| **`investment_amount` 채움률** | ~5% | **60~70%** |
| **시계열 기간** | 4.5개월 | **12개월+** |
| **민간 투자(VC/PE) 비율** | 2% | **30~40%** |
| **선행 지표(뉴스) 비율** | 2% | **20~30%** |

---

## 🚀 실행 로드맵

### Phase 1: Wowtale 확충 (3일, 즉시 시작 가능)

| Task | 공수 | 우선순위 | 담당 |
|------|------|---------|------|
| RSS 수집 극대화 (max_items=50) | 0.5일 | P0 | Backend |
| 투자 금액 정규식 추출 | 1일 | P0 | Backend |
| 본문 크롤링 추가 | 1일 | P1 | Backend |
| 아카이브 Backfill 크롤러 | 2일 | P2 | Backend |

### Phase 2: Yahoo Finance 확충 (2일)

| Task | 공수 | 우선순위 | 담당 |
|------|------|---------|------|
| period="1y" 변경 + Backfill 스크립트 | 1일 | P0 | Backend |
| Macro 컬렉터 라우터 등록 | 0.5일 | P1 | Backend |
| 전체 시계열 수집 모드 (옵션) | 2일 | P2 | Backend |

### Phase 3: 대체 소스 확보 (5일)

| Task | 공수 | 우선순위 | 담당 |
|------|------|---------|------|
| Platum RSS 수집기 | 1일 | P0 | Backend |
| 벤처스퀘어 RSS 수집기 | 1일 | P1 | Backend |
| 네이버 금융 뉴스 크롤러 | 2일 | P1 | Backend |
| 크런치베이스 API 연동 | 1일 | P2 | Backend |

**총 공수**: **10일** (2주 스프린트)

---

## ⚠️ 주의사항 및 리스크

### 1. 크롤링 법적 검토

| 사이트 | ToS/robots.txt | 상업적 이용 | 리스크 평가 |
|--------|---------------|------------|-----------|
| **Wowtale** | ✅ robots.txt 허용 | ⚠️ 명시 없음 | 🟡 Medium — 소규모 크롤링은 일반적으로 허용, 대량은 문의 권장 |
| **Platum** | ✅ robots.txt 허용 | ⚠️ 명시 없음 | 🟡 Medium |
| **네이버 금융** | ⚠️ 일부 제한 | ❌ 상업적 이용 금지 | 🔴 High — 개인 연구/비상업 용도만, 출처 표기 필수 |
| **크런치베이스** | ✅ 공식 API | ✅ 유료 플랜으로 허용 | 🟢 Low |

**권장 조치**:
1. Wowtale/Platum: 소규모 크롤링(일 1~2회) + User-Agent 명시 + 1초 sleep
2. 네이버 금융: **비상업 용도만** 또는 공식 API 사용 검토
3. 크런치베이스: 유료 플랜 구독 (월 $29~)

### 2. IP 차단 방어

- **Rate Limiting**: 사이트당 일 1~2회 수집
- **User-Agent**: 브라우저처럼 보이는 헤더 사용
- **Sleep**: 요청 간 1~2초 대기
- **Proxy**: 필요 시 프록시 로테이션 (Phase 3 이후)

### 3. 데이터 정확도

- **정규식 추출**: 70~80% 정확도 (오탐/미탐 존재)
- **LLM 추출**: 90~95% 정확도 (비용 증가)
- **검증 로직**: Silver 단계에서 이상치 필터링

---

## 🔗 관련 문서

- `BRONZE_ARCHITECTURE_DECISION.md`: 전체 Bronze 품질 진단
- `DATA_COLLECTION_SOURCES_GUIDE_V3.md`: 데이터 소스 전체 전략
- `wowtale_collector.py`: 현재 Wowtale RSS 수집기
- `yahoo_finance_collector.py`: 현재 Yahoo Finance 수집기
- `yahoo_macro_collector.py`: Yahoo Macro 수집기
