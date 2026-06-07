# Wowtale 아카이브 크롤러 설계 명세

> **작성일**: 2026-05-17  
> **목적**: `wowtale_archive_crawler.py` 구현을 위한 사이트 구조 분석 및 HTML 셀렉터 명세  
> **선행 문서**: `WOWTALE_RSS_COLLECTION_GUIDE.md`, `WOWTALE_YAHOO_ENHANCEMENT_STRATEGY.md`

---

## 1. 사이트 개요

| 항목 | 내용 |
|------|------|
| **URL** | https://wowtale.net |
| **플랫폼** | WordPress (테마 커스터마이징) |
| **CDN** | `https://cdn.wowtale.net/wp-content/uploads/YYYY/MM/` |
| **RSS** | `https://wowtale.net/feed/` (최근 50건) |
| **언어** | 한국어 메인 / 영문 서브 (`en.wowtale.net`) |
| **업데이트** | 일 3~10건 |
| **크롤링 가능** | robots.txt 소규모 허용 (일 1~2회, 1초 sleep 필수) |

---

## 2. URL 구조

### 2-1. 기사 URL 패턴

```
https://wowtale.net/{YYYY}/{MM}/{DD}/{post_id}/
```

예시:
```
https://wowtale.net/2026/05/15/258765/
https://wowtale.net/2026/05/14/258629/
```

- `post_id`는 자동 증가 정수 (현재 258xxx 대)
- URL 내 날짜(`YYYY/MM/DD`)로 `published_at` 추정 가능 (보조 수단, time 태그가 기준)

### 2-2. 카테고리 아카이브 URL 패턴

```
https://wowtale.net/category/{slug}/           # 1페이지
https://wowtale.net/category/{slug}/page/{n}/  # n페이지 (n >= 2)
```

### 2-3. 태그 아카이브 URL 패턴

```
https://wowtale.net/tag/{tag_slug}/
https://wowtale.net/tag/{tag_slug}/page/{n}/
```

---

## 3. 네비게이션 & 카테고리 전체 구조

### 3-1. 메인 네비게이션

```
뉴스  (/)
와우비즈  (/biz/wow-together/)
행사  (/event/)
```

### 3-2. 서브 카테고리 네비게이션 (뉴스 섹션)

| 메뉴명 | URL | slug | 카테고리 설명 |
|--------|-----|------|--------------|
| 뉴스 홈 | `/` | — | 전체 최신 기사 |
| 최신 | `/latest-news/` | latest-news | 시간 순 최신 피드 |
| 산업지형 | `/category/landscape/` | landscape | 산업별 지형도·심층 분석 리포트 |
| 인터뷰 | `/category/interview/` | interview | 창업자·VC 인터뷰 |
| 지원사업 | `/category/contests/` | contests | 정부·민간 공모전·지원 프로그램 공고 |
| **투자** | `/category/funding/` | funding | 국내 스타트업 투자 유치 소식 (**핵심**) |
| 해외 | `/category/Global-news/` | Global-news | 실리콘밸리 중심 해외 스타트업 소식 |
| 정책 | `/category/policy/` | policy | 중기부·정부 창업 정책·규제 변화 |
| 인공지능(AI) | `/category/ai/` | ai | AI 스타트업·기술 트렌드 |
| 바이오헬스 | `/category/bio-healthcare/` | bio-healthcare | 바이오·헬스케어 스타트업 |
| 소부장 | `/tag/%EC%86%8C%EB%B6%80%EC%9E%A5/` | 소부장 (tag) | 소재·부품·장비 |
| **벤처캐피탈** | `/category/venture-capital/` | venture-capital | VC·CVC·액셀러레이터 소식 (**핵심**) |
| 콘텐츠 | `/category/contents/` | contents | 미디어·엔터테인먼트·크리에이터 |
| **M&A** | `/tag/%EC%9D%B8%EC%88%98%ED%95%A9%EB%B3%91/` | 인수합병 (tag) | 인수합병 딜 (**핵심**) |

---

## 4. Roadmap 플랫폼 매핑 — Bronze 테이블별 수집 대상

메달리온 아키텍처의 Bronze 계층에 어떤 카테고리가 매핑되는지 정의합니다.

### 4-1. `raw_economic_data` (경제·투자 흐름 선행 지표)

| 우선순위 | 카테고리 | slug | source_type |
|---------|---------|------|-------------|
| **P0 — 핵심** | 투자 | `funding` | `WOWTALE_INVEST` / `WOWTALE_MA` / `WOWTALE_IPO` / `WOWTALE_FUND` |
| **P0 — 핵심** | M&A | `인수합병` (tag) | `WOWTALE_MA` |
| P1 | 벤처캐피탈 | `venture-capital` | `WOWTALE_VC` |
| P1 | 해외 (투자 필터) | `Global-news` | `WOWTALE_GLOBAL_INVEST` |

**수집 목표**: 최근 1년치 약 1,000~3,000건, 투자 금액·투자자·라운드 추출

### 4-2. `raw_innovation_data` (혁신·기술 선행 지표)

| 우선순위 | 카테고리 | slug | source_type |
|---------|---------|------|-------------|
| **P0** | 인공지능(AI) | `ai` | `WOWTALE_AI` |
| P1 | 바이오헬스 | `bio-healthcare` | `WOWTALE_BIO` |
| P1 | 산업지형 | `landscape` | `WOWTALE_LANDSCAPE` |
| P2 | 소부장 | `소부장` (tag) | `WOWTALE_SOBUJANG` |
| P2 | 해외 | `Global-news` | `WOWTALE_GLOBAL_TECH` |

### 4-3. `raw_opportunity_data` (기회·공고 선행 지표)

| 우선순위 | 카테고리 | slug | source_type |
|---------|---------|------|-------------|
| **P0** | 지원사업 | `contests` | `WOWTALE_CONTEST` |
| P1 | 정책 | `policy` | `WOWTALE_POLICY` |

### 4-4. `raw_discourse_data` (담론·인식 선행 지표)

| 우선순위 | 카테고리 | slug | source_type |
|---------|---------|------|-------------|
| P1 | 산업지형 | `landscape` | `WOWTALE_LANDSCAPE` |
| P2 | 인터뷰 | `interview` | `WOWTALE_INTERVIEW` |

---

## 5. HTML 구조 분석

### 5-1. 카테고리 아카이브 페이지 구조

WordPress 표준 구조로, 기사 목록은 `<article>` 태그 배열로 구성됩니다.

```html
<!-- 페이지 최상위 컨테이너 -->
<main id="main" class="site-main">

  <!-- 카테고리 설명 (있는 경우) -->
  <header class="page-header">
    <h1 class="page-title">투자유치(Funding)</h1>
    <div class="archive-description">
      <p>국내 스타트업의 투자유치 소식을 전합니다</p>
    </div>
  </header>

  <!-- 기사 목록 루프 -->
  <div class="posts-wrapper">

    <!-- 개별 기사 카드 -->
    <article class="post-258765 post type-post status-publish format-standard has-post-thumbnail">

      <!-- 썸네일 영역 (lazy load: svg placeholder → img) -->
      <div class="post-thumbnail">
        <a href="https://wowtale.net/2026/05/15/258765/">
          <svg xmlns="..." width="640" height="360"></svg>  <!-- 레이아웃 예약 placeholder -->
          <img
            src="https://cdn.wowtale.net/wp-content/uploads/2026/05/filename.jpg"
            width="640"
            height="360"
            alt="기사 제목"
            class="wp-post-image"
            loading="lazy"
          />
        </a>
      </div>

      <!-- 기사 헤더 -->
      <header class="entry-header">
        <h2 class="entry-title">
          <a href="https://wowtale.net/2026/05/15/258765/" rel="bookmark">
            위로보틱스, 950억 규모 시리즈B 투자 유치… 휴머노이드 사업 본격화
          </a>
        </h2>
      </header>

      <!-- 날짜 (아카이브 카드에는 직접 노출 안 됨, URL에서 추출 가능) -->
      <!-- excerpt 없음 — 카드는 제목+썸네일만 표시 -->

    </article>

    <article class="post-258629 post type-post ...">
      <!-- 동일 구조 반복 -->
    </article>

  </div><!-- .posts-wrapper -->

  <!-- 페이지네이션 -->
  <nav class="navigation pagination" aria-label="Posts">
    <div class="nav-links">
      <a class="prev page-numbers" href="/category/funding/">« 이전</a>
      <a class="page-numbers" href="/category/funding/">1</a>
      <span class="page-numbers current">2</span>
      <a class="page-numbers" href="/category/funding/page/3/">3</a>
      <a class="next page-numbers" href="/category/funding/page/3/">다음 »</a>
    </div>
  </nav>

</main>
```

#### 핵심 CSS 셀렉터 (카테고리 아카이브)

| 추출 데이터 | CSS 셀렉터 | 비고 |
|------------|-----------|------|
| 기사 전체 목록 | `article.post` 또는 `article[class*="type-post"]` | |
| post_id | `article` 클래스에서 `post-{id}` 파싱 | `re.search(r'post-(\d+)', class_str)` |
| 기사 제목 | `h2.entry-title > a` 또는 `h2 > a` | `.get_text(strip=True)` |
| 기사 URL | `h2.entry-title > a[href]` | `.get("href")` |
| 썸네일 URL | `.post-thumbnail img[src]` | lazy-load: `src` 또는 `data-src` |
| 다음 페이지 링크 | `a.next.page-numbers[href]` | 없으면 마지막 페이지 |
| 페이지 번호들 | `a.page-numbers[href]` | 전체 페이지 수 파악용 |

#### article 태그 클래스 패턴 (확인된 값)

```
post-{post_id}        # 포스트 ID (필수 추출)
post                  # 고정
type-post             # 고정 (page/attachment 등과 구분)
status-publish        # 발행 상태
format-standard       # 포스트 포맷 (standard/video/gallery 등)
has-post-thumbnail    # 썸네일 존재 여부
category-funding      # 소속 카테고리 (카테고리 페이지에서 추가됨)
```

---

### 5-2. 기사 상세 페이지 구조

```html
<article class="post-258765 post type-post ...">

  <!-- 기사 헤더 -->
  <header class="entry-header">
    <h1 class="entry-title">
      위로보틱스, 950억 규모 시리즈B 투자 유치… 휴머노이드 사업 본격화
    </h1>

    <!-- 메타 정보 -->
    <div class="entry-meta">
      <!-- 발행일 (확인된 형식: YYYY.MM.DD 텍스트 또는 time 태그) -->
      <time class="entry-date published" datetime="2026-05-15T09:30:00+09:00">
        2026.05.15
      </time>

      <!-- 저자 -->
      <span class="byline">
        <a href="https://wowtale.net/author/nbr/">정명화</a>
      </span>

      <!-- 카테고리 -->
      <span class="cat-links">
        <a href="https://wowtale.net/category/robotics/">로보틱스(Robotics)</a>
        <a href="https://wowtale.net/category/funding/">투자유치(Funding)</a>
      </span>
    </div>
  </header>

  <!-- 기사 본문 — 투자 정보가 첫 단락에 집중 -->
  <div class="entry-content">

    <!-- 첫 단락: 핵심 투자 정보 (금액·투자자·라운드) -->
    <p>
      글로벌 로보틱스 기업 위로보틱스가 950억 원 규모 시리즈B 투자 유치를
      완료했다고 15일 밝혔다. 이번 투자에는
      <a href="...">JB인베스트먼트</a>가 리드 투자자로 참여했으며,
      <a href="...">인터베스트</a>, <a href="...">하나벤처스</a>,
      <a href="...">스마일게이트인베스트먼트</a>, SBVA, NH투자증권, 컴퍼니케이,
      지유투자, 퓨처플레이 등이 함께했다.
    </p>

    <!-- 이후 단락: 회사 소개, 투자 배경, 향후 계획 -->
    <p>위로보틱스는 ...</p>
    <p>이번 투자금은 ...</p>

    <!-- 관련 기사 섹션 -->
    <div class="related-posts">
      <h3>관련 기사</h3>
      <ul>
        <li><a href="...">위로보틱스, 130억원 규모 시리즈A 투자 유치...</a></li>
      </ul>
    </div>

  </div><!-- .entry-content -->

</article>
```

#### 핵심 CSS 셀렉터 (기사 상세)

| 추출 데이터 | CSS 셀렉터 | 비고 |
|------------|-----------|------|
| 기사 제목 | `h1.entry-title` | |
| 발행일 (ISO) | `time.entry-date[datetime]` | `datetime` 속성 우선 |
| 발행일 (텍스트) | `time.entry-date` | `get_text()` fallback |
| 저자 | `.byline a` 또는 `.author a` | |
| 카테고리들 | `.cat-links a` | 복수 가능 |
| 태그들 | `.tags-links a` | 복수 가능 |
| 본문 전체 | `div.entry-content` | BS4 `get_text()` |
| 본문 첫 단락 | `div.entry-content > p:first-of-type` | 투자 정보 집중 |
| 투자자 링크 | `div.entry-content a[href*="category"]` | 카테고리 링크된 VC명 |

---

### 5-3. 날짜 형식 및 추출 우선순위

Wowtale의 날짜 표기는 컨텍스트에 따라 다릅니다.

| 위치 | 형식 | 예시 | 추출 방법 |
|------|------|------|----------|
| 기사 상세 `<time>` datetime 속성 | ISO 8601 | `2026-05-15T09:30:00+09:00` | **1순위** — `.get("datetime")` |
| 기사 상세 `<time>` 텍스트 | YYYY.MM.DD | `2026.05.15` | 2순위 — `get_text()` 파싱 |
| 카테고리 아카이브 카드 | 미표시 | — | URL 경로 파싱 fallback |
| 기사 URL 경로 | YYYY/MM/DD | `/2026/05/15/258765/` | 3순위 — `re.search(r'/(\d{4})/(\d{2})/(\d{2})/', url)` |

```python
import re
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))

def parse_date_from_url(url: str) -> datetime | None:
    """URL 경로에서 날짜 추출 (fallback용)."""
    m = re.search(r'/(\d{4})/(\d{2})/(\d{2})/', url)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return datetime(y, mo, d, 9, 0, 0, tzinfo=KST)  # KST 09:00 기본값
    return None
```

---

### 5-4. 이미지 Lazy-Load 처리

Wowtale은 SVG placeholder + lazy-load 방식을 사용합니다. 썸네일 URL 추출 시 주의가 필요합니다.

```html
<!-- 로딩 전: SVG placeholder만 있음 -->
<img src="data:image/svg+xml,..." width="640" height="360" />

<!-- JavaScript 실행 후: 실제 이미지 src 주입 -->
<img
  src="https://cdn.wowtale.net/wp-content/uploads/2026/05/filename.jpg"
  data-src="https://cdn.wowtale.net/..."
  loading="lazy"
/>
```

**크롤러 대응**: `requests`/`httpx` (non-JS) 환경에서는 `data-src` 속성 또는 `srcset` 속성에서 실제 URL을 추출합니다.

```python
def extract_thumbnail(article_soup) -> str | None:
    img = article_soup.select_one(".post-thumbnail img")
    if not img:
        return None
    # data-src 우선, 없으면 src (SVG 제외)
    for attr in ("data-src", "data-lazy-src", "src"):
        url = img.get(attr, "")
        if url and not url.startswith("data:"):
            return url
    return None
```

---

## 6. 페이지네이션 전략

### 6-1. 페이지네이션 HTML 구조

```html
<nav class="navigation pagination">
  <div class="nav-links">
    <!-- 이전 페이지 (1페이지에서는 없음) -->
    <a class="prev page-numbers" href="/category/funding/">« 이전</a>

    <!-- 페이지 번호 목록 -->
    <a class="page-numbers" href="/category/funding/">1</a>
    <span class="page-numbers current">2</span>  <!-- 현재 페이지 -->
    <a class="page-numbers" href="/category/funding/page/3/">3</a>
    <span class="page-numbers dots">…</span>
    <a class="page-numbers" href="/category/funding/page/12/">12</a>

    <!-- 다음 페이지 (마지막 페이지에서는 없음) -->
    <a class="next page-numbers" href="/category/funding/page/3/">다음 »</a>
  </div>
</nav>
```

### 6-2. 크롤러 페이지 순회 전략

```python
async def _get_next_page_url(soup: BeautifulSoup) -> str | None:
    """다음 페이지 URL 추출. 없으면 None (마지막 페이지)."""
    next_link = soup.select_one("a.next.page-numbers")
    return next_link.get("href") if next_link else None

async def _get_total_pages(soup: BeautifulSoup) -> int:
    """전체 페이지 수 추출 (점프 크롤링용)."""
    page_nums = soup.select("a.page-numbers:not(.next):not(.prev)")
    if not page_nums:
        return 1
    last = page_nums[-1].get_text(strip=True)
    try:
        return int(last)
    except ValueError:
        return 1
```

### 6-3. 페이지당 기사 수

| 카테고리 | 페이지당 기사 수 | 비고 |
|---------|--------------|------|
| funding | ~20건 | 확인됨 |
| Global-news | ~10건 | 확인됨 |
| ai | ~10건 | 확인됨 |
| 기타 | ~10~20건 | 카테고리 규모 따라 다름 |

---

## 7. 본문 투자 정보 패턴

### 7-1. 투자 금액 표현 패턴 (정규식용)

기사 본문에서 확인된 실제 표현 예시:

```
"950억 원 규모 시리즈B 투자 유치"
"500억원 규모 CB 발행"
"6,400만 달러 시리즈A 유치"
"1억2200만 달러 투자유치"
"4억 달러 추가 유치… 누적 10억 달러 돌파"
"2300만 달러 시리즈A 투자 유치"
"55억 달러 조달"
```

### 7-2. 라운드 표현 패턴

```
시드(Seed), 프리A(Pre-A), 시리즈A, 시리즈B, 시리즈C, 시리즈D
프리IPO(Pre-IPO), 브릿지(Bridge)
CB(전환사채), BW(신주인수권부사채)
```

### 7-3. 투자자 표현 패턴

```
"JB인베스트먼트가 리드 투자자로 참여했으며"
"카카오벤처스·알토스벤처스 공동 투자"
"대웅제약·네이버로부터 전략적 투자 유치"
"KB증권으로부터 시리즈A 투자 유치"
"호라이즌인베스트먼트서 프리A 투자 유치"
```

투자자명 추출 시 `<a href>` 태그 + 정규식 패턴 병행 사용 권장:

```python
# 투자자명이 링크로 마크업된 경우
investors_from_links = [
    a.get_text(strip=True)
    for a in content_div.select("a")
    if "category" not in a.get("href", "") and len(a.get_text(strip=True)) > 2
]

# 정규식 패턴 (VC명 직접 추출)
VC_SUFFIX_PATTERN = re.compile(
    r'([\w가-힣]+(?:벤처스|벤처캐피탈|인베스트먼트|파트너스|캐피탈|증권|은행|'
    r'파트너|어드바이저|홀딩스|그룹|VC|CVC))'
)
```

---

## 8. 크롤러 구현 핵심 파라미터

### 8-1. HTTP 요청 설정

```python
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://wowtale.net/",
}

TIMEOUT = 30       # 초
SLEEP_SEC = 1.0    # 요청 간 대기 (서버 부하 방지)
MAX_RETRIES = 3    # 실패 시 재시도 횟수
RETRY_WAIT = 5.0   # 재시도 간격 (초)
```

### 8-2. Backfill 기본 설정 (권장값)

```python
BACKFILL_CATEGORIES = [
    "funding",           # P0: 투자 유치 (raw_economic_data)
    "venture-capital",   # P0: VC 소식 (raw_economic_data)
    "ai",                # P1: AI 트렌드 (raw_innovation_data)
    "bio-healthcare",    # P1: 바이오 (raw_innovation_data)
    "contests",          # P1: 지원사업 (raw_opportunity_data)
    "Global-news",       # P2: 해외 (raw_innovation_data)
    "landscape",         # P2: 산업지형 (raw_discourse_data)
    "policy",            # P2: 정책 (raw_opportunity_data)
]

MAX_PAGES_PER_CATEGORY = 50   # 페이지당 ~20건 → 50페이지 = ~1,000건
ARTICLE_FETCH_ENABLED = True  # 상세 페이지 개별 크롤링 여부
MAX_ARTICLE_TEXT_LEN = 5000   # raw_metadata["content_text"] 저장 최대 길이
```

### 8-3. 중복 방지 (idempotent)

- `raw_economic_data.source_url`에 UNIQUE 제약 → 동일 URL 재수집 시 `ON CONFLICT DO NOTHING`
- 카테고리 아카이브 크롤링 시 URL을 먼저 수집 → DB에 없는 URL만 상세 페이지 크롤링

---

## 9. 카테고리별 크롤링 우선순위 요약

```
Phase 1 (Backfill — raw_economic_data, 즉시)
  ├── /category/funding/          P0  ~50페이지 (~1,000건, 1년치)
  └── /category/venture-capital/  P0  ~20페이지 (~400건)

Phase 2 (Backfill — raw_innovation_data)
  ├── /category/ai/               P1  ~30페이지
  └── /category/bio-healthcare/   P1  ~20페이지

Phase 3 (Backfill — raw_opportunity_data + raw_discourse_data)
  ├── /category/contests/         P1  ~15페이지
  ├── /category/Global-news/      P2  ~30페이지
  ├── /category/landscape/        P2  ~10페이지
  └── /category/policy/           P2  ~10페이지
```

---

## 10. 구현 파일 위치

```
backend/domain/master/
└── hub/services/collectors/economic/
    ├── wowtale_collector.py          # 기존 RSS 수집기 (Phase 1 완료)
    └── wowtale_archive_crawler.py    # 신규 아카이브 크롤러 (구현 대상)

backend/scripts/
└── wowtale_backfill.py               # Backfill 실행 스크립트 (신규)
```

---

## 11. 관련 문서

- `WOWTALE_RSS_COLLECTION_GUIDE.md` — RSS 기반 수집기 설계 (Phase 1 완료)
- `WOWTALE_YAHOO_ENHANCEMENT_STRATEGY.md` — 전체 데이터 확충 전략
- `BRONZE_ARCHITECTURE_DECISION.md` — Bronze 계층 전체 아키텍처
- `wowtale_collector.py` — 현재 RSS 수집기 (아카이브 크롤러의 DTO·유틸 함수 재사용)
