# Yahoo Finance ETF 수집 가이드 (`raw_economic_data`)

## 개요

| 항목 | 값 |
|------|------|
| **출처명** | Yahoo Finance (한국 테마 ETF) |
| **공식 사이트** | https://finance.yahoo.com/ |
| **데이터 타입** | 시계열 금융 데이터 (가격, 거래량) |
| **수집 도구** | `yfinance` 라이브러리 (비공식, 역엔지니어링) |
| **업데이트 빈도** | 실시간 (장 마감 후 확정) |
| **수집 빈도 권장** | **하루 1회 (새벽 배치)** — IP 차단 방지 |
| **매핑 테이블** | `raw_economic_data` |
| **난이도** | ⭐⭐ (라이브러리 의존 + 데이터 해석 필요) |

---

## 왜 Yahoo Finance ETF 인가?

### 1. "자본의 선행 이동"을 포착하는 핵심 지표

개인 투자자와 기관은 **특정 테마에 돈이 몰릴 것 같다는 기대**가 생기면,
직접 개별 종목을 사기 전에 먼저 **테마 ETF부터 매수**하는 경향이 있습니다.

| 시나리오 | 투자 순서 | 시간차 |
|---------|----------|--------|
| "AI 붐이 온다" | ① TIGER AI반도체 ETF 매수 → ② SK하이닉스 직접 매수 | 수일~수주 |
| "2차전지 상승장" | ① KODEX 2차전지 ETF 매수 → ② LG에너지솔루션 직접 매수 | 수일~수주 |

→ **ETF 거래량 급증 = 해당 테마로 자본이 몰리기 시작했다는 가장 빠른 신호**

### 2. DART, RSS 뉴스와 상호 보완

| 출처 | 신호 타입 | 지연 시간 |
|------|-----------|----------|
| DART 공시 | 기업의 "공식 투자 결정" | 즉시~1일 |
| Wowtale/스타트업레시피 | 언론이 "보도한 투자" | 1~3일 |
| **Yahoo Finance ETF** | 시장이 "예상·반응한 자본 유입" | **실시간** (장 마감 후) |

→ 3개 출처를 조합하면 **"공식 발표 전 자본 이동"까지 추적 가능**

### 3. 1인 개발자에게 가장 구현하기 쉬운 금융 데이터

- ✅ 공식 API 신청·승인 불필요
- ✅ `yfinance` 라이브러리 1줄로 데이터 수집
- ✅ 크롤링 금지 우회 (Yahoo가 허용하는 범위 내)
- ⚠️ 단, 비공식 라이브러리이므로 Yahoo 정책 변경 시 깨질 위험 있음

---

## 핵심 전략: "거래량 급증 탐지"

### 왜 가격이 아닌 거래량인가?

| 지표 | 의미 | 문제점 |
|------|------|--------|
| 가격 상승 | "이미 오른 뒤" | 선행성 낮음 |
| **거래량 급증** | "자본이 몰리는 중" | **선행 지표** |

거래량이 평균 대비 2배 이상 증가했다면, 그 테마에 **"무언가 일어나고 있다"**는
강한 신호입니다.

### 탐지 알고리즘 (3단계)

```python
# Step 1: 최근 20일 평균 거래량 계산
avg_volume_20d = hist['Volume'].rolling(20).mean()

# Step 2: 어제 거래량이 평균 대비 몇 배인지 계산
yesterday_volume = hist.iloc[-1]['Volume']
volume_ratio = yesterday_volume / avg_volume_20d.iloc[-1]

# Step 3: 2배 이상이면 "급증" 판정
if volume_ratio >= 2.0:
    # 자본 유입액 = 거래량 × 종가
    inflow_amount = int(yesterday_volume * hist.iloc[-1]['Close'])
    # Bronze 적재
```

---

## 한국 테마 ETF 티커 리스트 (2026년 기준)

### 우선순위 1 (핵심 트렌드 테마)

| 티커 | ETF 이름 | 테마 | 운용사 |
|------|---------|------|--------|
| `091220.KS` | TIGER 글로벌AI액티브 | AI/반도체 | 미래에셋 |
| `441680.KS` | KODEX 2차전지산업 | 2차전지/배터리 | 삼성자산운용 |
| `360750.KS` | TIGER 블록체인액티브 | 블록체인/Web3 | 미래에셋 |
| `381180.KS` | TIGER 차이나바이오테크 | 바이오/제약 | 미래에셋 |
| `228790.KS` | KODEX 메타버스액티브 | 메타버스/XR | 삼성자산운용 |

### 우선순위 2 (산업 전환 테마)

| 티커 | ETF 이름 | 테마 |
|------|---------|------|
| `139660.KS` | KODEX ESG | ESG/지속가능경영 |
| `420030.KS` | TIGER 미국나스닥100 | 글로벌 테크 (한국 투자자 관심) |
| `261140.KS` | KODEX K-신재생에너지액티브 | 재생에너지/탄소중립 |
| `332620.KS` | TIGER K-푸드 | K-푸드/농식품 |

### 추가 고려 ETF (Phase 2)

- **TIGER 미국빅테크TOP10** (`464920.KS`) — 빅테크 자금 흐름
- **KODEX K-메타버스액티브MZ** (`453870.KS`) — MZ세대 투자 트렌드
- **TIGER 차이나전기차SOLACTIVE** (`371460.KS`) — 전기차 공급망

→ **Phase 1 권장**: 우선순위 1의 5개 티커로 시작 (AI, 2차전지, 블록체인, 바이오, 메타버스)

---

## `yfinance` 라이브러리 3대 함정과 대응책

### 함정 1: IP 차단 (Rate Limiting)

**현상**: 짧은 시간에 너무 많은 티커를 조회하면 Yahoo가 IP 차단

**대응**:
```python
import asyncio

async def collect_with_delay(tickers: list[str]):
    results = []
    for ticker in tickers:
        result = await asyncio.to_thread(fetch_ticker_data, ticker)
        results.append(result)
        await asyncio.sleep(2)  # 티커 간 2초 간격 강제
    return results
```

**권장 수집 빈도**: 하루 1회 (새벽 3~4시)

---

### 함정 2: 데이터 누락 (일부 티커만 실패)

**현상**: 특정 티커가 상장폐지되거나 Yahoo가 데이터를 제공하지 않을 때
`yf.Ticker(ticker).history()` 가 빈 DataFrame 반환

**대응**:
```python
def fetch_ticker_data(ticker: str) -> dict | None:
    try:
        etf = yf.Ticker(ticker)
        hist = etf.history(period="20d")
        
        if hist.empty:
            logger.warning(f"Yahoo Finance: {ticker} 데이터 없음 (상장폐지 또는 Yahoo 미제공)")
            return None
        
        # 정상 처리
        return {"ticker": ticker, "data": hist}
    
    except Exception as e:
        logger.error(f"Yahoo Finance: {ticker} 수집 실패 - {e}")
        return None
```

**Bronze Layer 원칙**: 실패한 티커는 건너뛰되, 로그에 기록 → 수동 확인

---

### 함정 3: 통화 단위 혼동 (KRW vs USD)

**현상**: 한국 ETF(`.KS`, `.KQ`)는 **원화(KRW)** 기준이지만,
미국 ETF는 **달러(USD)** 기준

**대응**:
```python
def get_currency_from_ticker(ticker: str) -> str:
    """티커 suffix로 통화 판단"""
    if ticker.endswith((".KS", ".KQ")):
        return "KRW"
    elif ticker.endswith((".US", ".O", ".N")):
        return "USD"
    return "UNKNOWN"
```

**DTO 매핑 시 `currency` 필드에 명시적으로 기록**

---

## DTO 매핑 전략

### Bronze Layer 저장 필드

| `EconomicCollectDto` 필드 | 값 | 비고 |
|---------------------------|-----|------|
| `source_type` | `YAHOO_ETF_AI` / `YAHOO_ETF_BATTERY` / `YAHOO_ETF_BLOCKCHAIN` 등 | 테마별로 세분화 |
| `source_url` | `https://finance.yahoo.com/quote/{ticker}/history` | 원본 차트 페이지 |
| `raw_title` | `"TIGER 글로벌AI액티브 거래량 2.3배 급증 (2026-05-11)"` | 사람이 읽기 쉬운 요약 |
| `investor_name` | `None` | ETF는 투자 주체가 불특정 다수 |
| `target_company_or_fund` | `"TIGER 글로벌AI액티브"` | ETF 이름 (한글) |
| `investment_amount` | `거래량 × 종가` | **원화 기준** 자본 유입 추정액 |
| `currency` | `"KRW"` | 한국 ETF는 원화 |
| `published_at` | 어제 날짜 (KST 자정) | 장 마감일 |
| `raw_metadata` | `{ticker, volume_ratio, avg_volume_20d, close, high, low}` | Silver 단계 추가 분석용 |

### `source_type` 세분화 (테마별)

| 티커 | `source_type` |
|------|---------------|
| `091220.KS` (TIGER 글로벌AI액티브) | `YAHOO_ETF_AI` |
| `441680.KS` (KODEX 2차전지산업) | `YAHOO_ETF_BATTERY` |
| `360750.KS` (TIGER 블록체인액티브) | `YAHOO_ETF_BLOCKCHAIN` |
| `381180.KS` (TIGER 차이나바이오테크) | `YAHOO_ETF_BIO` |
| `228790.KS` (KODEX 메타버스액티브) | `YAHOO_ETF_METAVERSE` |

→ 나중에 대시보드에서 **"AI 테마 자금 유입 추이"** 같은 시계열 차트 생성 가능

---

## 구현 예시 (의사코드)

### Collector 클래스

```python
"""Yahoo Finance ETF 거래량 급증 탐지 Collector."""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import yfinance as yf
import pandas as pd

from domain.master.models.transfer.economic_collect_dto import EconomicCollectDto

logger = logging.getLogger(__name__)

_KST = timezone(timedelta(hours=9))

# 티커 → source_type 매핑
_TICKER_TO_SOURCE_TYPE: dict[str, str] = {
    "091220.KS": "YAHOO_ETF_AI",
    "441680.KS": "YAHOO_ETF_BATTERY",
    "360750.KS": "YAHOO_ETF_BLOCKCHAIN",
    "381180.KS": "YAHOO_ETF_BIO",
    "228790.KS": "YAHOO_ETF_METAVERSE",
}

# 티커 → 한글 이름
_TICKER_TO_NAME: dict[str, str] = {
    "091220.KS": "TIGER 글로벌AI액티브",
    "441680.KS": "KODEX 2차전지산업",
    "360750.KS": "TIGER 블록체인액티브",
    "381180.KS": "TIGER 차이나바이오테크",
    "228790.KS": "KODEX 메타버스액티브",
}


class YahooFinanceETFCollector:
    """Yahoo Finance 한국 테마 ETF 거래량 급증 탐지 컬렉터.
    
    - yfinance 라이브러리 사용 (비공식, 역엔지니어링)
    - 거래량이 20일 평균 대비 2배 이상 증가한 ETF만 수집
    - IP 차단 방지: 티커 간 2초 간격 + 하루 1회 배치 권장
    """
    
    def __init__(
        self,
        *,
        volume_threshold: float = 2.0,
        lookback_days: int = 20,
    ):
        """
        Args:
            volume_threshold: 거래량 급증 판정 기준 (배수). 기본 2.0 = 평균 대비 2배
            lookback_days: 평균 계산 기간 (일). 기본 20일
        """
        self.volume_threshold = volume_threshold
        self.lookback_days = lookback_days
    
    async def collect(self) -> list[EconomicCollectDto]:
        """비동기 수집 (각 티커 간 2초 지연)."""
        dtos: list[EconomicCollectDto] = []
        
        for ticker in _TICKER_TO_SOURCE_TYPE.keys():
            try:
                dto = await asyncio.to_thread(self._collect_ticker, ticker)
                if dto:
                    dtos.append(dto)
                await asyncio.sleep(2)  # IP 차단 방지
            except Exception:
                logger.exception(f"Yahoo Finance {ticker} 수집 실패")
        
        logger.info(f"Yahoo Finance ETF 수집 완료: {len(dtos)}건")
        return dtos
    
    def _collect_ticker(self, ticker: str) -> Optional[EconomicCollectDto]:
        """단일 티커 수집 (동기 함수 — asyncio.to_thread로 호출됨)."""
        try:
            etf = yf.Ticker(ticker)
            hist = etf.history(period=f"{self.lookback_days + 5}d")
            
            if hist.empty or len(hist) < 10:
                logger.warning(f"{ticker}: 데이터 부족 (상장폐지 또는 Yahoo 미제공)")
                return None
            
            # 거래량 급증 판정
            avg_volume = hist['Volume'].rolling(self.lookback_days).mean()
            yesterday = hist.iloc[-1]
            yesterday_avg = avg_volume.iloc[-1]
            
            if pd.isna(yesterday_avg) or yesterday_avg == 0:
                logger.warning(f"{ticker}: 평균 거래량 계산 불가")
                return None
            
            volume_ratio = yesterday['Volume'] / yesterday_avg
            
            if volume_ratio < self.volume_threshold:
                # 급증 아님 → 스킵
                return None
            
            # 급증 감지 → DTO 생성
            inflow_amount = int(yesterday['Volume'] * yesterday['Close'])
            
            etf_name = _TICKER_TO_NAME.get(ticker, ticker)
            source_type = _TICKER_TO_SOURCE_TYPE.get(ticker, "YAHOO_ETF")
            
            raw_title = (
                f"{etf_name} 거래량 {volume_ratio:.1f}배 급증 "
                f"({yesterday.name.strftime('%Y-%m-%d')})"
            )
            
            # published_at: 어제 날짜 (장 마감일) KST 자정
            published_date = yesterday.name.to_pydatetime().date()
            published_at = datetime(
                published_date.year,
                published_date.month,
                published_date.day,
                tzinfo=_KST,
            )
            
            raw_metadata = {
                "ticker": ticker,
                "volume_ratio": round(volume_ratio, 2),
                "avg_volume_20d": int(yesterday_avg),
                "yesterday_volume": int(yesterday['Volume']),
                "close": float(yesterday['Close']),
                "high": float(yesterday['High']),
                "low": float(yesterday['Low']),
            }
            
            return EconomicCollectDto(
                source_type=source_type,
                source_url=f"https://finance.yahoo.com/quote/{ticker}/history",
                raw_title=raw_title[:500],
                investor_name=None,
                target_company_or_fund=etf_name[:255],
                investment_amount=inflow_amount,
                currency="KRW",
                raw_metadata=raw_metadata,
                published_at=published_at,
            )
        
        except Exception:
            logger.exception(f"{ticker} 처리 중 오류")
            return None
```

---

## 운영 시 주의사항 (4가지)

### 1. IP 차단 방지 전략

| 위험도 | 수집 빈도 | 티커 수 | 대응 |
|--------|----------|---------|------|
| 낮음 | 하루 1회 | 5개 | 티커 간 2초 지연 |
| 보통 | 하루 2회 | 10개 | 티커 간 3초 지연 |
| 높음 | 하루 3회 이상 | 20개+ | ⚠️ 차단 위험 높음 → **권장하지 않음** |

**권장**: 새벽 3시 1회 배치, 티커 5개, 간격 2초

---

### 2. `yfinance` 버전 고정

`yfinance`는 Yahoo 구조 변경에 맞춰 자주 업데이트됩니다.
갑작스러운 버전 업그레이드로 인한 파이프라인 중단을 방지하기 위해
**버전을 고정**하세요.

```txt
# requirements.txt
yfinance==0.2.40  # 2026-05 기준 안정 버전
```

---

### 3. 거래량 급증 "오탐" 처리

**오탐 사례**:
- 월요일 (주말 후 거래량 자연 증가)
- 공휴일 다음 날
- 분기말·결산일

**대응**:
```python
# raw_metadata에 요일 정보 추가
raw_metadata["day_of_week"] = yesterday.name.strftime("%A")  # "Monday"

# Silver Layer에서 월요일 데이터는 가중치 0.5로 조정
```

---

### 4. 비공식 라이브러리 리스크 대비

`yfinance`가 갑자기 작동을 멈춘다면?

**대응**:
1. **모니터링 알림**: 수집 건수가 0건이면 Slack/이메일 알림
2. **Fallback 계획**: 
   - Plan B: 네이버 금융 크롤링 (Playwright)
   - Plan C: 한국거래소(KRX) OpenAPI (신청 필요)

---

## 다음 단계 (구현 순서)

| # | 작업 | 예상 시간 |
|---|------|----------|
| 1 | `yahoo_finance_collector.py` 작성 | 2시간 |
| 2 | `bronze_economic_ingest_service.ingest_yahoo_etf()` 추가 | 30분 |
| 3 | 라우터 `POST /api/master/bronze/economic/yahoo-etf` 추가 | 30분 |
| 4 | 통합 테스트 스크립트 `yahoo_etf_integration_test.py` | 30분 |
| 5 | `requirements.txt`에 `yfinance==0.2.40` 추가 | 5분 |
| 6 | 수집 결과 검증 (실제 급증 날짜와 비교) | 1시간 |

**총 예상 시간**: 약 4~5시간

---

## 기대 효과

### 정량적 효과

- **선행 지표 확보**: 뉴스 보도보다 1~3일 빠른 자본 흐름 포착
- **다각도 검증**: DART + RSS + ETF 3개 출처 교차 검증 → 신뢰도 향상
- **대시보드 시각화**: "AI 테마 자금 유입 추이" 같은 시계열 차트 생성 가능

### 정성적 효과

- **트렌드 예측력 향상**: "언론이 보도하기 전에 시장은 이미 알고 있었다"
- **사용자 신뢰 확보**: "이 앱은 뉴스가 아닌 실제 돈의 흐름을 본다"

---

## 관련 문서

- `RAW_ECONOMIC_DATA_COLLECTION_GUIDE.md` — 경제 도메인 6개 출처 종합
- `DART_ECONOMIC_ENHANCEMENT_STRATEGY.md` — DART 컬렉터 참고
- `WOWTALE_RSS_COLLECTION_GUIDE.md` — RSS 컬렉터 참고
- `backend/docs/DATA_COLLECTION_SOURCES_GUIDE_V3.md` — 전체 출처 인덱스
