# 네이버 API → RSS 전환 전략 (최종 보완판)

## 📋 목차
1. [아키텍처 변경 전략](#1-아키텍처-변경-전략)
2. [RSS URL 매핑 전략](#2-rss-url-매핑-전략)
3. [코드 수정 전략](#3-코드-수정-전략)
4. [NewsController 수정 전략](#4-newscontroller-수정-전략)
5. [구현 단계별 전략](#5-구현-단계별-전략)
6. [주의사항 및 제약사항](#6-주의사항-및-제약사항)
   - 6.1 [캐싱 전략의 의무화](#61-캐싱-전략의-의무화-필수-구현)
   - 6.2 [페이징 및 개수 제한 극복](#62-페이징-및-개수-제한-극복-중요)
   - 6.3 [검색어 처리 전략](#63-검색어-처리-전략)
   - 6.4 [날짜 처리의 중요성](#64-날짜-처리의-중요성-중요)
   - 6.5 [비동기 병렬 처리](#65-비동기-병렬-처리-필수)
7. [설정 관리 전략](#7-설정-관리-전략)
8. [마이그레이션 전략](#8-마이그레이션-전략-점진적-전환)

---

## 1. 아키텍처 변경 전략

### 현재 구조 (네이버 API)
- **검색어 기반**: `query`로 동적 검색
- **파라미터**: `query`, `display`, `start` (페이징)
- **단일 엔드포인트**로 모든 카테고리 처리

### RSS 구조
- **URL 기반**: 카테고리별 고정 RSS URL
- **검색어 기능 없음** (RSS는 최신 기사 목록만 제공)
- **각 뉴스 사이트/카테고리마다 별도 RSS URL 필요**

---

## 2. RSS URL 매핑 전략

### ⚠️ 옵션 A: 네이버 뉴스 RSS 활용 (비권장)

#### 위험성 분석
- ❌ **비공식 API와 유사**: 네이버 뉴스 RSS는 공식 API가 아닙니다
- ❌ **불안정성**: 네이버가 언제든지 RSS 포맷이나 URL을 예고 없이 변경하거나 차단할 수 있습니다
- ❌ **장기적 유지보수 어려움**: 비공식 엔드포인트에 의존하는 것은 위험합니다
- ⚠️ **법적 리스크**: 과도한 요청 시 IP 차단 가능성

#### 네이버 RSS URL 예시 (참고용)
```
카테고리 → 네이버 RSS URL 매핑
- 경제: https://news.naver.com/main/rss/section.naver?sid=101
- 정치: https://news.naver.com/main/rss/section.naver?sid=100
- 사회: https://news.naver.com/main/rss/section.naver?sid=102
- 생활/문화: https://news.naver.com/main/rss/section.naver?sid=103
- 세계: https://news.naver.com/main/rss/section.naver?sid=104
- IT/과학: https://news.naver.com/main/rss/section.naver?sid=105
- 스포츠: https://news.naver.com/main/rss/section.naver?sid=106
- 연예: https://news.naver.com/main/rss/section.naver?sid=107
```

**사용 권장도**: 초기 테스트 및 보조용으로만 사용, 프로덕션에서는 제한적 사용

---

### ✅ 옵션 B: 다중 출처 RSS 통합 (최종 권장)

#### 장점
- ✅ **안정성**: 공식 RSS 피드 제공 언론사 활용
- ✅ **다양성**: 여러 출처 통합으로 데이터 품질 향상
- ✅ **장기적 유지보수**: 공식 피드이므로 변경 가능성 낮음
- ✅ **법적 안정성**: 공개 RSS 피드 활용

#### 권장 RSS 출처 목록

**주요 언론사 공식 RSS**
- **연합뉴스**: https://www.yna.co.kr/rss/
  - 경제: https://www.yna.co.kr/rss/economy.xml
  - 정치: https://www.yna.co.kr/rss/politics.xml
  - 사회: https://www.yna.co.kr/rss/society.xml
  - 국제: https://www.yna.co.kr/rss/international.xml
  - IT/과학: https://www.yna.co.kr/rss/technology.xml
  - 스포츠: https://www.yna.co.kr/rss/sports.xml
  - 연예: https://www.yna.co.kr/rss/entertainment.xml

- **한겨레**: https://www.hani.co.kr/rss/
  - 정치: https://www.hani.co.kr/rss/politics/
  - 경제: https://www.hani.co.kr/rss/economy/
  - 사회: https://www.hani.co.kr/rss/society/
  - 국제: https://www.hani.co.kr/rss/international/
  - IT/과학: https://www.hani.co.kr/rss/science/

- **경제신문 (매일경제, 한국경제 등)**
  - 매일경제: https://www.mk.co.kr/rss/
  - 한국경제: https://www.hankyung.com/rss/

- **IT 전문 매체**
  - IT조선: https://it.chosun.com/rss/
  - 전자신문: https://www.etnews.com/rss/

#### 통합 전략
1. **카테고리별 다중 출처 수집**: 예) "경제" 카테고리 → 연합뉴스 경제 + 한겨레 경제 + 매일경제
2. **병합 및 중복 제거**: 제목 기준으로 중복 기사 제거
3. **날짜순 정렬**: 최신 기사 우선
4. **데이터 풀(Pool) 확장**: 여러 출처 통합으로 20-50개 제한 극복

---

## 3. 코드 수정 전략

### 3.1 RssService 개선

#### 필수 구현 항목
- [ ] `formatDate()` 구현 (NewsService의 로직 재사용)
- [ ] **이미지 추출 로직 추가** (Jsoup 라이브러리 활용)
- [ ] 날짜 정렬 기능 추가
- [ ] HTML 태그 제거 로직 추가

#### 이미지 추출 로직 개선 (중요)

**문제점**: RSS 피드는 이미지 URL을 다양한 방식으로 제공
- `media:content` 태그 (RSS 2.0 확장)
- `enclosure` 태그
- description의 HTML `<img>` 태그

**해결책**: Jsoup 라이브러리 활용
```java
// build.gradle에 추가 필요
implementation 'org.jsoup:jsoup:1.17.2'

// 이미지 추출 예시
private String extractImageUrl(SyndEntry entry) {
    // 1. media:content 태그 확인
    List<SyndEnclosure> enclosures = entry.getEnclosures();
    if (!enclosures.isEmpty()) {
        SyndEnclosure enclosure = enclosures.get(0);
        if (enclosure.getType().startsWith("image/")) {
            return enclosure.getUrl();
        }
    }
    
    // 2. description의 HTML에서 img 태그 추출 (Jsoup 사용)
    if (entry.getDescription() != null) {
        String html = entry.getDescription().getValue();
        Document doc = Jsoup.parse(html);
        Element img = doc.selectFirst("img");
        if (img != null) {
            return img.attr("src");
        }
    }
    
    // 3. 기본 이미지 반환
    return "https://placehold.co/400x250/000000/FFFFFF?text=RSS";
}
```

---

### 3.2 NewsService 리팩토링 전략

#### ✅ 전략 2: NewsService를 래퍼로 유지 (최종 권장)

**핵심 전략**: `query` 파라미터의 이중 역할 처리

```
NewsService.searchNews(query, display, start)
  ↓
  [query 판별]
  ├─ 정의된 카테고리명? (예: "경제", "IT/과학")
  │   └─→ RSS URL로 매핑 → RssService.fetchNewsFromRss(rssUrl) 호출
  │
  └─ 자유 검색어? (예: "청년 창업", "AI 윤리")
      └─→ 네이버 API 제한적 호출 (토큰 낭비 최소화)
          또는 RSS 데이터 수집 후 메모리 필터링
```

#### 구체적 구현 로직

```java
public List<NewsArticle> searchNews(String query, Integer display, Integer start) {
    // 1. query가 정의된 카테고리명인지 확인
    String rssUrl = rssUrlMapper.getRssUrlByCategory(query);
    
    if (rssUrl != null) {
        // 카테고리명 → RSS URL 매핑 성공
        List<NewsArticle> articles = rssService.fetchNewsFromRss(rssUrl);
        
        // 2. 날짜순 정렬 (이미 RssService에서 처리 가능)
        // 3. display 파라미터로 limit 처리
        // 4. start 파라미터로 offset 처리 (메모리 페이징)
        return applyPaging(articles, display, start);
    } else {
        // 자유 검색어 → 네이버 API 호출 (제한적)
        // 또는 RSS 데이터 풀에서 필터링
        return searchFromRssPool(query, display, start);
    }
}
```

#### 장점
- ✅ **NewsController 수정 최소화**: 기존 인터페이스 유지
- ✅ **하위 호환성**: 기존 API 클라이언트 영향 없음
- ✅ **유연성**: 카테고리와 검색어 모두 지원
- ✅ **점진적 전환**: RSS 우선, 필요시 API 폴백

---

#### 전략 1: NewsService를 RSS 기반으로 완전 교체
```
NewsService.searchNews(query, display, start)
  ↓
NewsService.searchNews(category, display) 
  → RssService.fetchNewsFromRss(rssUrl) 호출
  → 카테고리 → RSS URL 매핑 필요
```
**단점**: 기존 API 인터페이스 변경 필요, 호환성 문제

#### 전략 3: 하이브리드 접근
```
- NewsService: 네이버 API와 RSS 모두 지원
- 설정으로 API/RSS 선택 가능
- 점진적 마이그레이션 가능
```
**장점**: 유연성, **단점**: 복잡도 증가

---

## 4. NewsController 수정 전략

### `/search` 엔드포인트
- **변경 없음**: NewsService가 내부적으로 처리
- `query` → NewsService에서 카테고리/검색어 판별
- 기존 클라이언트 코드 영향 없음

### `/latest` 엔드포인트
- 각 카테고리별 RSS URL로 변경
- **현재**: `newsService.searchNews("경제", 15, 1)`
- **변경**: `newsService.searchNews("경제", 15, 1)` (내부적으로 RSS 사용)
- 각 RSS에서 가져온 후 limit 처리

---

## 5. 구현 단계별 전략

### Phase 1: RssService 완성
1. [ ] **`formatDate()` 구현 - 다중 날짜 포맷 지원 (중요)**
   - RFC 822, ISO 8601 등 다양한 포맷 시도
   - 강력한 예외 처리 로직 포함
   - 자세한 내용은 [6.4 날짜 처리의 중요성](#64-날짜-처리의-중요성-중요) 참고
2. [ ] **Jsoup 라이브러리 추가 및 이미지 추출 로직 구현**
3. [ ] HTML 태그 제거 로직 추가
4. [ ] 날짜 정렬 기능 추가
5. [ ] 에러 핸들링 강화

### Phase 2: 카테고리 → RSS URL 매핑
1. [ ] **별도 설정 파일 생성** (rss-urls.json 또는 rss-urls.yml)
2. [ ] `RssUrlMapper` 클래스 구현
3. [ ] 카테고리별 다중 출처 RSS URL 등록
4. [ ] 동적 로딩 기능 구현 (코드 수정 없이 URL 변경 가능)

### Phase 3: NewsService 수정
1. [ ] `searchNews()` 메서드에 query 판별 로직 추가
2. [ ] 카테고리명 → RSS URL 매핑 로직 추가
3. [ ] **비동기 병렬 처리 구현 (필수)**
   - CompletableFuture 또는 WebClient 활용
   - 다중 RSS 피드 병렬 호출
   - 자세한 내용은 [6.5 비동기 병렬 처리](#65-비동기-병렬-처리-필수) 참고
4. [ ] display 파라미터로 limit 처리
5. [ ] **start 파라미터로 메모리 페이징 구현**
   - 초기에는 메모리 페이징 사용
   - 데이터 풀 크기 모니터링
   - 자세한 내용은 [6.2 페이징 및 개수 제한 극복](#62-페이징-및-개수-제한-극복-중요) 참고
6. [ ] 자유 검색어 처리 로직 추가 (RSS 풀 필터링 또는 API 폴백)

### Phase 4: 캐싱 전략 구현 (필수)
1. [ ] **Redis 또는 메모리 캐시 설정**
2. [ ] RSS 피드 수집 결과 캐싱 (5-30분 TTL)
3. [ ] NewsController가 캐시에서 데이터 조회하도록 수정
4. [ ] 캐시 무효화 전략 수립

### Phase 5: NewsController 수정
1. [ ] `/search`: 내부적으로 RSS 사용 (인터페이스 유지)
2. [ ] `/latest`: RSS 기반으로 동작 확인
3. [ ] 에러 핸들링 및 로깅 강화

---

## 6. 주의사항 및 제약사항

### RSS의 제약사항
- ❌ **검색어 기능 없음**: RSS는 최신 기사 목록만 제공
- ❌ **페이징 제한**: `start` 파라미터 의미 없음 (항상 최신부터)
- ⚠️ **개수 제한**: RSS 피드마다 제공 개수 다름 (보통 20-50개)
- ⚠️ **실시간성**: RSS 업데이트 주기에 의존

---

### 🚨 필수 해결 방안

#### 6.1 캐싱 전략의 의무화 (필수 구현)

**문제점**: 
- RSS는 실시간성이 API보다 떨어짐
- 잦은 호출은 불필요하고 대상 서버에 부하를 줌
- 네트워크 비용 증가

**해결책**:
1. **서버 측 캐싱 필수**
   - Redis 또는 인메모리 캐시 (Caffeine 등) 사용
   - TTL: 5분 ~ 30분 (설정 가능)
   - 카테고리별로 개별 캐싱

2. **캐시 키 전략**
   ```
   cache:rss:category:{category}:limit:{limit}
   예: cache:rss:category:economy:limit:20
   ```

3. **캐시 갱신 전략**
   - 백그라운드 스케줄러로 주기적 갱신 (예: 5분마다)
   - 클라이언트 요청 시 캐시 미스 시에만 RSS 호출
   - NewsController는 항상 캐시에서 조회

4. **구현 예시**
   ```java
   @Cacheable(value = "rssFeeds", key = "#category + ':' + #limit")
   public List<NewsArticle> getCachedRssNews(String category, int limit) {
       // RSS 피드 수집
       return rssService.fetchNewsFromRss(rssUrl);
   }
   ```

---

#### 6.2 페이징 및 개수 제한 극복 (중요)

**문제점**: 
- RSS 피드는 보통 20-50개만 제공
- `start` 파라미터 지원 안 함

**해결책**: 하이브리드 페이징 전략 (데이터 풀 확장 + 메모리/DB 페이징)

**전략 요약**: 
초기에는 간단한 메모리 페이징을 사용하고, 데이터 풀이 커지면 DB 기반의 OFFSET/LIMIT 페이징으로 전환하는 전략은 **성능과 리소스 관리라는 두 마리 토끼를 잡을 수 있는 최적의 방안**입니다.

##### 1단계: 데이터 풀 확장
```
여러 언론사 RSS 통합
  ↓
카테고리별 다중 출처 수집
  예) "경제" 카테고리:
      - 연합뉴스 경제 RSS (20개)
      - 한겨레 경제 RSS (20개)
      - 매일경제 RSS (20개)
      = 총 60개 기사 풀 생성
  ↓
병합 및 중복 제거 (제목 기준)
  ↓
날짜순 정렬
  ↓
데이터 풀 완성 (예: 50-100개)
```

##### 2단계: 메모리 페이징 구현 (초기 단계)

**⚠️ 메모리 페이징의 한계 인지**

메모리 페이징은 초기 단계에서 효과적이지만, 데이터 풀 크기가 커지면 서버 메모리에 부하를 줄 수 있습니다.

```java
private List<NewsArticle> applyPaging(
    List<NewsArticle> articles, 
    Integer display, 
    Integer start
) {
    // 1. 날짜순 정렬 (이미 정렬되어 있을 수 있음)
    articles.sort((a, b) -> {
        // 날짜 내림차순 정렬
        return b.getDate().compareTo(a.getDate());
    });
    
    // 2. start 파라미터로 offset 적용
    int offset = (start != null && start > 0) ? start - 1 : 0;
    int fromIndex = Math.min(offset, articles.size());
    
    // 3. display 파라미터로 limit 적용
    int limit = (display != null && display > 0) ? display : 20;
    int toIndex = Math.min(fromIndex + limit, articles.size());
    
    // 4. 서브리스트 반환
    return articles.subList(fromIndex, toIndex);
}
```

**메모리 페이징 한계점**:
- ❌ 데이터 풀이 수천 개로 커지면 서버 메모리 부하
- ❌ 대량 데이터 처리 시 성능 저하
- ❌ JVM 힙 메모리 부족 가능성

**대안: 하이브리드 페이징 전략 (최적의 방안)**

데이터 풀 크기가 **500~1000개를 초과**하면 DB 기반 페이징으로 전환을 고려해야 합니다.

**핵심 가치**: 성능과 리소스 관리의 균형
- ✅ **초기 단계**: 간단한 메모리 페이징으로 빠른 구현 및 낮은 지연시간
- ✅ **확장 단계**: DB 기반 페이징으로 메모리 부하 해소 및 대규모 데이터 처리
- ✅ **자동 전환**: 데이터 풀 크기 모니터링을 통한 자동 전환 로직
- ✅ **최적화**: 각 단계에서 최적의 성능과 리소스 효율성 확보

```java
// 데이터 풀 크기 체크
if (articles.size() > 1000) {
    // DB에 임시 저장
    saveToDatabase(articles);
    
    // DB 기반 페이징 사용
    return getPagedArticlesFromDB(display, start);
} else {
    // 메모리 페이징 사용
    return applyPaging(articles, display, start);
}
```

**DB 기반 페이징 구현**:
```java
// PostgreSQL 예시
@Query(value = "SELECT * FROM news_articles " +
               "WHERE category = :category " +
               "ORDER BY published_date DESC " +
               "LIMIT :limit OFFSET :offset",
       nativeQuery = true)
List<NewsArticle> findPagedArticles(
    @Param("category") String category,
    @Param("limit") int limit,
    @Param("offset") int offset
);
```

**전환 전략**:
1. **초기 단계**: 메모리 페이징 사용 (데이터 풀 < 500개)
2. **모니터링**: 데이터 풀 크기 지속 모니터링
3. **전환 기준**: 데이터 풀 > 1000개 또는 메모리 사용률 > 70%
4. **DB 저장**: RSS 수집 결과를 PostgreSQL에 임시 저장
5. **DB 페이징**: OFFSET/LIMIT으로 페이징 처리
6. **TTL 관리**: 오래된 기사는 자동 삭제 (예: 7일 이상)

**효과**:
- ✅ **메모리 부하 감소**: JVM 힙 메모리 효율적 사용
- ✅ **대량 데이터 처리 가능**: 수천~수만 개 기사 처리 가능
- ✅ **확장성 향상**: 데이터 증가에 따른 자동 대응
- ✅ **성능 유지**: DB 인덱스 활용으로 페이징 성능 보장
- ✅ **리소스 최적화**: 메모리와 DB를 상황에 맞게 활용

##### 3단계: 캐시와 페이징 통합
- 데이터 풀을 캐시에 저장 (메모리 페이징 시)
- 또는 DB에 저장 (DB 페이징 시)
- 페이징은 캐시/DB에서 수행
- 캐시 갱신 시에만 RSS 호출

**하이브리드 페이징 전략의 최종 효과**:
- ✅ **RSS 개수 제한 극복**: 여러 출처 통합으로 데이터 풀 확장
- ✅ **`start` 파라미터 지원**: 메모리/DB 페이징으로 완전한 페이징 지원
- ✅ **성능 향상**: 캐시 활용으로 빠른 응답 시간
- ✅ **확장성 확보**: DB 페이징으로 대규모 데이터 처리 가능
- ✅ **리소스 효율**: 상황에 맞는 최적의 페이징 방식 자동 선택
- ✅ **성능과 리소스의 균형**: 두 마리 토끼를 잡는 최적의 방안

---

#### 6.3 검색어 처리 전략

**자유 검색어가 필요한 경우**:

1. **옵션 A: RSS 데이터 풀에서 필터링** (권장)
   ```java
   // 모든 RSS 피드를 수집하여 풀 생성
   List<NewsArticle> allArticles = collectAllRssFeeds();
   
   // 메모리에서 검색어 필터링
   return allArticles.stream()
       .filter(article -> 
           article.getTitle().contains(query) || 
           article.getDescription().contains(query)
       )
       .limit(display)
       .collect(Collectors.toList());
   ```
   - 장점: API 호출 없음, 비용 절감
   - 단점: 검색 범위가 RSS 풀에 한정됨

2. **옵션 B: 네이버 API 제한적 호출**
   - 검색어가 카테고리명이 아닌 경우에만 API 호출
   - 토큰 사용량 최소화
   - 폴백 전략으로 활용

---

#### 6.4 날짜 처리의 중요성 (중요)

**문제점**: 
- RSS 피드의 날짜 포맷은 표준이 아닌 경우가 많음
- 각 언론사마다 다른 날짜 포맷 사용
- 파싱 실패 시 데이터 손실 발생

**Rome 라이브러리의 한계**:
- Rome은 자체적으로 날짜 파싱을 시도하지만 실패하는 경우가 많음
- `entry.getPublishedDate()`가 `null`을 반환할 수 있음

**해결책: java.time을 활용한 다중 날짜 포맷 지원**

**전략 요약**: 
RSS 데이터의 고질적인 문제인 날짜 포맷 비표준 문제를 **`java.time` API를 활용한 다중 포맷 시도 로직**으로 해결하여 **데이터 품질을 보장**합니다.

`formatDate()` 메서드에 여러 날짜 포맷 패턴을 시도하는 강력한 예외 처리 로직을 포함해야 합니다.

```java
private String formatDate(Date date) {
    if (date == null) {
        log.warn("날짜가 null입니다. 현재 날짜 반환");
        return LocalDateTime.now().format(DateTimeFormatter.ofPattern("yyyy.MM.dd"));
    }
    
    // java.util.Date를 LocalDateTime으로 변환
    Instant instant = date.toInstant();
    LocalDateTime localDateTime = LocalDateTime.ofInstant(instant, ZoneId.systemDefault());
    
    // 표준 포맷으로 변환
    return localDateTime.format(DateTimeFormatter.ofPattern("yyyy.MM.dd"));
}

// SyndEntry에서 날짜 추출 (다중 포맷 시도)
private Date extractPublishedDate(SyndEntry entry) {
    // 1. publishedDate 시도
    if (entry.getPublishedDate() != null) {
        return entry.getPublishedDate();
    }
    
    // 2. updatedDate 시도
    if (entry.getUpdatedDate() != null) {
        return entry.getUpdatedDate();
    }
    
    // 3. description이나 기타 필드에서 날짜 문자열 추출 시도
    String dateStr = extractDateFromDescription(entry);
    if (dateStr != null) {
        return parseDateString(dateStr);
    }
    
    // 4. 모두 실패 시 현재 날짜 반환
    log.warn("날짜 추출 실패: entry={}", entry.getTitle());
    return new Date();
}

// 다양한 날짜 포맷 파싱 시도
private Date parseDateString(String dateStr) {
    List<DateTimeFormatter> formatters = Arrays.asList(
        DateTimeFormatter.RFC_1123_DATE_TIME,  // RFC 822 (예: "Wed, 13 Dec 2025 10:30:00 +0900")
        DateTimeFormatter.ISO_DATE_TIME,       // ISO 8601 (예: "2025-12-13T10:30:00+09:00")
        DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss"),
        DateTimeFormatter.ofPattern("yyyy.MM.dd HH:mm:ss"),
        DateTimeFormatter.ofPattern("yyyy-MM-dd"),
        DateTimeFormatter.ofPattern("yyyy.MM.dd")
    );
    
    for (DateTimeFormatter formatter : formatters) {
        try {
            // ZonedDateTime으로 파싱 시도
            ZonedDateTime zonedDateTime = ZonedDateTime.parse(dateStr, formatter);
            return Date.from(zonedDateTime.toInstant());
        } catch (Exception e) {
            // 다음 포맷 시도
            continue;
        }
    }
    
    // 모든 포맷 실패
    log.warn("날짜 파싱 실패: dateStr={}", dateStr);
    return new Date(); // 현재 날짜 반환
}
```

**핵심 가치**: 데이터 품질 보장

RSS 데이터의 고질적인 문제인 날짜 포맷 비표준 문제를 `java.time` API를 활용한 다중 포맷 시도 로직으로 해결하여 데이터 품질을 보장합니다.

**java.time API 활용의 장점**:
- ✅ **표준화**: Java 8+ 표준 날짜/시간 API 사용
- ✅ **타입 안정성**: `LocalDateTime`, `ZonedDateTime` 등 명확한 타입
- ✅ **타임존 처리**: 자동 타임존 변환 지원
- ✅ **불변성**: Thread-safe한 불변 객체
- ✅ **확장성**: 새로운 포맷 추가 용이

**구현 팁**:
1. **다양한 포맷 지원**: RFC 822, ISO 8601, 커스텀 포맷 등
2. **폴백 전략**: publishedDate → updatedDate → description 추출 → 현재 날짜
3. **로깅**: 파싱 실패 시 로그 기록 (모니터링용)
4. **기본값**: 파싱 실패 시 현재 날짜 반환 (데이터 손실 방지)
5. **java.time 활용**: `DateTimeFormatter`, `ZonedDateTime` 등 활용
6. **데이터 품질 보장**: 파싱 실패율 최소화로 신뢰성 향상

---

#### 6.5 비동기 병렬 처리 (필수)

**문제점**: 
- 다중 RSS 피드를 순차적으로 호출하면 시간이 오래 걸림
- 예: 10개 RSS 피드 × 평균 1초 = 10초 대기
- 사용자 경험 저하
- 배치 작업 시 비효율적인 리소스 사용

**해결책**: 비동기 병렬 처리

**핵심 가치**: 응답 시간 단축 및 배치 작업 효율성 극대화

여러 RSS 피드를 순차적으로 처리하는 대신 병렬로 처리하여:
- ✅ **응답 시간 획기적 단축**: 10초 → 1-2초 (5-10배 향상)
- ✅ **토큰 낭비 방지**: RSS는 무료이므로 API 토큰 사용 없음 (네이버 API 대비)
- ✅ **배치 작업 효율성 극대화**: 백그라운드 스케줄러에서 여러 피드를 동시에 수집하여 배치 작업 시간 최소화
- ✅ **리소스 활용 최적화**: I/O 대기 시간 동안 다른 작업 처리
- ✅ **확장성**: 피드 개수 증가에 따른 성능 저하 최소화

**전략 요약**: 
여러 RSS 피드를 순차적으로 처리하는 대신 병렬로 처리하여 **응답 시간을 획기적으로 단축**하고, **토큰 낭비를 막는 배치 작업의 효율성을 극대화**합니다.

##### 구현 방법 1: CompletableFuture 활용 (권장)

```java
@Service
public class RssService {
    
    @Autowired
    private ExecutorService executorService; // ThreadPool 설정 필요
    
    /**
     * 여러 RSS URL을 병렬로 호출
     */
    public List<NewsArticle> fetchMultipleRssFeeds(List<String> rssUrls) {
        // 1. 각 RSS URL에 대해 CompletableFuture 생성
        List<CompletableFuture<List<NewsArticle>>> futures = rssUrls.stream()
            .map(url -> CompletableFuture.supplyAsync(() -> {
                try {
                    return fetchNewsFromRss(url);
                } catch (Exception e) {
                    log.error("RSS 피드 수집 실패: URL={}", url, e);
                    return List.<NewsArticle>of(); // 빈 리스트 반환
                }
            }, executorService))
            .collect(Collectors.toList());
        
        // 2. 모든 Future가 완료될 때까지 대기
        CompletableFuture<Void> allFutures = CompletableFuture.allOf(
            futures.toArray(new CompletableFuture[0])
        );
        
        // 3. 모든 결과 수집 및 병합
        return allFutures.thenApply(v -> 
            futures.stream()
                .map(CompletableFuture::join)
                .flatMap(List::stream)
                .collect(Collectors.toList())
        ).join();
    }
}
```

**ThreadPool 설정**:
```java
@Configuration
public class AsyncConfig {
    
    @Bean(name = "rssExecutor")
    public ExecutorService rssExecutor() {
        return Executors.newFixedThreadPool(20); // 동시에 20개 RSS 피드 처리
    }
}
```

##### 구현 방법 2: WebClient 활용 (비동기 HTTP 클라이언트)

```java
@Service
public class RssService {
    
    private final WebClient webClient;
    
    public RssService() {
        this.webClient = WebClient.builder()
            .clientConnector(new ReactorClientHttpConnector(
                HttpClient.create()
                    .option(ChannelOption.CONNECT_TIMEOUT_MILLIS, 5000)
                    .responseTimeout(Duration.ofSeconds(10))
            ))
            .build();
    }
    
    /**
     * 여러 RSS URL을 비동기로 호출
     */
    public Mono<List<NewsArticle>> fetchMultipleRssFeedsAsync(List<String> rssUrls) {
        // 1. 각 URL에 대해 Mono 생성
        List<Mono<List<NewsArticle>>> monos = rssUrls.stream()
            .map(url -> webClient.get()
                .uri(url)
                .retrieve()
                .bodyToMono(String.class)
                .map(this::parseRssFeed)
                .onErrorResume(e -> {
                    log.error("RSS 피드 수집 실패: URL={}", url, e);
                    return Mono.just(List.<NewsArticle>of());
                }))
            .collect(Collectors.toList());
        
        // 2. 모든 Mono를 병합
        return Flux.fromIterable(monos)
            .flatMap(mono -> mono)
            .collectList()
            .map(lists -> lists.stream()
                .flatMap(List::stream)
                .collect(Collectors.toList()));
    }
}
```

**WebClient 의존성 추가**:
```gradle
dependencies {
    implementation 'org.springframework.boot:spring-boot-starter-webflux'
}
```

##### 성능 비교

| 방식 | 10개 RSS 피드 처리 시간 | 30개 RSS 피드 처리 시간 | 장점 | 단점 |
|------|----------------------|----------------------|------|------|
| 순차 처리 | ~10초 | ~30초 | 구현 간단 | 느림, 배치 작업 비효율 |
| CompletableFuture | ~1-2초 | ~2-3초 | 구현 간단, Spring 기본 제공, 배치 효율 | ThreadPool 관리 필요 |
| WebClient | ~1-2초 | ~2-3초 | 비동기 I/O, 리소스 효율적, 배치 효율 | WebFlux 의존성 필요 |

**성능 향상 효과**:
- 순차 처리 대비 **5-15배 성능 향상**
- 배치 작업 시간 **90% 이상 단축** (30초 → 2-3초)
- 서버 리소스 활용률 **대폭 향상**

**권장 사항**:
- ✅ **CompletableFuture**: Spring Boot 기본 제공, 구현 간단
- ✅ **WebClient**: 대규모 처리 시 리소스 효율적
- ⚠️ **ThreadPool 크기**: RSS 피드 개수에 맞게 조정 (예: 피드 개수 × 1.5)

**배치 작업 효율성 극대화**:

백그라운드 스케줄러에서 RSS 피드를 주기적으로 수집할 때, 병렬 처리를 통해:
- **시간 절약**: 30개 피드 순차 처리 시 30초 → 병렬 처리 시 2-3초
- **서버 리소스 효율**: CPU와 네트워크 I/O를 최대한 활용
- **캐시 갱신 속도**: 빠른 수집으로 캐시 갱신 주기 단축 가능
- **확장성**: 피드 개수 증가에도 성능 유지

**구현 시 주의사항**:
1. **Timeout 설정**: 각 RSS 호출에 타임아웃 설정 (예: 10초)
2. **에러 핸들링**: 일부 RSS 실패 시에도 다른 피드는 정상 처리
3. **리소스 관리**: ThreadPool 크기 적절히 설정
4. **로깅**: 병렬 처리 상태 모니터링
5. **배치 최적화**: 스케줄러에서 병렬 처리로 배치 작업 시간 최소화

---

## 7. 설정 관리 전략

### ⚠️ 기존 방식의 문제점
- `application.yml`에 RSS URL을 하드코딩하면 코드 수정 없이 URL 변경이 어려움
- 운영 중 URL 변경 시 재배포 필요

### ✅ 개선된 설정 관리 전략

#### 옵션 1: 별도 설정 파일 (권장 - 중소규모)
```
프로젝트 구조:
src/main/resources/
  ├── application.yml
  └── rss-urls.yml  (또는 rss-urls.json)
```

**rss-urls.yml 예시**:
```yaml
rss:
  sources:
    economy:
      - name: "연합뉴스 경제"
        url: "https://www.yna.co.kr/rss/economy.xml"
        enabled: true
      - name: "한겨레 경제"
        url: "https://www.hani.co.kr/rss/economy/"
        enabled: true
      - name: "매일경제"
        url: "https://www.mk.co.kr/rss/30000041/"
        enabled: true
    
    politics:
      - name: "연합뉴스 정치"
        url: "https://www.yna.co.kr/rss/politics.xml"
        enabled: true
      - name: "한겨레 정치"
        url: "https://www.hani.co.kr/rss/politics/"
        enabled: true
    
    # ... 기타 카테고리
```

**장점**:
- 코드 수정 없이 URL 변경 가능
- 카테고리별 다중 출처 관리 용이
- `enabled` 플래그로 출처 활성화/비활성화 가능

---

#### 옵션 2: 외부 설정 서비스 (권장 - 대규모/운영 환경)

**AWS Systems Manager Parameter Store (SSM) 활용**
```java
@Configuration
public class RssUrlConfig {
    
    @Value("${aws.ssm.parameter.path:/news-service/rss-urls}")
    private String ssmParameterPath;
    
    @Bean
    public RssUrlMapper rssUrlMapper() {
        // SSM에서 RSS URL 목록 동적 로딩
        String rssUrlsJson = ssmClient.getParameter(ssmParameterPath);
        return parseRssUrls(rssUrlsJson);
    }
}
```

**장점**:
- 코드/배포 없이 URL 변경 가능
- 중앙 집중식 관리
- 버전 관리 및 롤백 가능
- 보안 강화 (민감 정보 암호화)

**대안**:
- **Spring Cloud Config Server**: 설정 서버 활용
- **데이터베이스**: RSS URL을 DB에 저장하고 관리자 페이지에서 수정
- **환경 변수**: Docker/K8s 환경 변수 활용

---

#### 옵션 3: 하이브리드 접근
```yaml
# application.yml
rss:
  config-source: "file"  # file, ssm, db
  config-file: "rss-urls.yml"
  cache-ttl: 300  # 5분
  max-articles-per-source: 50
```

---

### 카테고리 매핑 예시
```java
public enum NewsCategory {
    ECONOMY("경제", "economy"),
    POLITICS("정치", "politics"),
    SOCIETY("사회", "society"),
    CULTURE("문화", "culture"),
    WORLD("세계", "world"),
    IT_SCIENCE("IT/과학", "it-science"),
    SPORTS("스포츠", "sports"),
    ENTERTAINMENT("연예", "entertainment");
    
    private final String koreanName;
    private final String configKey;
}
```

---

## 8. 마이그레이션 전략 (점진적 전환)

### 단계별 마이그레이션

#### Phase 0: 준비 단계
1. ✅ **RssService 완성** - 기본 RSS 파싱 기능 구현
2. ✅ **Rome Tools 의존성 추가** - build.gradle
3. ⏳ **Jsoup 의존성 추가** - 이미지 추출용

#### Phase 1: RSS 인프라 구축
1. ⏳ **RssUrlMapper 구현** - 설정 파일 로딩
2. ⏳ **다중 출처 RSS URL 등록** - 주요 언론사 RSS 추가
3. ⏳ **RssService 개선** - 이미지 추출, 날짜 포맷팅 완성

#### Phase 2: NewsService 통합
1. ⏳ **NewsService에 RSS 모드 추가** - 설정으로 선택 가능하도록
2. ⏳ **query 판별 로직 구현** - 카테고리명 vs 검색어
3. ⏳ **데이터 풀 확장 로직** - 다중 출처 통합
4. ⏳ **메모리 페이징 구현** - start 파라미터 지원

#### Phase 3: 캐싱 전략 구현 (필수)
1. ⏳ **캐시 인프라 구축** - Redis 또는 인메모리 캐시
2. ⏳ **캐시 로직 구현** - RSS 피드 결과 캐싱
3. ⏳ **스케줄러 구현** - 백그라운드 캐시 갱신
4. ⏳ **NewsController 수정** - 캐시에서 데이터 조회

#### Phase 4: 테스트 및 검증
1. ⏳ **단위 테스트** - 각 컴포넌트 테스트
2. ⏳ **통합 테스트** - 전체 플로우 테스트
3. ⏳ **성능 테스트** - 캐시 효과 검증
4. ⏳ **부하 테스트** - RSS 서버 부하 모니터링

#### Phase 5: 프로덕션 전환
1. ⏳ **스테이징 환경 배포** - 검증
2. ⏳ **프로덕션 배포** - RSS 모드로 전환
3. ⏳ **모니터링 강화** - RSS 피드 가용성 체크
4. ⏳ **네이버 API 코드 제거** (선택) - 완전 전환 시 제거

### 롤백 계획
- 설정으로 API/RSS 모드 전환 가능하도록 유지
- 문제 발생 시 즉시 API 모드로 롤백
- 캐시 무효화로 즉시 반영

---

## 📝 추가 고려사항

### 성능 최적화
- ✅ **RSS 피드 캐싱** (5-30분 간격, 필수)
- ✅ **비동기 병렬 처리** (CompletableFuture 또는 WebClient 활용)
  - 다중 RSS 피드 동시 수집
  - ThreadPool 최적화
  - 성능 향상: 순차 처리 10초 → 병렬 처리 1-2초
- ✅ **에러 핸들링** (일부 RSS 실패 시에도 다른 피드는 정상 동작)
- ✅ **Connection Pool** 설정 (RSS 서버 부하 최소화)
- ✅ **Timeout 설정** (응답 지연 시 빠른 실패)
- ✅ **메모리 관리**
  - 데이터 풀 크기 모니터링
  - 메모리 페이징 → DB 페이징 전환 전략
  - JVM 힙 메모리 최적화

### 모니터링
- **RSS 피드 응답 시간 모니터링** - 느린 피드 식별
- **RSS 피드 가용성 체크** - 주기적 헬스체크
- **데이터 품질 모니터링** - 빈 피드, 파싱 에러 등
- **캐시 히트율 모니터링** - 캐시 효과 측정
- **에러 로그 집계** - 실패한 RSS 피드 추적
- **데이터 풀 크기 모니터링** - 메모리 부하 예측
- **날짜 파싱 실패율** - 날짜 포맷 이슈 추적
- **비동기 처리 성능** - 병렬 처리 효과 측정

### 보안 고려사항
- **RSS URL 검증** - 악성 URL 방지
- **Rate Limiting** - RSS 서버 부하 방지
- **User-Agent 설정** - 정상적인 요청으로 식별
- **HTTPS 우선** - 보안 연결 사용

---

## 🔗 참고 자료

### RSS 피드 출처
- **연합뉴스 RSS**: https://www.yna.co.kr/rss/
- **한겨레 RSS**: https://www.hani.co.kr/rss/
- **매일경제 RSS**: https://www.mk.co.kr/rss/
- **네이버 뉴스 RSS**: https://news.naver.com/main/rss/ (비공식, 주의)

### 라이브러리
- **Rome Tools**: https://rometools.github.io/rome/
  - Maven: `com.rometools:rome:1.18.0`
- **Jsoup**: https://jsoup.org/
  - Maven: `org.jsoup:jsoup:1.17.2`
- **Spring WebFlux** (WebClient 사용 시)
  - Maven: `org.springframework.boot:spring-boot-starter-webflux`

### 캐싱 라이브러리
- **Spring Cache**: Spring Boot 기본 제공
- **Caffeine**: 고성능 인메모리 캐시
  - Maven: `com.github.ben-manes.caffeine:caffeine`
- **Redis**: 분산 캐시
  - Spring Data Redis 사용

---

## ✅ 체크리스트

### 필수 구현 항목
- [ ] **RssService 완성**
  - [ ] `formatDate()` 구현 - 다중 날짜 포맷 지원 (RFC 822, ISO 8601 등)
  - [ ] 이미지 추출 로직 (Jsoup 활용)
  - [ ] HTML 태그 제거 로직
  - [ ] 날짜 정렬 기능
- [ ] **Jsoup 라이브러리 추가** 및 이미지 추출 로직
- [ ] **RssUrlMapper 구현** (설정 파일 로딩)
- [ ] **다중 출처 RSS URL 등록** (주요 언론사 공식 RSS)
- [ ] **NewsService query 판별 로직** (카테고리명 vs 검색어)
- [ ] **비동기 병렬 처리 구현** (CompletableFuture 또는 WebClient)
  - [ ] ThreadPool 설정
  - [ ] Timeout 설정
  - [ ] 에러 핸들링 (일부 실패 시에도 정상 처리)
- [ ] **데이터 풀 확장** (다중 출처 통합)
- [ ] **메모리 페이징 구현** (초기 단계)
- [ ] **데이터 풀 크기 모니터링** (500-1000개 기준)
- [ ] **DB 기반 페이징 전환 준비** (데이터 풀 > 1000개 시)
- [ ] **캐싱 전략 구현 (필수)**
  - [ ] Redis 또는 인메모리 캐시 설정
  - [ ] TTL 설정 (5-30분)
  - [ ] 캐시 키 전략
- [ ] **백그라운드 스케줄러** (캐시 갱신)
- [ ] **에러 핸들링 강화**

### 선택 구현 항목
- [ ] **AWS SSM 연동** (설정 관리)
- [ ] **Redis 캐시** (분산 환경)
- [ ] **DB 기반 페이징** (PostgreSQL 활용)
- [ ] **관리자 페이지** (RSS URL 관리)
- [ ] **모니터링 대시보드**
  - [ ] RSS 피드 응답 시간
  - [ ] 데이터 풀 크기
  - [ ] 캐시 히트율
  - [ ] 에러 로그 집계

---

**최종 업데이트**: 2025-12-14
**버전**: 2.2 (핵심 전략 가치 강화 및 성능 최적화 보완)

### 주요 개선 사항 (v2.2)
- ✅ **하이브리드 페이징 전략**: 성능과 리소스 관리의 균형 강조
- ✅ **비동기 병렬 처리**: 배치 작업 효율성 극대화 및 토큰 낭비 방지
- ✅ **날짜 파싱 강화**: java.time 활용으로 데이터 품질 보장
- ✅ **성능 비교표 보강**: 구체적인 성능 향상 수치 추가
