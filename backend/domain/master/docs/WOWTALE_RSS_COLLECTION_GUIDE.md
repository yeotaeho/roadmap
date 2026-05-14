# Wowtale RSS 기반 경제 데이터 수집 가이드

> **작성일**: 2026-05-11  
> **목적**: Wowtale 스타트업 투자 뉴스 RSS 피드 수집 구현 가이드

---

## 📊 Wowtale 개요

**Wowtale**은 한국 스타트업 투자 뉴스를 가장 빠르게 전달하는 미디어입니다.

- **URL**: https://wowtale.net/
- **RSS 피드**: https://wowtale.net/feed/
- **특징**: WordPress 기반, 표준 RSS 2.0 완벽 지원
- **업데이트 주기**: 실시간 (하루 3~10건)
- **데이터 품질**: 투자 금액, 투자사, 피투자사 정보가 본문에 포함

---

## 🎯 수집 전략

### 1. RSS 피드 구조

Wowtale RSS는 다음과 같은 구조로 제공됩니다:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>와우테일 – 스타트업 & 벤처캐피탈 전문 미디어</title>
    <link>https://wowtale.net</link>
    <description>스타트업 투자 뉴스</description>
    <item>
      <title>카카오벤처스, AI 스타트업 'A사'에 100억 투자</title>
      <link>https://wowtale.net/2026/05/11/...</link>
      <pubDate>Mon, 11 May 2026 09:00:00 +0900</pubDate>
      <description><![CDATA[
        <p>카카오벤처스가 인공지능 스타트업 A사에 100억 원 규모의 시리즈 B 투자를 단독으로 진행했다...</p>
      ]]></description>
      <guid>https://wowtale.net/?p=12345</guid>
    </item>
  </channel>
</rss>
```

### 2. 수집 대상 필드

| RSS 필드 | 매핑 대상 | 비고 |
|---------|----------|------|
| `<title>` | `raw_title` | 헤드라인 (필수) |
| `<link>` | `source_url` | 원문 링크 (필수, 중복 체크 키) |
| `<content:encoded>` (1순위) | `raw_metadata["content_text"]` | 기사 전문 HTML (BS4 정제 후 저장) |
| `<description>` (2순위) | `raw_metadata["content_text"]` 또는 `summary` | 전문이 없을 때 fallback |
| `<pubDate>` / `published_parsed` | `published_at` | UTC → KST(UTC+9) 변환 |
| `<guid>` | `raw_metadata["guid"]` | 고유 식별자 |
| `<category>` | `raw_metadata["tags"]` | 분류·필터링 보조 |

### 3. 노이즈 필터링 (LLM 비용 절감)

Wowtale은 투자 뉴스 외에 행사·인터뷰·정책 일반도 함께 송출합니다. 이를 그대로 적재하면 Silver Layer LLM이 "투자 뉴스 아님"을 판별하느라 토큰을 낭비하므로 **Collector 단에서 사전 차단**합니다.

```python
INVESTMENT_KEYWORDS = (
    "투자", "유치", "라운드", "시리즈", "시드", "프리A",
    "Pre-A", "Pre-IPO", "프리IPO",
    "펀드", "결성",
    "인수", "합병", "M&A",
    "상장", "IPO",
)

# 제목 + 카테고리(tags) 둘 다 검사
def _is_investment_relevant(title: str, tags: list[str]) -> bool:
    haystack = title + " " + " ".join(tags)
    return any(k in haystack for k in INVESTMENT_KEYWORDS)
```

매칭되지 않으면 `continue`로 스킵하고, `logger.info`에 `(노이즈 스킵 N건)`을 함께 출력해 운영 시 가시성을 확보합니다.

### 4. source_type 세분화 전략

대시보드에서 "M&A 추이"와 "초기 투자(Seed/Pre-A) 추이"를 분리해 보고 싶을 때 SQL이 단순해지도록 **제목 매칭 규칙으로 4분류**합니다.

| source_type | 매칭 키워드 | 의미 |
|-------------|-----------|------|
| `WOWTALE_MA` | M&A, 인수, 합병, 인수합병 | 인수합병 |
| `WOWTALE_IPO` | IPO, 상장, Pre-IPO, 프리IPO | 상장 관련 |
| `WOWTALE_FUND` | 펀드, 결성, 펀드결성, 펀드 결성 | 펀드 결성 (LP→GP) |
| `WOWTALE_INVEST` | (그 외 투자 관련) | 일반 투자 라운드 (시드/시리즈) |

> **규칙**: 더 구체적인(긴) 키워드부터 먼저 검사합니다. 예) `"Pre-IPO"`를 `"IPO"` 보다 앞에 두어야 일반 IPO로 잘못 분류되지 않습니다.

### 5. 투자 주체 (`investor_name`) 추출

RSS 본문은 HTML이므로 완벽한 파싱이 어렵습니다. Phase 1에서는:

- **제목에서 간단 추출**: `"A벤처스, B사에 투자"` → `investor_name = "A벤처스"`
- **본문 파싱은 Phase 3로 유예**: BeautifulSoup + LLM 조합으로 정확도 확보

### 6. published_at — KST(UTC+9) 변환

`feedparser`의 `published_parsed`는 **UTC 기준 `time.struct_time`** 입니다. KST 변환을 빼먹으면 DART 때 겪었던 9시간 오프셋 버그가 재현됩니다.

```python
import time
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

KST = timezone(timedelta(hours=9))

def parse_published_at(entry: dict) -> datetime | None:
    # 1순위: published_parsed(UTC struct_time) — 가장 안전
    if pp := entry.get("published_parsed"):
        ts = time.mktime(pp)
        return datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(KST)
    # 2순위: published(RFC 2822 문자열)
    if pub := entry.get("published"):
        dt = parsedate_to_datetime(pub)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(KST)
    return None
```

### 7. 본문 확보 (`content:encoded` 우선)

LLM이 정확한 투자 금액·VC 목록을 뽑으려면 요약본이 아닌 **전문**이 필요합니다. WordPress RSS는 보통 `<content:encoded>`에 전문을 넣어 줍니다.

```python
from bs4 import BeautifulSoup

def extract_html_content(entry: dict) -> str:
    # 1순위: content:encoded (기사 전문)
    if content_list := entry.get("content"):
        try:
            value = content_list[0].get("value") or ""
            if value:
                return value
        except (AttributeError, IndexError, TypeError):
            pass
    # 2순위: summary (요약본)
    return entry.get("summary", "") or ""

clean_text = BeautifulSoup(html, "html.parser").get_text(separator=" ", strip=True)
```

> **만약 Wowtale RSS가 전문을 주지 않는다면**: `entry.link` 로 한 번 더 `aiohttp.get` 후 본문 영역(`div.entry-content` 등)만 BS4 로 긁어오는 **2-Step 크롤링**을 추가합니다. (Phase 2 옵션)

---

## 🛠️ 구현 체크리스트

### Phase 1: RSS 기본 수집 ✅ 완료

- [x] `feedparser`, `beautifulsoup4` 라이브러리 설치 확인 (`requirements.txt`)
- [x] `WowtaleEconomicCollector` 클래스 생성
- [x] RSS 피드 파싱 (`feedparser.parse`)
- [x] 필수 필드 매핑 (`raw_title`, `source_url`, `published_at`)
- [x] **노이즈 필터** (`_is_investment_relevant`)
- [x] **source_type 세분화** (`WOWTALE_MA / IPO / FUND / INVEST`)
- [x] **KST 타임존 변환** (`published_parsed UTC → KST`)
- [x] **`content:encoded` 우선 사용** + `BeautifulSoup` 정제
- [x] 제목 기반 간단 `investor_name` 추출 (정규표현식)
- [x] `BronzeEconomicIngestService.ingest_wowtale()` 메서드 추가
- [x] API 엔드포인트 추가 (`POST /api/master/bronze/economic/wowtale`)
- [x] 통합 테스트 스크립트 작성

### Phase 2: 본문 보강 (필요 시)

- [ ] RSS 전문이 짧을 경우 `aiohttp` 로 본문 페이지 크롤링 (2-Step)
- [ ] 본문 영역(`div.entry-content`) BS4 추출 후 `raw_metadata["content_text"]` 갱신

### Phase 3: LLM 정밀 추출 (Silver Layer)

- [ ] `raw_metadata["content_text"]` 입력으로 투자사·피투자사·금액·라운드 추출
- [ ] `investment_amount`, `target_company_or_fund` 갱신 (`refined_*` 테이블)

---

## 📝 구현 예시 코드

### 1. `WowtaleEconomicCollector` 핵심 로직 (실제 구현 반영)

> 전체 구현은 `backend/domain/master/hub/services/collectors/economic/wowtale_collector.py` 를 직접 참고하세요. 아래는 노이즈 필터·source_type 분류·KST 변환·`content:encoded` 우선 추출 4가지 핵심 패턴만 발췌했습니다.

```python
import re
import time
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import feedparser
from bs4 import BeautifulSoup

KST = timezone(timedelta(hours=9))

INVESTMENT_KEYWORDS = (
    "투자", "유치", "라운드", "시리즈", "시드", "프리A",
    "Pre-A", "Pre-IPO", "프리IPO",
    "펀드", "결성", "인수", "합병", "M&A", "상장", "IPO",
)

SOURCE_TYPE_RULES = (
    ("M&A", "WOWTALE_MA"), ("인수합병", "WOWTALE_MA"),
    ("인수", "WOWTALE_MA"), ("합병", "WOWTALE_MA"),
    ("Pre-IPO", "WOWTALE_IPO"), ("프리IPO", "WOWTALE_IPO"),
    ("IPO", "WOWTALE_IPO"), ("상장", "WOWTALE_IPO"),
    ("펀드 결성", "WOWTALE_FUND"), ("펀드결성", "WOWTALE_FUND"),
    ("결성", "WOWTALE_FUND"), ("펀드", "WOWTALE_FUND"),
)
DEFAULT_SOURCE_TYPE = "WOWTALE_INVEST"


def is_investment_relevant(title: str, tags: list[str]) -> bool:
    haystack = title + " " + " ".join(tags)
    return any(k in haystack for k in INVESTMENT_KEYWORDS)


def classify_source_type(title: str, tags: list[str]) -> str:
    haystack = title + " " + " ".join(tags)
    for keyword, stype in SOURCE_TYPE_RULES:
        if keyword in haystack:
            return stype
    return DEFAULT_SOURCE_TYPE


def parse_published_at(entry: dict) -> datetime | None:
    if pp := entry.get("published_parsed"):
        ts = time.mktime(pp)
        return datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(KST)
    if pub := entry.get("published"):
        dt = parsedate_to_datetime(pub)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(KST)
    return None


def extract_full_text(entry: dict, *, max_len: int = 5000) -> tuple[str, str]:
    """(content_text, content_source) 반환. 1순위 content:encoded, 2순위 summary."""
    html = ""
    source = "summary"
    if content_list := entry.get("content"):
        try:
            value = content_list[0].get("value") or ""
            if value:
                html = value
                source = "content_encoded"
        except (AttributeError, IndexError, TypeError):
            pass
    if not html:
        html = entry.get("summary", "") or ""

    if not html:
        return "", source
    text = BeautifulSoup(html, "html.parser").get_text(separator=" ", strip=True)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_len], source
```

루프 본문은 다음과 같이 4단계로 동작합니다.

```python
for entry in feed.entries[:max_items]:
    title = (entry.get("title") or "").strip()
    link = (entry.get("link") or "").strip()
    tags = [t.term for t in entry.get("tags", []) if getattr(t, "term", None)]

    # 1) 노이즈 필터 (Silver LLM 비용 절감)
    if not title or not link or not is_investment_relevant(title, tags):
        continue

    # 2) source_type 세분화
    source_type = classify_source_type(title, tags)

    # 3) KST 타임존 변환
    published_at = parse_published_at(entry)

    # 4) 본문 우선순위 추출 (content:encoded → summary)
    full_text, content_source = extract_full_text(entry)

    raw_metadata = {
        "guid": entry.get("id", ""),
        "tags": tags,
        "content_text": full_text,
        "content_source": content_source,
    }
    # ... DTO 생성 ...
```

### 2. Service 메서드 추가

```python
# bronze_economic_ingest_service.py

async def ingest_wowtale(self, *, max_items: int = 50) -> dict[str, Any]:
    """Wowtale RSS 피드 수집."""
    from domain.master.hub.services.collectors.economic.wowtale_collector import (
        WowtaleEconomicCollector,
    )

    collector = WowtaleEconomicCollector()
    dtos: list[EconomicCollectDto] = []
    try:
        dtos = await collector.collect(max_items=max_items)
    except Exception:
        logger.exception("Wowtale 경제 Bronze 수집 실패. 빈 결과로 진행합니다.")

    inserted = await self._economic_repo.insert_many_skip_duplicates(dtos)

    result = {
        "source": "wowtale",
        "fetched": len(dtos),
        "inserted": inserted,
        "not_inserted": max(0, len(dtos) - inserted),
    }
    logger.info("Bronze economic Wowtale ingest: %s", result)
    return result
```

### 3. API 엔드포인트 추가

```python
# master_routor.py

@router.post("/bronze/economic/wowtale")
async def run_wowtale_economic_bronze(
    max_items: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Wowtale RSS 피드 기반 스타트업 투자 뉴스 수집."""
    svc = BronzeEconomicIngestService(db, None)
    return await svc.ingest_wowtale(max_items=max_items)
```

---

## 🚀 실행 방법

### 1. 로컬 테스트

```bash
# Wowtale RSS 수집 테스트
curl -X POST "http://localhost:8000/api/master/bronze/economic/wowtale?max_items=10"
```

### 2. 스케줄러 등록 (미래)

```python
# APScheduler 또는 Celery Beat
@scheduler.scheduled_job("cron", hour=3, minute=10)
async def collect_wowtale_daily():
    async with get_db() as db:
        svc = BronzeEconomicIngestService(db, None)
        await svc.ingest_wowtale(max_items=100)
```

---

## 📌 주의사항

### 1. RSS 피드 에티켓

- Wowtale 서버에 부담을 주지 않도록 **1분에 1회 이하** 호출 권장
- 스케줄러는 **새벽 3시 10분** (DART 수집 직후) 권장

### 2. 중복 방지

- `source_url`이 이미 UNIQUE 제약이므로 재수집 시 자동 스킵
- RSS는 최신 50건만 노출하므로, **하루 1~2회** 수집으로 충분

### 3. 데이터 품질

- RSS는 요약문만 제공하므로 **정확한 투자 금액은 Phase 3에서 본문 크롤링 + LLM 추출 필요**
- Phase 1 목표: 뉴스 발생 사실만 빠르게 수집 → Silver Layer에서 정제

---

## 🔗 참고 링크

- Wowtale RSS: https://wowtale.net/feed/
- feedparser 문서: https://feedparser.readthedocs.io/
- RFC 2822 (RSS pubDate): https://www.rfc-editor.org/rfc/rfc2822
- BeautifulSoup (본문 파싱): https://www.crummy.com/software/BeautifulSoup/

---

**다음 단계**: 중소벤처기업부 사업공고 OpenAPI 수집
