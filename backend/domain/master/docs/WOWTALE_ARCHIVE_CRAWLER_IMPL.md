# Wowtale 아카이브 크롤러 구현 전략

> **작성일**: 2026-05-17  
> **구현 파일**: `wowtale_archive_crawler.py` (신규), `bronze_economic_ingest_service.py` (메서드 추가), `master_routor.py` (엔드포인트 추가)  
> **목적**: RSS 최근 50건 한계 돌파 → 1년치 과거 데이터 Backfill

---

## 1. 구현 배경 및 문제 정의

기존 `WowtaleEconomicCollector` (RSS 기반)는 `https://wowtale.net/feed/` 에서
**최근 50건**만 수집한다. Wowtale이 일 3~10건 게시하므로 RSS만으로는
**최근 5~7일치**만 확보할 수 있다.

Roadmap 플랫폼의 Silver Layer LLM이 "돈의 흐름" 트렌드를 분석하려면
**최소 1년치(약 1,000~3,000건)**의 시계열 데이터가 필요하다.

### 해결 전략 선택 이유

| 전략 | 장점 | 단점 | 채택 여부 |
|------|------|------|----------|
| RSS 다중 피드 (카테고리 별) | 간단 | 여전히 최근 50건 한계 | ❌ |
| Sitemap XML 파싱 | URL 전체 취득 가능 | 날짜 정보 없어 필터 불가 | ❌ |
| **카테고리 아카이브 크롤링** | 날짜 순 페이지네이션, 중단점 명확 | HTTP 요청 수 多 | ✅ 채택 |
| Playwright (JS 렌더링) | JavaScript 의존 콘텐츠 처리 | 무거움, WordPress는 불필요 | ❌ |

WordPress의 카테고리 아카이브 페이지(`/category/{slug}/page/{n}/`)는
**날짜 역순**으로 기사를 나열하므로 `from_date` 컷오프를 적용해 조기 종료할 수 있다.

---

## 2. 구현 파일 구조

```
backend/
├── domain/master/hub/services/collectors/economic/
│   └── wowtale_archive_crawler.py          # 신규 — 크롤러 클래스
│
├── domain/master/hub/services/
│   └── bronze_economic_ingest_service.py   # 수정 — ingest_wowtale_archive() 메서드 추가
│
├── api/v1/master/
│   └── master_routor.py                    # 수정 — POST /bronze/economic/wowtale-archive 추가
│
└── scripts/
    ├── wowtale_backfill.py                 # 신규 — CLI Backfill 스크립트
    └── wowtale_archive_integration_test.py # 신규 — 통합 테스트
```

---

## 3. 아키텍처 및 데이터 흐름

```
[API / CLI]
    │  POST /bronze/economic/wowtale-archive (202 비동기)
    │  또는 python scripts/wowtale_backfill.py
    ▼
BronzeEconomicIngestService.ingest_wowtale_archive()
    │  파라미터: max_pages, from_date, categories, fetch_article_body
    ▼
WowtaleArchiveCrawler.crawl_all()
    │  카테고리 순차 순회 (기본: funding → venture-capital → Global-news)
    ▼
crawl_category()  [asyncio.to_thread]
    │
    ├─ [루프] GET /category/{slug}/page/{n}/
    │       _parse_archive_page(html) → list[_ArticleRef], has_next
    │
    └─ [각 기사] _build_dto(ref)
             ├─ skip_article_fetch=False → GET 기사 상세 페이지
             │       _parse_article_page(html) → published_at, body_text
             └─ extract_investment_amount_krw(title + body)
                _classify_source_type(title)
                EconomicCollectDto 생성
    ▼
EconomicRepository.insert_many_skip_duplicates()
    │  source_url UNIQUE 기반 ON CONFLICT DO NOTHING
    ▼
raw_economic_data (Bronze PostgreSQL)
```

---

## 4. 핵심 설계 결정

### 4-1. 동기 HTTP + asyncio.to_thread

기존 `wowtale_collector.py`와 `rss_wordpress_sync.py`의 패턴을 그대로 따른다.

```python
# wowtale_archive_crawler.py
async def crawl_category(self, ...) -> list[EconomicCollectDto]:
    return await asyncio.to_thread(self._crawl_category_sync, ...)
```

**이유**:
- `httpx.Client` (동기) → `httpx.AsyncClient` 보다 연결 풀 관리가 단순
- 기존 `fetch_html_sync` / `wordpress_main_text` 유틸 재사용 가능
- `asyncio.to_thread`로 이벤트 루프 블로킹 방지

### 4-2. from_date 조기 중단 전략

카테고리 아카이브는 최신 기사부터 나열되므로, 페이지를 순회하다가
**URL 경로의 날짜(/YYYY/MM/DD/)가 from_date 이전**이면 즉시 중단한다.

```python
if from_date and ref.published_at and ref.published_at < from_date:
    stop_crawl = True
    break
```

- URL 날짜는 ±1일 오차 가능 (09:00 KST 기본값 사용)
- 정확한 날짜는 기사 상세 페이지의 `<time datetime="ISO8601">` 에서 추출

### 4-3. 이중 날짜 추출 (정확도 vs 속도)

| 모드 | 날짜 출처 | 정확도 | 속도 |
|------|---------|--------|------|
| `fetch_article_body=False` | URL 경로 `/YYYY/MM/DD/` → KST 09:00 | ±1일 | 빠름 (~30배) |
| `fetch_article_body=True` | `<time class="entry-date" datetime="ISO8601">` | 분 단위 정확 | 느림 |

Backfill 초기 실행에서는 `fetch_article_body=True` (기본값) 를 권장한다.
투자 금액 추출 정확도가 `body_text` 유무에 따라 크게 달라지기 때문이다.

### 4-4. 중복 방지 계층

1. **크롤러 내부**: `known_urls` set으로 동일 카테고리 내 + 카테고리 간 중복 URL 스킵
2. **Repository**: `source_url` UNIQUE 제약 + `ON CONFLICT DO NOTHING`

```python
# crawl_all() 내부
seen: set[str] = set(known_urls or set())
for slug, apply_filter in targets:
    dtos = await self.crawl_category(slug, known_urls=seen, ...)
    seen.update(d.source_url for d in dtos if d.source_url)  # 카테고리 간 중복 방지
```

### 4-5. 카테고리별 source_type 전략

| 카테고리 slug | source_type 결정 방식 | 가능한 값 |
|-------------|-------------------|---------|
| `funding` | 제목 기반 자동 분류 | `WOWTALE_INVEST` / `WOWTALE_MA` / `WOWTALE_IPO` / `WOWTALE_FUND` |
| `venture-capital` | 고정 | `WOWTALE_VC` |
| `Global-news` | 제목 기반 자동 분류 + 투자 필터 | `WOWTALE_INVEST` / `WOWTALE_MA` 등 |
| `ai` | 고정 | `WOWTALE_AI` |
| `bio-healthcare` | 고정 | `WOWTALE_BIO` |
| `contests` | 고정 | `WOWTALE_CONTEST` |
| `landscape` | 고정 | `WOWTALE_LANDSCAPE` |
| `policy` | 고정 | `WOWTALE_POLICY` |

### 4-6. API 응답: 202 Accepted (비동기)

수집량에 따라 수십 분이 소요되므로 `BackgroundTasks`로 처리하고 즉시 `202 Accepted`를 반환한다.

```python
@router.post("/bronze/economic/wowtale-archive", status_code=202)
async def run_wowtale_archive_bronze(body: WowtaleArchiveRequest, background_tasks: BackgroundTasks):
    background_tasks.add_task(_run_backfill)
    return {"status": "accepted", "message": "..."}
```

이는 기존 `moef-upload` 엔드포인트의 비동기 패턴과 동일하다.

---

## 5. CSS 셀렉터 전략 (실사이트 검증 결과)

Wowtale(WordPress)에서 실제 확인한 셀렉터:

### 카테고리 아카이브 페이지

```python
# 기사 컨테이너 (우선순위 순)
articles = (
    soup.select("article.post")                    # WordPress 표준
    or soup.select("article[class*='type-post']")  # 클래스 부분 매칭
    or soup.select("article")                      # 최종 폴백
)

# 기사 제목 + URL (우선순위 순)
title_a = (
    art.select_one("h2.entry-title a")  # WordPress 표준
    or art.select_one("h2 a")           # 단순 h2
    or art.select_one(".entry-title a") # 클래스만
)

# 다음 페이지
has_next = soup.select_one("a.next.page-numbers") is not None
```

### 기사 상세 페이지

```python
# 발행일 (우선순위 순)
"time.entry-date[datetime]"   # WordPress 표준 (ISO 8601)
"time.published[datetime]"    # 일부 테마
"time[datetime]"              # 최종 폴백

# 본문 (wordpress_main_text() 내부 셀렉터 순서)
"article .entry-content"
"div.entry-content"
"article.post"
"main article"
"div.post-content"
```

### 이미지 Lazy-Load 처리

Wowtale은 `data:image/svg+xml` placeholder 방식의 lazy-load를 사용한다.
현재 구현에서는 썸네일 URL을 수집하지 않으므로 별도 처리 불필요.

---

## 6. 실행 방법

### 6-1. CLI Backfill (권장: 대용량 초기 수집)

```bash
cd backend

# 기본 실행 (최근 1년, funding + venture-capital + Global-news)
python scripts/wowtale_backfill.py

# 날짜 컷오프 지정
python scripts/wowtale_backfill.py --from-date 2025-01-01

# 빠른 실행 (본문 크롤링 스킵 — 제목·날짜만, ~30배 빠름)
python scripts/wowtale_backfill.py --no-article-body

# 테스트용 소규모 (1페이지만)
python scripts/wowtale_backfill.py --max-pages 1 --categories funding
```

### 6-2. API (소규모 점진적 수집 또는 모니터링)

```bash
# 기본 실행 (202 즉시 응답, 백그라운드 실행)
curl -X POST http://localhost:8000/api/master/bronze/economic/wowtale-archive \
  -H "Content-Type: application/json" \
  -d '{"max_pages": 10, "from_date": "2025-06-01", "fetch_article_body": true}'

# 빠른 실행 (본문 스킵)
curl -X POST http://localhost:8000/api/master/bronze/economic/wowtale-archive \
  -H "Content-Type: application/json" \
  -d '{"max_pages": 50, "fetch_article_body": false}'

# 특정 카테고리만
curl -X POST http://localhost:8000/api/master/bronze/economic/wowtale-archive \
  -H "Content-Type: application/json" \
  -d '{"max_pages": 20, "categories": ["funding", "venture-capital"]}'
```

### 6-3. 통합 테스트

```bash
cd backend
python scripts/wowtale_archive_integration_test.py
```

---

## 7. 성능 특성 및 예상 결과

### 7-1. 소요 시간 추정

| 설정 | 공식 | 예상 시간 |
|------|------|---------|
| 기본 (3 카테고리 × 50페이지 × 본문 ON) | 3 × 50 × 20건 × 1.5초 | **약 75분** |
| 본문 OFF (3 카테고리 × 50페이지) | 3 × 50 × 1초 + 카테고리 간 2초 | **약 2.5분** |
| 단일 카테고리 (funding, 50페이지, 본문 ON) | 50 × 20건 × 1.5초 | **약 25분** |

> `article_sleep_sec=0.5` + `sleep_sec=1.0` 기준. 서버 응답 시간(~0.3초) 포함.

### 7-2. 예상 수집량 (1년치 Backfill 기준)

| 카테고리 | 일 평균 게시 | 1년 예상 | 50페이지 예상 |
|---------|------------|---------|------------|
| funding | 5~8건 | 1,800~2,900건 | ~1,000건 |
| venture-capital | 1~3건 | 365~1,100건 | ~400건 |
| Global-news | 3~5건 (투자 필터 후) | 500~800건 | ~300건 |
| **합계** | | **2,700~4,800건** | **~1,700건** |

### 7-3. 투자 금액 추출 성공률 예상

| 단계 | 성공률 |
|------|--------|
| 제목만 (본문 크롤링 OFF) | 40~50% |
| 제목 + 본문 (본문 크롤링 ON) | 70~80% |
| Silver LLM 추출 (미래) | 90~95% |

---

## 8. RSS 수집기와의 관계

```
정기 수집 (매일 09:00 KST)
    WowtaleEconomicCollector.collect()   ← RSS, 최근 50건
    → raw_economic_data (일별 신규 5~10건)

초기 Backfill (1회성 또는 분기별)
    WowtaleArchiveCrawler.crawl_all()    ← 아카이브 페이지 크롤링
    → raw_economic_data (과거 ~1,700건 추가)
```

두 수집기는 모두 `source_url` UNIQUE 제약으로 중복을 방지하므로
**순서에 관계없이 실행 가능**하다. RSS가 먼저 적재된 URL은 아카이브 크롤러가
`ON CONFLICT DO NOTHING`으로 자동 스킵한다.

---

## 9. 제한 사항 및 주의사항

### 9-1. 크롤링 에티켓

| 항목 | 설정값 | 이유 |
|------|--------|------|
| 페이지 간 sleep | 1.0초 | Wowtale 서버 부하 방지 |
| 기사 간 sleep | 0.5초 | 연속 요청 방지 |
| User-Agent | Chrome 브라우저 사칭 | 봇 차단 방지 |
| 수집 주기 | 1회성 Backfill + 일 1회 RSS | 과도한 요청 방지 |

> robots.txt 소규모 크롤링 허용 확인 완료 (상업적 대량 크롤링은 Wowtale 문의 권장).

### 9-2. HTML 구조 변경 리스크

WordPress 테마 업데이트 시 CSS 클래스명이 변경될 수 있다.

**모니터링 지표**: `_parse_archive_page` 의 `refs` 빈 리스트 반환 횟수.
빈 리스트가 연속 2페이지 이상 반환되면 셀렉터 재검증 필요.

### 9-3. 투자 필터 적용 카테고리

`Global-news` 카테고리는 투자 외 기술 뉴스도 포함하므로
`apply_investment_filter=True`로 설정해 `_is_investment_relevant()` 필터를 적용한다.
`funding`, `venture-capital` 은 카테고리 자체가 투자 관련이므로 필터 불필요.

### 9-4. 날짜 정확도

- `fetch_article_body=False` : URL 경로 날짜 (당일 KST 09:00로 고정)
- `fetch_article_body=True` : `<time datetime="ISO8601">` 분 단위 정확

Silver Layer에서 `published_at` 정밀도가 중요한 경우 `fetch_article_body=True` 사용.

---

## 10. 관련 문서 및 파일

| 문서/파일 | 역할 |
|----------|------|
| `WOWTALE_ARCHIVE_CRAWLER_SPEC.md` | 사이트 HTML 구조 분석 명세 |
| `WOWTALE_YAHOO_ENHANCEMENT_STRATEGY.md` | 전체 데이터 확충 전략 |
| `WOWTALE_RSS_COLLECTION_GUIDE.md` | RSS 수집기 설계 가이드 |
| `wowtale_archive_crawler.py` | 크롤러 구현 본체 |
| `wowtale_collector.py` | RSS 수집기 (공유 유틸 포함) |
| `rss_wordpress_sync.py` | WordPress 본문 추출 유틸 |
| `_rss_investment_krw.py` | 투자 금액 정규식 추출 |
| `wowtale_backfill.py` | CLI Backfill 스크립트 |
| `wowtale_archive_integration_test.py` | 통합 테스트 |
