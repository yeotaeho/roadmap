# Bronze Layer 데이터 수집 품질 진단 및 개선 전략

## 📋 문서 개요

- **작성일**: 2026-05-13
- **목적**: 현재 구축된 Bronze Layer (`raw_economic_data`) 수집 파이프라인의 데이터 품질을 진단하고, "Economic Flow (자본 흐름)" 분석에 필요한 정량적 지표 확보를 위한 구체적 개선 방안을 제시
- **분석 범위**: The VC, NTIS를 제외한 모든 활성 Collector (DART, ALIO, Wowtale, StartupRecipe, Yahoo, MOEF, MSIT)
- **분석 데이터**: 총 **131건**의 `raw_economic_data` 레코드 (17개 `source_type`)

---

## 🔍 현황 요약

### 수집 완료된 데이터 소스별 분포

| Source Type | 레코드 수 | 주요 특징 |
|-------------|-----------|-----------|
| **DART 관련** | 10건 | M&A, 시설투자, 유상증자, 전환사채 등 |
| **ALIO 공공기관 사업** | 25건 | 정부 공공기관 사업 정보 |
| **Wowtale RSS** | 2건 | 스타트업 뉴스 |
| **StartupRecipe RSS** | 1건 | 창업 지원 정보 |
| **Yahoo Finance** | 5건 | ETF (QQQ, SPY 등) 시장 데이터 |
| **MOEF 예산안** | 2건 | 기재부 예산안 PDF |
| **MSIT 보도자료/공고** | 86건 | 과기부 보도자료, 사업공고, R&D 예산 계획 |

### 시계열 범위

- **최소 날짜**: 2025-11-25
- **최대 날짜**: 2026-04-14
- **기간**: 약 **4.5개월** (시계열 분석에는 부족, 최소 1년 이상 권장)

---

## ❌ 발견된 문제점 및 원인 분석

### 1. 🔴 **CRITICAL: DART 데이터의 정량 지표 전면 누락**

#### 문제점
- **`investment_amount`**: 10건 모두 **`None`**
- **`raw_metadata`**: 10건 모두 **빈 딕셔너리 `{}`**
- **현재 상태**: DART 공시 제목(예: "유상증자 결정")만 수집, 실제 금액·대상 기업 정보는 미파싱

#### 원인
현재 `dart_collector.py`는 DART OpenAPI의 **리스트 조회 API**만 호출하여 공시 제목과 URL을 가져오고 있음. 실제 투자 금액, 투자 대상, 주식 수, 발행 가액 등의 정보는 각 공시의 **상세 페이지 또는 첨부 XML**을 추가 파싱해야 함.

#### Economic Flow 영향도
**최고 (Critical)** — M&A, 유상증자, 시설투자는 기업 자본 이동의 핵심인데, 금액 정보가 없으면 **정량적 분석 불가능**.

#### 구체적 해결 방법

**A. DART OpenAPI 상세 조회 추가 호출**

```python
# dart_collector.py 내부에 추가 메서드 구현 예시

async def _fetch_disclosure_detail(self, corp_code: str, rcept_no: str) -> dict:
    """
    DART 단일 공시 상세 조회 API 호출
    https://opendart.fss.or.kr/api/company.xml?crtfc_key=...&corp_code=...&rcept_no=...
    """
    url = "https://opendart.fss.or.kr/api/company.xml"
    params = {
        "crtfc_key": self._api_key,
        "corp_code": corp_code,
        "rcept_no": rcept_no,
    }
    async with self._session.get(url, params=params) as resp:
        xml_text = await resp.text()
        return xmltodict.parse(xml_text)

def _extract_investment_from_detail(self, detail: dict, report_nm: str) -> Optional[int]:
    """
    공시 유형별 금액 추출 로직
    - 유상증자: 'istc_totamt' (발행 총액)
    - M&A: 'acqs_mth1_stock_tamt' (취득 금액)
    - 시설투자: 'invstmnt_totamt' (투자 총액)
    """
    if "유상증자" in report_nm:
        return int(detail.get("istc_totamt", 0))
    elif "주요사항보고서(인수합병)" in report_nm:
        return int(detail.get("acqs_mth1_stock_tamt", 0))
    elif "시설투자" in report_nm:
        return int(detail.get("invstmnt_totamt", 0))
    # ... 전환사채, 타법인 출자 등 추가
    return None
```

**B. DTO 매핑 시 상세 정보 병합**

```python
async def collect_async(self, lookback_days: int = 30) -> list[EconomicCollectDto]:
    list_items = await self._fetch_list(lookback_days)
    dtos = []
    
    for item in list_items:
        corp_code = item["corp_code"]
        rcept_no = item["rcept_no"]
        
        # 상세 조회 추가
        detail = await self._fetch_disclosure_detail(corp_code, rcept_no)
        amount = self._extract_investment_from_detail(detail, item["report_nm"])
        
        dtos.append(EconomicCollectDto(
            source_type=self._classify_source_type(item["report_nm"]),
            source_url=f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcept_no}",
            raw_title=item["report_nm"],
            investor_name=item["corp_name"],
            target_company_or_fund=detail.get("acqs_comp_name"),  # M&A 대상
            investment_amount=amount,  # 🟢 금액 매핑
            raw_metadata=detail,       # 🟢 상세 정보 저장
            published_at=datetime.strptime(item["rcept_dt"], "%Y%m%d"),
        ))
    
    return dtos
```

**C. 예상 수집 시간 증가 대응**

- **문제**: 리스트 30건 → 상세 조회 30회 추가 (네트워크 지연 누적)
- **해결**: `asyncio.gather`로 상세 조회 병렬 처리 (5~10배 속도 향상)

```python
details = await asyncio.gather(
    *[self._fetch_disclosure_detail(item["corp_code"], item["rcept_no"]) 
      for item in list_items]
)
```

**우선순위**: ⚠️ **P0 (최우선)** — 다음 스프린트에서 즉시 구현

---

### 2. 🔴 **CRITICAL: ALIO 데이터의 예산 금액 전면 누락**

#### 문제점
- **`investment_amount` (budget_krw 매핑)**: 25건 모두 **`None`**
- **`published_at`**: 25건 중 23건이 **`None`** (시계열 분석 불가)
- **현재 상태**: 공공기관 사업 제목만 수집, 예산 규모·사업 시작일 정보 미활용

#### 원인
1. **ALIO API 응답 스키마 불일치**: 현재 `alio_public_inst_project_collector.py`의 `_parse_item()` 메서드가 예산 필드를 잘못 찾고 있음 (존재하지 않는 필드명 참조 가능성)
2. **날짜 필드 미매핑**: API 응답의 `bizStartDate`, `bizEndDate` 같은 필드를 `published_at`으로 변환하는 로직 누락

#### Economic Flow 영향도
**최고 (Critical)** — 정부 공공기관 사업 예산은 공공 부문에서 민간으로 흘러가는 자본의 대표 지표. 금액 없이는 "얼마나 큰 사업인지" 판단 불가능.

#### 구체적 해결 방법

**A. ALIO API 응답 필드 재확인**

ALIO 500 에러 수정 후 실제 응답 JSON 샘플을 확보하여, 예산 필드 이름을 정확히 식별:

```json
{
  "result": [
    {
      "instNm": "한국도로공사",
      "bizNm": "스마트 톨게이트 구축",
      "bizBdgt": "1500000000",  // 🔍 실제 필드명 확인 필요
      "bizStartDate": "20260101",
      "bizEndDate": "20261231"
    }
  ]
}
```

**B. Collector 수정 예시**

```python
def _parse_item(self, item: dict[str, Any]) -> EconomicCollectDto:
    # 예산 필드 매핑 (실제 필드명으로 교체)
    budget_str = self._pick(item, ["bizBdgt", "totBdgt", "budget"])
    budget_krw = None
    if budget_str:
        try:
            budget_krw = int(budget_str.replace(",", ""))
        except ValueError:
            logger.warning(f"ALIO budget parse failed: {budget_str}")
    
    # 날짜 매핑 (사업 시작일을 published_at으로)
    published_at = None
    start_date_str = self._pick(item, ["bizStartDate", "startDate"])
    if start_date_str:
        try:
            published_at = datetime.strptime(start_date_str, "%Y%m%d")
        except ValueError:
            pass
    
    return EconomicCollectDto(
        source_type="GOVT_ALIO_PROJECT",
        source_url=self._pick(item, ["siteUrl", "url"]) or "N/A",
        raw_title=self._pick(item, ["bizNm", "projectName"]) or "Unknown",
        investor_name=self._pick(item, ["instNm", "institution"]),
        target_company_or_fund=None,
        investment_amount=budget_krw,  # 🟢 수정
        currency="KRW",
        raw_metadata=item,
        published_at=published_at,     # 🟢 수정
    )
```

**C. 통합 테스트 스크립트 작성**

```bash
# scripts/alio_integration_test.py 실행 시 예산·날짜 출력 확인
python backend/scripts/alio_integration_test.py

# 예상 출력:
# ✅ 수집 완료: 25건
# ✅ budget_krw None 비율: 0% (목표)
# ✅ published_at None 비율: < 10%
```

**우선순위**: ⚠️ **P0 (최우선)** — ALIO API 500 에러 해결 직후 즉시 구현

---

### 3. 🟡 **HIGH: Wowtale / Yahoo Finance 시계열 데이터 부족**

#### 문제점
- **Wowtale**: 2건 (너무 적음, RSS 피드에서 최소 10~20건은 확보 가능)
- **Yahoo Finance**: 5건 (16개 ETF 설계했으나 5개만 수집됨)

#### 원인
1. **수집 빈도 부족**: 일회성 수동 실행으로만 테스트, 자동화 스케줄러 미구동
2. **Lookback 기간 짧음**: `wowtale_collector.py`나 `yahoo_finance_collector.py`에서 RSS/API 조회 시 기본 30일만 확인
3. **야후 파이낸스 Ticker 미전체 수집**: 설정된 16개 ETF 중 일부만 실제 호출됨

#### Economic Flow 영향도
**중상 (High)** — 시계열 트렌드 분석(월별·분기별 자금 흐름 변화)을 하려면 최소 1년 이상의 데이터 필요. 현재 4.5개월치로는 통계적 유의미성 부족.

#### 구체적 해결 방법

**A. 스케줄러 자동화 (FastAPI + APScheduler 또는 Celery Beat)**

```python
# backend/core/scheduler.py (신규 파일)

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from backend.domain.master.hub.services.bronze_economic_ingest_service import BronzeEconomicIngestService

scheduler = AsyncIOScheduler()

@scheduler.scheduled_job("cron", hour=9, minute=0, id="daily_economic_collect")
async def daily_collection():
    """매일 오전 9시 자동 수집"""
    service = BronzeEconomicIngestService(...)
    
    # Wowtale
    await service.ingest_wowtale_rss(lookback_days=7)
    
    # Yahoo Finance (전체 ETF)
    for ticker in ["QQQ", "SPY", "IWM", "DIA", ...]:  # 16개 전체
        await service.ingest_yahoo_finance(ticker=ticker)
    
    # DART
    await service.ingest_dart(lookback_days=7)

# main.py에서 앱 시작 시 스케줄러 활성화
@app.on_event("startup")
async def startup_scheduler():
    scheduler.start()
```

**B. Yahoo Finance Collector 수정 (16개 ETF 전체 순회)**

```python
# yahoo_finance_collector.py

TICKERS = [
    "QQQ", "SPY", "IWM", "DIA", "EEM", "VWO", "GLD", "SLV",
    "TLT", "AGG", "XLE", "XLF", "XLK", "XLV", "XLI", "XLU"
]

async def collect_all_tickers() -> list[EconomicCollectDto]:
    """16개 ETF 전체 수집"""
    tasks = [collect_ticker(t) for t in TICKERS]
    results = await asyncio.gather(*tasks)
    return [dto for sublist in results for dto in sublist]
```

**C. 과거 데이터 Backfill (일회성 대량 수집)**

```bash
# scripts/backfill_yahoo_finance.py 작성
# 2025-01-01 ~ 현재까지 16개 ETF 전체 일봉 데이터 수집

python backend/scripts/backfill_yahoo_finance.py --start-date 2025-01-01
```

**우선순위**: ⚠️ **P1 (높음)** — 스케줄러는 2주 내 구현, Backfill은 1개월 내 실행

---

### 4. 🟡 **MEDIUM: VC 투자 금액 소스 부재**

#### 문제점
- **현재 데이터**: Wowtale 2건, StartupRecipe 1건 (투자 금액 정보 없음)
- **목표**: "어느 VC가 어느 스타트업에 얼마를 투자했는지" 데이터 확보 (Economic Flow의 핵심)

#### 원인
1. **The VC 수집 중단**: ToS 위반으로 자동 수집 불가
2. **대체 소스 미확보**: 크런치베이스, TheVC 외 합법적 VC 투자 데이터 소스 미탐색

#### Economic Flow 영향도
**중 (Medium)** — 스타트업 생태계 자금 흐름 파악에 중요하나, 정부 예산·공시 데이터로도 일부 보완 가능

#### 구체적 해결 방법

**A. NTIS R&D 과제 데이터로 간접 추정**

- NTIS OpenAPI에서 "정부 R&D 과제 지원금"이 스타트업에 흘러가는 패턴 파악
- 예: "AI 스타트업 A사 → NTIS 과제 5억 원" = 간접적 자금 유입

**B. 크런치베이스 Pro API 또는 PitchBook 검토**

- **크런치베이스**: 유료 API ($500/month), 글로벌 VC 투자 데이터 최고 품질
- **PitchBook**: 금융기관용 데이터베이스, 비싼 편
- **ROI 분석 후 도입 여부 결정** (초기에는 NTIS로 대체 가능)

**C. 뉴스 크롤링 강화 (Platum, 벤처스퀘어 RSS 추가)**

```python
# platum_collector.py (신규)
RSS_URL = "https://platum.kr/feed"
# 제목에서 "시리즈A", "투자 유치", "000억 원" 키워드 추출
```

**우선순위**: 🔵 **P2 (중간)** — NTIS 승인 후 먼저 활용, VC API는 3개월 후 재검토

---

### 5. 🟢 **LOW: MOEF 제목 해시값 문제**

#### 문제점
- **MOEF 2건의 `raw_title`**: `"51e4c8ab...(SHA-256)"` 형태의 해시값
- **원인**: `moef_local_pdf_collector.py`에서 파일 경로를 해싱하여 제목 대신 사용

#### 해결 방법

```python
# moef_local_pdf_collector.py 수정

def _generate_title_from_path(self, file_path: Path) -> str:
    """파일명 그대로 제목으로 사용"""
    return file_path.stem  # "26년 예산안 국회통과★ (1)"
```

**우선순위**: 🟢 **P3 (낮음)** — 2건뿐이라 긴급하지 않음, 다음 유지보수 시 수정

---

### 6. 🟢 **LOW: MSIT R&D 예산 파일 파싱 실패 (3건)**

#### 문제점
- **MSIT RND 3건**: `text_len=0` (HWPX 파일 다운로드 또는 파싱 실패)

#### 해결 방법

```python
# msit_publicinfo_63_collector.py 디버깅 로직 추가

if not parsed_text or len(parsed_text.strip()) < 100:
    logger.error(f"HWPX parsing failed: {url}, file_size={file_size}")
    # 실패한 파일의 raw bytes를 S3나 로컬에 저장하여 수동 분석
```

**우선순위**: 🟢 **P3 (낮음)** — 86건 중 3건 실패는 허용 범위, 로깅 강화 후 모니터링

---

### 7. 🟠 **HIGH: 데이터 다양성(Diversity) 부족 — 편중된 데이터 포트폴리오**

#### 문제점

현재 131건의 데이터는 **정부 → 민간 방향**과 **IT/AI 섹터**에 지나치게 편중되어 있어, 전체 경제 생태계의 자금 흐름을 균형 있게 반영하지 못하고 있습니다.

#### 5가지 다양성 지표 분석

##### A. 📍 **자금 흐름 방향 편중** (Flow Direction Bias)

| 흐름 방향 | 현재 비율 | 대표 소스 | 문제점 |
|-----------|-----------|-----------|--------|
| **정부 → 민간** | ~85% | MSIT (86건), ALIO (25건), MOEF (2건) | 압도적 다수 |
| **민간 → 민간** | ~8% | DART M&A (일부) | VC 투자 데이터 전무 |
| **해외 → 국내** | ~4% | Yahoo Finance (5건) | ETF 시장 데이터만, 외국인 직접투자(FDI) 없음 |
| **국내 → 해외** | 0% | 없음 | 한국 기업의 해외 투자·M&A 데이터 부재 |

**영향도**: 🔴 **Critical** — 민간 투자(VC, PE)와 글로벌 자본 이동이 보이지 않아 "정부 주도 경제"로만 보이는 착시 발생

##### B. 🏭 **산업 섹터 편중** (Industry Sector Bias)

| 산업 분야 | 현재 비율 | 대표 소스 | 커버리지 |
|-----------|-----------|-----------|----------|
| **IT/AI/소프트웨어** | ~70% | MSIT 보도자료·공고 | ✅ 충분 |
| **제조업** | ~5% | DART 시설투자 일부 | ⚠️ 부족 (반도체, 자동차, 철강 등 빠짐) |
| **바이오/헬스케어** | ~2% | DART 일부 | ❌ 거의 없음 |
| **금융** | ~4% | Yahoo ETF | ⚠️ 금융기관 투자 데이터 없음 |
| **에너지/환경** | 0% | 없음 | ❌ 없음 (ESG 투자 트렌드 반영 불가) |
| **건설/부동산** | ~3% | ALIO 일부 | ⚠️ 부족 |
| **유통/서비스** | 0% | 없음 | ❌ 없음 |

**영향도**: 🔴 **High** — 경제 전반을 보지 못하고 "과기부 중심" 시각만 제공

##### C. 🏢 **기업 규모 편중** (Company Size Bias)

| 기업 규모 | 현재 비율 | 대표 소스 | 문제점 |
|-----------|-----------|-----------|--------|
| **대기업** | ~25% | DART 상장사 | 일부 커버 |
| **공공기관** | ~20% | ALIO | 일부 커버 |
| **중견기업** | ~5% | DART 일부 | ⚠️ 부족 |
| **스타트업** | ~2% | Wowtale (2건) | ❌ 거의 없음 |
| **중소기업/소상공인** | 0% | 없음 | ❌ 없음 |

**영향도**: 🟡 **Medium** — 플랫폼 타겟 유저가 스타트업인데, 정작 스타트업 관련 자금 흐름 데이터가 거의 없음

##### D. 🗺️ **지역 편중** (Geographic Bias)

| 지역 | 현재 비율 | 문제점 |
|------|-----------|--------|
| **중앙정부/수도권** | ~95% | 과기부, 기재부, 상장사 중심 |
| **지방/지역** | ~5% | MOEF 지역 예산 포함되나 상세 분석 없음 |

**영향도**: 🟡 **Medium** — 지역별 자금 흐름 비교 불가 (예: "부산 AI 산업 vs 대전 바이오")

##### E. 📊 **데이터 유형 편중** (Data Type Bias)

| 데이터 유형 | 현재 비율 | 대표 소스 | 한계 |
|-------------|-----------|-----------|------|
| **공식 공시/공고** | ~90% | DART, MSIT, ALIO | 사후적(Lagging) 지표 |
| **뉴스/언론 보도** | ~2% | Wowtale (2건) | ⚠️ 부족 — 시장 반응·여론 파악 불가 |
| **시장 데이터** | ~4% | Yahoo (5건) | ⚠️ 부족 — 실시간 가격·거래량 없음 |
| **SNS/커뮤니티** | 0% | 없음 | ❌ 없음 — 투자자 심리·트렌드 신호 부재 |
| **전문 리포트** | 0% | 없음 | ❌ 없음 — 산업 분석·전망 부재 |

**영향도**: 🟡 **Medium-High** — 선행 지표(Leading Indicator) 부족으로 미래 예측력 약함

---

#### 구체적 해결 방법

##### **Phase 1: 민간 투자 데이터 확보 (VC/PE)**

**A. 국내 VC 뉴스 소스 추가**

```python
# platum_collector.py (신규)
RSS_FEEDS = [
    "https://platum.kr/feed",              # 플래텀
    "https://www.venturesquare.net/feed",  # 벤처스퀘어
    "https://www.thestartupbible.com/feed" # 스타트업 바이블
]

# NLP로 투자 금액 추출
# 예: "○○스타트업, 시리즈A 50억 원 투자 유치" 
#     → investment_amount=5000000000
```

**B. 금융위원회 사모펀드 공시 크롤링**

- URL: https://dis.fss.or.kr/ (금융감독원 전자공시)
- 타겟: "사모펀드 결성·운용 보고서" (분기별)
- 효과: PE/VC 펀드 규모, 투자처 일부 공개 정보 확보

##### **Phase 2~3: 두 축 통합 데이터 전략 — "돈의 흐름" + "산업 트렌드"**

> **⚠️ 전략 재정의 (CRITICAL)**: 단일 데이터 소스로는 경제 생태계를 입체적으로 파악할 수 없습니다.
> 데이터 소스를 **목적에 따라 두 축으로 분리** 하여 수집·관리합니다:
>
> | 축 | 목적 | 답할 수 있는 질문 | 데이터 특성 | 대표 소스 |
> |----|------|-------------------|------------|----------|
> | **🥇 핵심축** | "돈의 흐름" (정량) | "어디로 얼마가 흘러갔나?" | 금액·지급주체·수혜자 필수 | NTIS, KONEPS, DART, 보조금24, BOK ECOS, 사모펀드 공시 |
> | **🥈 보조축** | "산업 트렌드" (정성) | "어느 산업이 뜨고 있나? 왜?" | 정책 발표·인허가·동향 | 22개 부처 보도자료·공고 |
>
> **두 축의 결합 효과**:
> - 핵심축만 있으면 → "돈이 흐른다는 사실만 알고 **WHY를 모름**"
> - 보조축만 있으면 → "정책은 알지만 **실제 자금 집행 여부 모름**"
> - **두 축 결합** → "정책 신호(MFDS 신약 허가) → 자금 집행(NTIS R&D 예산) → 시장 반응(DART 증자)" 의 **완전한 자본 흐름 추적**

---

###### **🥇 P0: "돈의 흐름" 핵심 데이터 6대 소스 (정량 — 금액 명시 필수)**

이 6개 소스는 **누가 → 누구에게 → 얼마를** 지급했는지가 명확히 기록되는, 진짜 자본 흐름 데이터입니다.

| # | 데이터 소스 | URL/API | 자금 흐름 유형 | 산업 커버리지 | 예상 월간 데이터 |
|---|-------------|---------|---------------|--------------|-----------------|
| 1 | **NTIS R&D 통합** ⏳신청중 | api.ntis.go.kr | 정부 → 민간 (R&D 과제비) | **전 부처 통합** (바이오/제조/에너지/AI 등) | **5,000건+** |
| 2 | **KONEPS 나라장터** ⏳추가예정 | apis.data.go.kr/1230000 | 정부 → 민간 (조달·발주) | **전 산업** (건설/IT/제조/용역) | **10,000건+** |
| 3 | **보조금24 통합조회** ⏳신규 | gov24.go.kr/api | 정부 → 기업/개인 (보조금) | **전 산업** (창업/R&D/시설/고용) | **2,000건+** |
| 4 | **DART 공시 (상세 파싱)** ✅구축 | opendart.fss.or.kr | 민간 ↔ 민간 (M&A/투자/증자) | 상장사 전체 | **500건+** |
| 5 | **한국은행 ECOS API** ⏳신규 | ecos.bok.or.kr/api | 거시 자금 흐름 (FDI/통화량) | 거시 경제 (선행지표) | **100건+** |
| 6 | **금감원 사모펀드 공시** ⏳신규 | dis.fss.or.kr | 민간 → 민간 (PE/VC) | 금융/투자 | **50건+** |

**합계 예상치**: 월간 **17,500건** 이상 — 현재 131건/4.5개월의 **600배 증가**

**왜 이 6개인가?**
- ✅ **금액 필드 존재**: 모든 소스에 `금액·예산·계약금액` 컬럼이 명시되어 있음
- ✅ **지급 주체·수혜자 명확**: A 기관이 B 기업에 얼마를 지급했는지 추적 가능
- ✅ **통합 API 제공**: 부처별 개별 크롤링 불필요 (NTIS가 모든 부처 R&D 통합, KONEPS가 모든 발주 통합)
- ✅ **ROI 최고**: 6개 연동만으로 전 부처 자금 흐름 80%+ 커버

---

###### **🥈 P1~P2: 산업 트렌드 시그널 (보조축 — 보도자료·정책 발표)**

> 보도자료는 "**돈의 흐름**" 보다 "**산업 트렌드**" 신호로 활용합니다.
> 따라서 **22개 부처 전체 크롤링이 아니라, 핵심 4개만 선별** 합니다.

| 부처/기관 | URL | 활용 목적 | 우선순위 | 비고 |
|-----------|-----|----------|---------|------|
| **한국은행 (BOK)** | bok.or.kr/portal/bbs/B0000220 | 통화·금리 정책 → **선행 자금 흐름 신호** | 🔴 P1 | 월 15건 |
| **금융위 (FSC)** | fsc.go.kr/no010101 | 금융 규제 변경 → 자본 시장 영향 | 🟡 P2 | 월 25건 |
| **산업통상자원부 (MOTIE)** | motie.go.kr | 산업정책 → 제조업 자금 방향성 | 🟡 P2 | 월 40건 |
| **보건복지부 (MOHW)** | mohw.go.kr | 바이오 정책 → 헬스케어 투자 신호 | 🟡 P2 | 월 25건 |

**나머지 18개 부처 보도자료**: ❌ **수집 보류** (KONEPS·NTIS가 실제 자금 데이터 흡수, 보도자료는 노이즈)

---

###### **🎯 산업 분류는 "수집 시 매칭"이 아니라 "수집 후 태깅"**

부처별로 크롤러를 22개 만드는 대신, **6개 핵심 소스에서 수집한 데이터에 산업 태그를 자동 부여**:

```python
# NTIS R&D 과제 1건 예시 (이미 산업 분류 필드 포함됨)
{
  "title": "AI 기반 신약 후보물질 발굴 플랫폼 개발",
  "funder": "보건복지부",          # → 산업: BIO 자동 추론
  "recipient": "○○바이오테크",
  "amount_krw": 1_500_000_000,
  "ntis_research_field": "LS-바이오의료",  # 🟢 NTIS가 이미 산업 분류 제공
}

# KONEPS 입찰 1건 예시
{
  "title": "스마트팩토리 자동화 시스템 구축 용역",
  "buyer": "한국전력공사",
  "winner": "○○SI",
  "contract_amount": 5_000_000_000,
  "industry_code_g2b": "81111811",  # 🟢 KONEPS 산업분류 코드
}
```

→ **NTIS·KONEPS·DART는 이미 산업 코드를 제공**하므로 별도 분류 작업 불필요

---

**예상 효과 (재정의)**:
- ❌ ~~비IT 섹터 데이터 30% → 60%~~ (보도자료 늘려서 달성하는 건 의미 없음)
- ✅ **금액(amount) 채워진 비율**: 0% → **90%+** (P0 6개 소스 모두 금액 필드 존재)
- ✅ **월간 정량 자금 흐름 데이터**: 131건/4.5개월 → **17,500건/월**
- ✅ **산업 자동 분류**: NTIS/KONEPS 코드 활용 → 추가 NLP 작업 최소화

###### **🛠️ 구현 우선순위 — 6대 핵심 소스 통합 로드맵**

| Phase | 작업 | 자금 흐름 유형 | 공수 | 효과 |
|-------|------|---------------|------|------|
| **Phase 2-1** | NTIS API 연동 (승인 대기 중) | 정부 → 민간 (R&D) | 5일 | **전 부처 R&D 자금 흐름 통합** (월 5,000건+) |
| **Phase 2-2** | KONEPS 나라장터 API 연동 | 정부 → 민간 (조달) | 4일 | **정부 발주·조달 자금 흐름** (월 10,000건+) |
| **Phase 2-3** | DART 상세 파싱 (P0 1번 참고) | 민간 ↔ 민간 (M&A) | 3일 | M&A·증자·시설투자 금액 채우기 |
| **Phase 2-4** | 보조금24 OpenAPI 연동 | 정부 → 기업/개인 | 3일 | 보조금 지급 데이터 (월 2,000건+) |
| **Phase 2-5** | 한국은행 ECOS API | 거시 자금 흐름 | 2일 | 통화량·FDI·금리 시계열 |
| **Phase 2-6** | 금감원 사모펀드 분기 공시 | 민간 → 민간 (PE/VC) | 3일 | PE/VC 펀드 결성·운용 보고 |

**총 공수**: 약 **20일** (1개월 내) — 보도자료 22개 크롤러 만드는 것보다 **훨씬 적은 공수로 600배 데이터 확보**

###### **🥈 보조축: 산업 트렌드 시그널 — 22개 부처·기관 매트릭스 (정성 데이터)**

> **목적 명확화**: 이 매트릭스는 "돈의 흐름"이 아니라 **"산업 트렌드·정책 방향성"** 파악용입니다.
> - 6대 핵심 소스 = **금액·자금 이동** (정량) — Q1: "어디로 돈이 흘러갔나?"
> - 22개 부처 매트릭스 = **정책·시장 신호** (정성) — Q2: "어느 산업이 뜨고 있나?"
>
> 두 축이 결합되면 "**돈이 흐르기 전 정부 정책 신호**" → "**실제 자금 집행**" 추적이 가능합니다.

###### **📊 산업 분야별 정부 부처·기관 매트릭스 (트렌드 시그널용)**

| 산업 분야 | 주관 부처/기관 | 핵심 데이터 소스 URL | 트렌드 신호 가치 | 우선순위 | 예상 월간 |
|-----------|----------------|---------------------|-----------------|---------|----------|
| **🧬 바이오/헬스케어** | 보건복지부 (MOHW) | mohw.go.kr/board.es?mid=a10503000000 | 바이오 R&D·의료 정책 방향 | 🔴 P0 | 25건 |
| | 식품의약품안전처 (MFDS) | mfds.go.kr/brd/m_99/list.do | **신약 허가·임상승인** (강력한 선행 시그널) | 🔴 P0 | 50건 |
| | 한국보건산업진흥원 (KHIDI) | khidi.or.kr/board/list?menuId=MENU00100 | 헬스 산업 동향 보고서 | 🟡 P1 | 10건 |
| **🏭 제조업 (반도체/자동차)** | 산업통상자원부 (MOTIE) | motie.go.kr | 산업 정책·수출입 동향 | 🔴 P0 | 40건 |
| | 한국산업기술진흥원 (KIAT) | kiat.or.kr | 산업 R&D 우선순위 발표 | 🟡 P1 | 15건 |
| **🎬 문화/콘텐츠/게임** | 문화체육관광부 (MCST) | mcst.go.kr/kor/s_notice/press/pressList.jsp | K-콘텐츠 수출 지원 정책 | 🔴 P0 | 30건 |
| | 한국콘텐츠진흥원 (KOCCA) | kocca.kr/cop/bbs/list/B0000150.do | 게임·웹툰·드라마 지원 사업 공고 | 🔴 P0 | 20건 |
| | 한국문화예술위원회 | arko.or.kr/board/list/2495 | 예술 분야 지원 | 🔵 P2 | 10건 |
| **💰 금융/통화** | 한국은행 (BOK) | bok.or.kr/portal/bbs/B0000220 | **금리·통화정책** (가장 강력한 거시 신호) | 🔴 P0 | 15건 |
| | 금융위원회 (FSC) | fsc.go.kr/no010101 | 금융 규제 변경 → 자본 시장 영향 | 🟡 P1 | 25건 |
| | 금융감독원 (FSS) | fss.or.kr/fss/bbs/B0000188/list.do | 금융 감독 정책 | 🟡 P1 | 30건 |
| **⚡ 에너지/환경/ESG** | 환경부 (ME) | me.go.kr/home/web/board/list.do?menuId=10525 | 탄소중립·녹색금융 정책 | 🟡 P1 | 20건 |
| | 한국에너지공단 | energy.or.kr/front/board/List7.do?board_id=4 | 재생에너지 지원 사업 | 🟡 P1 | 15건 |
| | 한국전력공사 (KEPCO) | home.kepco.co.kr/kepco/PR/list.do | 전력 인프라 투자 동향 | 🔵 P2 | 5건 |
| **🏗️ 건설/부동산/SOC** | 국토교통부 (MOLIT) | molit.go.kr/USR/NEWS/m_71/lst.jsp | 부동산·SOC 정책 (시장 영향 큼) | 🟡 P1 | 30건 |
| | 한국토지주택공사 (LH) | lh.or.kr/contents/cont.do?sCode=user&mPid=145 | 주택 공급 계획 | 🔵 P2 | 15건 |
| **🌾 농업/식품** | 농림축산식품부 (MAFRA) | mafra.go.kr/home/5108/subview.do | 농식품 산업 지원 | 🔵 P2 | 20건 |
| | 농업기술실용화재단 (FACT) | fact.or.kr/board.do?menuPos=15 | 농업 R&D 사업화 | 🔵 P2 | 5건 |
| **🚢 해양/수산** | 해양수산부 (MOF) | mof.go.kr/article/list.do?menuKey=370 | 해양 산업·조선업 정책 | 🔵 P2 | 15건 |
| **🛡️ 국방/방산** | 방위사업청 (DAPA) | dapa.go.kr/dapa/na/ntt/selectNttList.do | 방산 수주 동향 (수출 호황 산업) | 🔵 P2 | 20건 |
| **🎓 교육/HR** | 교육부 (MOE) | moe.go.kr/boardCnts/listRenew.do?boardID=294 | 인재 양성 정책 | 🔵 P2 | 15건 |
| | 고용노동부 (MOEL) | moel.go.kr/news/notice/noticeList.do | 노동 시장·일자리 정책 | 🔵 P2 | 10건 |
| **🚗 중소·벤처기업** | 중소벤처기업부 (MSS) | ✅ 이미 SMES OpenAPI 연동 중 | 스타트업 지원 사업 공고 | ✅ 완료 | 50건+ |

**총 합계**: 약 **460건/월** (22개 기관)

###### **🎯 우선순위 분류 — 신호 강도 기준**

| 우선순위 | 기관 수 | 선정 기준 | 1차 구현 시점 |
|---------|--------|----------|--------------|
| 🔴 **P0 (필수)** | 7개 | 시장 즉시 반응하는 강력한 신호 (BOK 금리, MFDS 신약허가, KOCCA K-콘텐츠 등) | Phase 3 즉시 |
| 🟡 **P1 (선별)** | 8개 | 산업별 핵심 정책 발표 (FSC 규제, ME 탄소중립, MOLIT 부동산 등) | Phase 3 후반 |
| 🔵 **P2 (확장)** | 7개 | 트렌드 분석용 사후 수집 (농업·해양·국방·교육) | Phase 4 |

###### **🛠️ 구현 전략 — `GovtPressCollector` 범용 크롤러 (MSIT 패턴 재활용)**

```python
# backend/domain/master/hub/services/collectors/economic/govt_press_collector.py (신규)

from dataclasses import dataclass
from .msit_bbs_collector import MSITStaticTableListStrategy, BoardConfig

@dataclass(frozen=True)
class GovtBoardConfig(BoardConfig):
    ministry_code: str          # "BOK", "MFDS", "MOTIE", ...
    industry_sector: str        # "FINANCE", "BIO", "MANUFACTURING", ...
    signal_priority: str        # "P0", "P1", "P2"

# 22개 부처 보드 선언적 정의
GOVT_BOARDS_P0 = [
    GovtBoardConfig(source_type="GOVT_BOK_POLICY",   ministry_code="BOK",   industry_sector="FINANCE",       signal_priority="P0", ...),
    GovtBoardConfig(source_type="GOVT_MFDS_APPROVAL", ministry_code="MFDS", industry_sector="BIO",           signal_priority="P0", ...),
    GovtBoardConfig(source_type="GOVT_MOTIE_PRESS",   ministry_code="MOTIE", industry_sector="MANUFACTURING", signal_priority="P0", ...),
    GovtBoardConfig(source_type="GOVT_MOHW_PRESS",    ministry_code="MOHW", industry_sector="BIO",           signal_priority="P0", ...),
    GovtBoardConfig(source_type="GOVT_MCST_PRESS",    ministry_code="MCST", industry_sector="CONTENT",       signal_priority="P0", ...),
    GovtBoardConfig(source_type="GOVT_KOCCA_NOTICE",  ministry_code="KOCCA", industry_sector="CONTENT",      signal_priority="P0", ...),
    GovtBoardConfig(source_type="GOVT_KHIDI_NOTICE",  ministry_code="KHIDI", industry_sector="BIO",          signal_priority="P0", ...),
]

GOVT_BOARDS_P1 = [
    # 환경부, 에너지공단, FSC, FSS, KIAT, MOLIT 등 8개
    GovtBoardConfig(source_type="GOVT_ME_PRESS",     ministry_code="ME",    industry_sector="ENERGY",       signal_priority="P1", ...),
    GovtBoardConfig(source_type="GOVT_FSC_POLICY",   ministry_code="FSC",   industry_sector="FINANCE",      signal_priority="P1", ...),
    GovtBoardConfig(source_type="GOVT_MOLIT_PRESS",  ministry_code="MOLIT", industry_sector="CONSTRUCTION", signal_priority="P1", ...),
    # ...
]

GOVT_BOARDS_P2 = [
    # 농업·해양·국방·교육·LH·KEPCO 등 7개
    GovtBoardConfig(source_type="GOVT_MAFRA_PRESS",  ministry_code="MAFRA", industry_sector="AGRICULTURE",  signal_priority="P2", ...),
    GovtBoardConfig(source_type="GOVT_MOF_PRESS",    ministry_code="MOF",   industry_sector="MARITIME",     signal_priority="P2", ...),
    GovtBoardConfig(source_type="GOVT_DAPA_NOTICE",  ministry_code="DAPA",  industry_sector="DEFENSE",      signal_priority="P2", ...),
    # ...
]

class GovtPressCollector:
    """범용 정부 부처 보도자료 크롤러 — 트렌드 시그널 전용"""
    
    async def collect_by_priority(self, priority: str = "P0") -> list[EconomicCollectDto]:
        boards = {"P0": GOVT_BOARDS_P0, "P1": GOVT_BOARDS_P1, "P2": GOVT_BOARDS_P2}[priority]
        tasks = [self._collect_board(b) for b in boards]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return [dto for sublist in results for dto in sublist if not isinstance(sublist, Exception)]
    
    def _to_dto(self, row: dict, board: GovtBoardConfig) -> EconomicCollectDto:
        return EconomicCollectDto(
            source_type=board.source_type,           # 예: "GOVT_BOK_POLICY"
            raw_title=row["title"],
            published_at=row["date"],
            investment_amount=None,                  # 🟢 트렌드 신호이므로 금액 없음 (의도적)
            raw_metadata={
                "ministry": board.ministry_code,
                "industry_sector": board.industry_sector,   # 🟢 산업 태깅
                "signal_priority": board.signal_priority,   # 🟢 신호 강도
                "data_role": "TREND_SIGNAL",                # 🟢 데이터 역할 명시
                **row,
            },
        )
```

###### **🔬 트렌드 시그널과 자금 흐름 결합 활용 (Cross-Analysis)**

| 분석 시나리오 | 사용 데이터 | 인사이트 |
|---------------|------------|---------|
| **"바이오 산업이 뜨고 있나?"** | MFDS 신약 허가 추이 (트렌드) + NTIS 바이오 R&D 예산 (자금) | 정책 신호 → 실제 자금 집행 연결 |
| **"K-콘텐츠 정부 지원 규모는?"** | MCST/KOCCA 보도자료 (트렌드) + KONEPS 콘텐츠 발주 (자금) | 정책 발표 후 실제 발주 변화 추적 |
| **"금리 인상 후 자금 흐름 변화"** | BOK 통화정책 보도자료 (트렌드) + DART 증자·M&A (자금) | 거시 신호 → 민간 자본 반응 측정 |
| **"탄소중립 정책 실효성"** | 환경부 보도자료 (트렌드) + NTIS 친환경 R&D 과제비 (자금) | 정책 → 예산 연결 검증 |

**핵심**: 22개 매트릭스가 없으면 "**돈만 흐르고 왜 흐르는지 모름**" → 트렌드 시그널이 **WHY**를 채워줌

###### **📈 트렌드 시그널만의 고유 가치**

| 가치 | 설명 | 예시 |
|------|------|------|
| **선행 지표** | 정책 발표 → 3~6개월 후 자금 집행 → 시장 변화 | "AI 반도체 육성 발표" → "예산 5조 편성" → "삼성·SK 투자 가속" |
| **산업 전환 신호** | 부처별 정책 변화로 산업 패러다임 시프트 감지 | 환경부 "탄소세 도입" = 에너지 산업 재편 신호 |
| **수출입 동향** | MOTIE·관세청 등 무역 데이터로 산업 경쟁력 변화 추적 | "반도체 수출 30% 감소" → 시장 위축 신호 |
| **인허가 시그널** | MFDS 신약 허가 = 바이오 기업 가치 평가의 핵심 이벤트 | 신약 임상 3상 통과 → 주가 +50% |

###### **📊 산업 분류는 "수집 후 태깅"으로 처리**

NTIS/KONEPS/DART는 이미 산업 코드를 제공하므로, 추가 NLP 작업은 보조축(보도자료, 뉴스)에만 적용:

```python
# backend/domain/master/hub/services/classifiers/industry_classifier.py (보조 분류기)

INDUSTRY_KEYWORDS = {
    "BIO": ["바이오", "제약", "신약", "임상", "백신"],
    "SEMICONDUCTOR": ["반도체", "메모리", "파운드리", "DRAM"],
    "AUTOMOTIVE": ["자동차", "전기차", "EV", "배터리"],
    "ENERGY": ["태양광", "풍력", "수소", "ESG"],
    "AI": ["AI", "인공지능", "LLM", "생성형"],
    "FINANCE": ["은행", "증권", "핀테크"],
    "CONSTRUCTION": ["건설", "부동산", "SOC"],
    "CONTENT": ["콘텐츠", "게임", "K-팝", "OTT"],
}

def classify_industry(title: str, content: str = "") -> list[str]:
    """보도자료·뉴스 등 산업 코드가 없는 데이터에만 적용"""
    text = f"{title} {content}".lower()
    return [k for k, kws in INDUSTRY_KEYWORDS.items() if any(kw.lower() in text for kw in kws)] or ["UNCLASSIFIED"]
```

→ **NTIS·KONEPS·DART는 이미 산업 코드 제공** 하므로 자동 매핑 (분류기 불필요)
→ **보도자료·뉴스·SNS** 등 비정형 텍스트에만 분류기 적용

---

**A. 한국거래소(KRX) 산업별 공시 필터링**

```python
# dart_collector.py 확장
SECTOR_FILTERS = {
    "PHARMA": ["바이오", "제약", "의료기기"],
    "MANUFACTURING": ["반도체", "디스플레이", "자동차", "철강"],
    "ENERGY": ["태양광", "풍력", "수소", "ESG"],
}

# DART API에 산업 코드 필터 추가
params["corp_cls"] = "Y"  # 유가증권 상장법인만
```

**B. 산업통상자원부(MOTIE) 에너지·제조 예산 크롤링**

- MSIT 크롤러 패턴 재활용
- 타겟 URL: https://www.motie.go.kr/motie/gov3.0/gov_openinfo/sajun/bbs/bbsView.do?bbs_cd_n=2

##### **Phase 3: 글로벌 자본 이동 추적 (FDI)**

**A. 한국은행 국제수지 통계 OpenAPI**

```python
# bok_fdi_collector.py (신규)
# 한국은행 경제통계시스템 API
# https://ecos.bok.or.kr/api/
# 외국인직접투자(FDI) 월별 데이터
```

**B. KOTRA 해외투자통계 크롤링**

- 한국 기업의 해외 진출·투자 데이터
- URL: https://www.kotra.or.kr/kh/about/KHMINC010M.html

##### **Phase 4: 선행 지표 확보 (뉴스·SNS·리포트)**

**A. 네이버 금융 뉴스 크롤링**

```python
# naver_finance_news_collector.py
# 타겟: "투자", "M&A", "IPO" 키워드 뉴스
# 효과: DART 공시 전 언론 보도로 선행 신호 포착
```

**B. 한국투자증권·미래에셋 산업 리포트 RSS**

- 증권사 리서치 센터의 무료 공개 리포트
- "반도체 업황", "바이오 투자 전망" 등 전문가 의견

**C. Reddit/Twitter 투자 커뮤니티 감성 분석 (장기)**

- r/koreainvest, #한국스타트업 해시태그
- 감성 점수로 투자 심리 지수 산출

---

#### 다양성 확보 목표 (3개월 후)

| 다양성 지표 | 현재 | 목표 | 측정 방법 |
|-------------|------|------|-----------|
| **자금 흐름 방향** | 정부→민간 85% | 정부→민간 60%, 민간→민간 30% | `investor_name` 분류 |
| **산업 섹터** | IT 70% | IT 40%, 제조 20%, 바이오 15%, 기타 25% | `raw_metadata.sector` 태깅 |
| **기업 규모** | 대기업+공공 45% | 대기업 20%, 스타트업 30%, 중소 30% | `investor_name` 규모 분류 |
| **데이터 유형** | 공시 90% | 공시 50%, 뉴스 30%, 시장 15%, SNS 5% | `source_type` 접두사 |

**우선순위**: 🟠 **P1 (높음)** — 민간 투자(VC) 소스는 2주 내, 산업 다변화는 1개월 내

---

## 🎯 통합 실행 계획 (우선순위별 Roadmap)

### Phase 1: 긴급 패치 (1~2주 내)

| Task | 담당 | 예상 공수 | 완료 조건 |
|------|------|-----------|-----------|
| **DART 상세 파싱 구현** | Backend | 3일 | `investment_amount` None 비율 < 5% |
| **ALIO 예산·날짜 매핑 수정** | Backend | 1일 | `budget_krw` None 비율 < 10% |
| **스케줄러 기본 구조 구축** | Backend | 2일 | 일 1회 자동 수집 확인 |

### Phase 2: "돈의 흐름" 6대 핵심 소스 통합 (1개월 내)

> **핵심 원칙**: 부처별 보도자료 크롤러를 늘리는 대신, **금액·지급주체·수혜자가 명시된 정량 소스 6개** 우선 연동

| Task | 담당 | 예상 공수 | 완료 조건 |
|------|------|-----------|-----------|
| **🥇 NTIS R&D API 통합 (P0)** | Backend | 5일 | R&D 과제 5,000건 이상 (금액 채움률 95%+) |
| **🥇 KONEPS 나라장터 API 통합 (P0)** | Backend | 4일 | 입찰·낙찰 10,000건 이상 (계약금액 필수) |
| **🥇 보조금24 OpenAPI 연동 (P0)** | Backend | 3일 | 보조금 지급 2,000건 이상 |
| **🥇 한국은행 ECOS API (P0)** | Backend | 2일 | 거시 통화·FDI 시계열 |
| **🥇 금감원 사모펀드 분기 공시 (P0)** | Backend | 3일 | PE/VC 펀드 결성 정보 |
| **Yahoo Finance Backfill** | Backend | 1일 | 16개 ETF × 365일 = 5,840건 |
| **VC 뉴스 크롤링 (Platum/벤처스퀘어)** | Backend | 2일 | 주 20건 (투자 금액 NLP 추출 70%+) |
| **산업 자동 분류기 (보조축용)** | Backend | 1일 | 보도자료/뉴스에만 적용 |

### Phase 3: 트렌드 시그널 보조축 (산업 트렌드 파악 — 22개 부처 매트릭스, 3개월 내)

> 6대 핵심 소스가 "**돈의 흐름 (정량)**"이라면, 22개 부처 매트릭스는 "**산업 트렌드 (정성)**"입니다.
> 두 축이 결합되면 **정책 신호 → 자금 집행 → 시장 반응** 의 완전한 추적이 가능합니다.

| Task | 담당 | 예상 공수 | 완료 조건 |
|------|------|-----------|-----------|
| **🛠️ `GovtPressCollector` 범용 크롤러 구축** | Backend | 3일 | MSIT 패턴 재활용, 선언적 보드 정의 |
| **🥈 P0: 트렌드 핵심 7개 부처 (BOK/MFDS/MOHW/MOTIE/MCST/KOCCA/KHIDI)** | Backend | 4일 | 강력한 선행 신호 월 200건 |
| **🥈 P1: 산업 정책 8개 부처 (FSC/FSS/ME/에너지공단/KIAT/MOLIT 등)** | Backend | 3일 | 산업별 정책 트렌드 월 130건 |
| **🥈 P2: 확장 7개 부처 (MAFRA/MOF/DAPA/LH/MOE/MOEL 등)** | Backend | 3일 | 트렌드 분석 보완 월 130건 |
| **🔬 Cross-Analysis 뷰 구축** | Backend+Data | 3일 | "정책 발표 → 실제 자금 집행" 시계열 매칭 |
| **산업 자동 분류기 (보조축용)** | Backend | 1일 | 8개 산업 태그 (보도자료 분류) |
| **크런치베이스 API 검토** | Product | 3일 | ROI 분석 보고서 작성 |
| **네이버 금융 뉴스 크롤링** | Backend | 2일 | 일 30건 (선행 지표용) |
| **KOTRA 해외투자 통계** | Backend | 2일 | 국내→해외 자본 이동 데이터 |
| **산업 태그 정교화 (GICS 매핑)** | Backend | 2일 | NTIS/KONEPS 코드 → GICS 24개 표준 매핑 |
| **데이터 품질 대시보드 구축** | Backend+Frontend | 5일 | Grafana/Superset + 산업별·자금흐름별 차트 |

**트렌드 시그널 예상 효과**:
- 산업 트렌드 데이터: 0건 → **월 460건+**
- IT 편중 해소: 현재 70% → **목표 IT 40% + 비IT 60%**
- 데이터 역할 명확화: 6대 정량 + 22개 정성 = 입체적 분석 가능

---

## 📊 성공 지표 (KPI)

### 정량적 목표 (3개월 후)

| 지표 | 현재 | 목표 |
|------|------|------|
| **총 레코드 수** | 131건 | 10,000건 이상 |
| **`investment_amount` 채워진 비율** | 0% (DART), 0% (ALIO) | 80% 이상 |
| **시계열 기간** | 4.5개월 | 12개월 이상 |
| **일평균 신규 수집 건수** | 0건 (수동 실행) | 50건 이상 (자동화) |
| **데이터 소스 다양성** | 7개 | 10개 이상 (NTIS, Platum 등 추가) |
| **🆕 민간 투자(VC/PE) 비율** | ~2% (Wowtale 2건) | 30% 이상 |
| **🆕 비IT 산업 섹터 비율** | ~30% | 60% 이상 (제조, 바이오, 에너지 등) |
| **🆕 스타트업 관련 데이터 비율** | ~2% | 25% 이상 |
| **🆕 선행 지표(뉴스·SNS) 비율** | ~2% | 20% 이상 |

### 정성적 목표

- ✅ **"이번 분기 AI 분야에 정부 예산이 얼마나 투입되었나요?"** 같은 질문에 정량적 답변 가능
- ✅ **"최근 3개월 간 M&A 규모 상위 10건"** 같은 랭킹 쿼리 지원
- ✅ **월별 자금 흐름 차트** 생성 가능 (시계열 데이터 충분)
- 🆕 **"바이오 섹터와 AI 섹터 중 어디에 민간 투자가 더 많이 들어가나요?"** — 산업 간 비교 가능
- 🆕 **"정부 예산 vs VC 투자, 스타트업 자금원 비율은?"** — 자금 흐름 방향 다각화
- 🆕 **"외국인 투자가 가장 많이 들어온 산업은?"** — 글로벌 자본 이동 추적

---

## 🔗 관련 문서

- `DATA_COLLECTION_SOURCES_GUIDE_V3.md`: 전체 데이터 소스 설계
- `DART_ECONOMIC_ENHANCEMENT_STRATEGY.md`: DART 상세 파싱 전략 (작성 예정)
- `ALIO_COLLECTION_STRATEGY.md`: ALIO API 통합 가이드
- `GOVT_DOCS_COLLECTION_STRATEGY.md`: 정부 문서 크롤링 전략

---

## 📝 변경 이력

| 날짜 | 작성자 | 변경 내용 |
|------|--------|-----------|
| 2026-05-13 | System | 초안 작성 (131건 데이터 분석 기반) |
