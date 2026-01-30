# 연합뉴스 RSS 이미지 추출 전략

## 📋 문제 정의

연합뉴스 RSS 피드에서 이미지가 추출되지 않아 모든 기사가 플레이스홀더 이미지로 표시되는 문제

### 현재 상태
- ✅ RSS 피드 수집: 성공 (120개 기사)
- ❌ 이미지 추출: 실패 (모두 플레이스홀더)
- ✅ 3단계 폴백 전략: 구현 완료
  - 1단계: Enclosure/Media 태그
  - 2단계: Description HTML 파싱
  - 2-1단계: Content:Encoded 파싱 (**이미 구현됨**)
  - 3단계: 플레이스홀더

---

## 🔍 원인 분석

### 연합뉴스 RSS 특징
1. **표준 태그 미사용**: `<enclosure>`, `<media:content>` 등을 직접 제공하지 않음
2. **HTML 임베딩 방식**: 이미지가 `<description>` 또는 `<content:encoded>` 내 HTML로 포함
3. **다양한 형식**: 이미지 URL이 다양한 방식으로 인코딩됨

### 예상되는 RSS 구조

#### 케이스 1: Description에 HTML 포함
```xml
<item>
  <title>뉴스 제목</title>
  <description>
    <![CDATA[
      <img src="https://img.yonhapnews.co.kr/photo/123.jpg" />
      <p>기사 내용...</p>
    ]]>
  </description>
</item>
```

#### 케이스 2: Content:Encoded에 전체 HTML
```xml
<item>
  <title>뉴스 제목</title>
  <description>간단한 요약</description>
  <content:encoded>
    <![CDATA[
      <div class="article">
        <img src="https://img.yonhapnews.co.kr/photo/456.jpg" />
        <p>전체 기사 내용...</p>
      </div>
    ]]>
  </content:encoded>
</item>
```

#### 케이스 3: 이미지 URL만 텍스트로
```xml
<item>
  <title>뉴스 제목</title>
  <description>
    https://img.yonhapnews.co.kr/photo/789.jpg
    기사 내용...
  </description>
</item>
```

#### 케이스 4: 썸네일 태그 사용
```xml
<item>
  <title>뉴스 제목</title>
  <media:thumbnail url="https://img.yonhapnews.co.kr/photo/thumb.jpg" />
  <description>기사 내용...</description>
</item>
```

---

## 🎯 해결 전략

### 전략 1: 실제 RSS 피드 구조 분석 (최우선)

**목적**: 연합뉴스가 실제로 어떤 형식으로 이미지를 제공하는지 확인

**방법**:
1. 웹 브라우저에서 직접 확인
   ```
   https://www.yna.co.kr/rss/economy.xml
   ```

2. curl로 원본 XML 확인
   ```bash
   curl "https://www.yna.co.kr/rss/economy.xml" | grep -A 20 "<item>"
   ```

3. 첫 번째 item의 모든 태그 출력
   ```bash
   curl "https://www.yna.co.kr/rss/economy.xml" | 
   sed -n '/<item>/,/<\/item>/p' | head -50
   ```

**확인 항목**:
- [ ] `<enclosure>` 태그 존재 여부
- [ ] `<media:content>` 태그 존재 여부
- [ ] `<media:thumbnail>` 태그 존재 여부
- [ ] `<description>` 내용 형식 (HTML vs 텍스트)
- [ ] `<content:encoded>` 존재 여부 및 내용
- [ ] 이미지 URL 패턴 (img.yonhapnews.co.kr 등)

---

### 전략 2: Thumbnail 태그 지원 추가

**현재 미지원 태그**: `<media:thumbnail>`

**구현 위치**: `extractImageFromEnclosure()` 메서드 확장

**로직**:
```java
private String extractImageFromEnclosure(SyndEntry entry) {
    // 1. 기존 enclosure 확인
    List<SyndEnclosure> enclosures = entry.getEnclosures();
    for (SyndEnclosure enclosure : enclosures) {
        if (enclosure.getType() != null && enclosure.getType().startsWith("image/")) {
            return enclosure.getUrl();
        }
    }
    
    // 2. SyndEntry의 foreign markup 확인 (media:thumbnail 등)
    // Rome의 SyndEntry.getForeignMarkup() 사용
    Object foreignMarkup = entry.getForeignMarkup();
    if (foreignMarkup != null) {
        // JDOM Element로 캐스팅하여 media:thumbnail 찾기
        // namespace: http://search.yahoo.com/mrss/
    }
    
    return null;
}
```

**예상 XML 구조**:
```xml
<item xmlns:media="http://search.yahoo.com/mrss/">
  <media:thumbnail url="https://img.yonhapnews.co.kr/thumb.jpg" />
</item>
```

---

### 전략 3: 텍스트 내 URL 패턴 매칭

**목적**: HTML 태그 없이 URL만 있는 경우 처리

**구현 위치**: `extractImageFromHtml()` 실패 시 추가 단계

**로직**:
```java
private String extractImageUrlFromText(String text, String source) {
    if (text == null || text.isEmpty()) {
        return null;
    }
    
    // 연합뉴스 이미지 도메인 패턴
    String[] imagePatterns = {
        "https?://img\\.yonhapnews\\.co\\.kr/[^\\s\"'<>]+\\.(jpg|jpeg|png|gif|webp)",
        "https?://.*yonhap.*\\.(jpg|jpeg|png|gif|webp)",
        "https?://[^\\s\"'<>]+\\.(jpg|jpeg|png|gif|webp)"
    };
    
    for (String pattern : imagePatterns) {
        Pattern p = Pattern.compile(pattern, Pattern.CASE_INSENSITIVE);
        Matcher m = p.matcher(text);
        if (m.find()) {
            String url = m.group();
            log.debug("  → {} 텍스트에서 이미지 URL 발견: {}", source, url);
            return url;
        }
    }
    
    return null;
}
```

**호출 순서**:
1. HTML 파싱 시도 (`extractImageFromHtml`)
2. 실패 시 텍스트 패턴 매칭 (`extractImageUrlFromText`)

---

### 전략 4: OpenGraph 메타 태그 스크래핑 (최후 수단)

**목적**: RSS에서 이미지를 못 찾을 경우, 실제 기사 페이지를 방문하여 추출

**장점**:
- 거의 모든 언론사가 `og:image` 메타 태그 제공
- 고해상도 이미지 획득 가능

**단점**:
- 성능 저하 (HTTP 요청 필요)
- 언론사 서버 부하 증가
- 네트워크 의존성

**구현 로직**:
```java
private String extractImageFromArticlePage(String articleUrl) {
    try {
        // Jsoup으로 기사 페이지 스크래핑
        Document doc = Jsoup.connect(articleUrl)
            .timeout(3000)  // 3초 타임아웃
            .userAgent("Mozilla/5.0")
            .get();
        
        // 1. OpenGraph 이미지
        Element ogImage = doc.selectFirst("meta[property=og:image]");
        if (ogImage != null) {
            String content = ogImage.attr("content");
            if (isValidImageUrl(content)) {
                return content;
            }
        }
        
        // 2. Twitter Card 이미지
        Element twitterImage = doc.selectFirst("meta[name=twitter:image]");
        if (twitterImage != null) {
            String content = twitterImage.attr("content");
            if (isValidImageUrl(content)) {
                return content;
            }
        }
        
        // 3. 본문 내 첫 이미지
        Element firstImg = doc.selectFirst("article img, .article-body img");
        if (firstImg != null) {
            String src = firstImg.attr("src");
            if (isValidImageUrl(src)) {
                return src;
            }
        }
        
    } catch (Exception e) {
        log.warn("기사 페이지 스크래핑 실패: url={}, error={}", articleUrl, e.getMessage());
    }
    
    return null;
}
```

**주의사항**:
- 캐싱 필수 (Redis)
- Rate Limiting 적용
- 비동기 처리 권장
- 실패 시 빠른 fallback

---

### 전략 5: 연합뉴스 전용 커스텀 파서

**목적**: 연합뉴스만의 특수한 형식에 최적화된 파서 작성

**구현**:
```java
private String extractImageForYonhap(SyndEntry entry, String rssUrl) {
    // 연합뉴스인지 확인
    if (!rssUrl.contains("yonhapnews") && !rssUrl.contains("yna.co.kr")) {
        return null;
    }
    
    log.debug("연합뉴스 전용 이미지 추출 시도");
    
    // 1. Description 원본 확인 (CDATA 포함)
    if (entry.getDescription() != null) {
        String rawHtml = entry.getDescription().getValue();
        
        // 연합뉴스 특정 패턴
        // 예: <img src="//img.yonhapnews.co.kr/..." /> (프로토콜 없는 URL)
        String protocolLessPattern = "//img\\.yonhapnews\\.co\\.kr/[^\"'\\s]+";
        Pattern p = Pattern.compile(protocolLessPattern);
        Matcher m = p.matcher(rawHtml);
        if (m.find()) {
            return "https:" + m.group();
        }
    }
    
    // 2. Link URL에서 추출
    // 연합뉴스는 기사 URL에 이미지 ID가 포함될 수 있음
    String link = entry.getLink();
    if (link != null) {
        // URL 패턴 분석하여 이미지 URL 추측
        // 예: /view/AKR20231215... -> 특정 패턴
    }
    
    return null;
}
```

---

## 📊 통합 전략 플로우

```
RSS Entry 수신
    ↓
┌─────────────────────────────────────────┐
│ 0단계: 언론사 판별                       │
│ - 연합뉴스? → 전용 파서 우선            │
└─────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────┐
│ 1단계: 표준 태그 확인                    │
│ - <enclosure>                           │
│ - <media:content>                       │
│ - <media:thumbnail> ★ 추가 필요         │
└─────────────────────────────────────────┘
    ↓ (실패)
┌─────────────────────────────────────────┐
│ 2단계: Description HTML 파싱             │
│ - Jsoup 파싱                            │
│ - <img> 태그 찾기                       │
│ - src, data-src, data-lazy-src         │
└─────────────────────────────────────────┘
    ↓ (실패)
┌─────────────────────────────────────────┐
│ 2-1단계: Content:Encoded 파싱           │
│ - 전체 HTML 본문 파싱                   │
│ - 더 풍부한 콘텐츠                      │
└─────────────────────────────────────────┘
    ↓ (실패)
┌─────────────────────────────────────────┐
│ 2-2단계: 텍스트 URL 패턴 매칭 ★ 추가    │
│ - 정규표현식으로 이미지 URL 찾기        │
│ - 연합뉴스 도메인 우선                  │
└─────────────────────────────────────────┘
    ↓ (실패)
┌─────────────────────────────────────────┐
│ 2-3단계: 프로토콜 없는 URL 처리 ★ 추가  │
│ - //img.yonhapnews.co.kr/... 형식      │
│ - https: 프로토콜 자동 추가             │
└─────────────────────────────────────────┘
    ↓ (실패, 옵션)
┌─────────────────────────────────────────┐
│ 3단계: OpenGraph 스크래핑 (선택)        │
│ - 기사 페이지 방문                      │
│ - og:image 메타 태그 추출               │
│ - 성능 고려하여 선택적 적용             │
└─────────────────────────────────────────┘
    ↓ (실패)
┌─────────────────────────────────────────┐
│ 4단계: 플레이스홀더 이미지              │
└─────────────────────────────────────────┘
```

---

## 🛠 구현 우선순위

### Phase 1: 즉시 구현 (Critical)
1. **실제 RSS 구조 분석** (수동 작업)
   - 연합뉴스 RSS XML 직접 확인
   - 이미지 제공 방식 파악
   
2. **텍스트 URL 패턴 매칭 추가**
   - `extractImageUrlFromText()` 메서드
   - 정규표현식으로 이미지 URL 추출

3. **프로토콜 없는 URL 처리**
   - `//img.yonhapnews.co.kr/...` → `https://img.yonhapnews.co.kr/...`
   - `isValidImageUrl()` 메서드 확장

### Phase 2: 단기 개선 (Important)
1. **Thumbnail 태그 지원**
   - `<media:thumbnail>` 파싱
   - Rome 라이브러리의 Foreign Markup 활용

2. **연합뉴스 전용 파서**
   - 도메인별 커스텀 로직
   - 특수 패턴 처리

3. **디버그 로깅 강화**
   - 각 단계별 시도 로그
   - 실패 원인 명확히 출력

### Phase 3: 장기 개선 (Nice to Have)
1. **OpenGraph 스크래핑**
   - 성능 측정 후 적용 여부 결정
   - 캐싱 전략 필수

2. **이미지 URL 검증**
   - HTTP HEAD 요청으로 실제 접근 가능 여부 확인
   - 404 이미지 필터링

3. **이미지 품질 선택**
   - 여러 해상도 중 최적 선택
   - 썸네일 vs 원본 우선순위

---

## 🧪 테스트 전략

### 테스트 케이스

#### 1. 연합뉴스 경제 RSS
```
URL: https://www.yna.co.kr/rss/economy.xml
예상: 이미지 추출 성공 (80% 이상)
```

#### 2. 한겨레 경제 RSS
```
URL: https://www.hani.co.kr/rss/economy/
예상: 이미지 추출 성공 (기존 로직으로 가능)
```

#### 3. BBC News RSS (영문)
```
URL: http://feeds.bbci.co.uk/news/rss.xml
예상: Enclosure 태그로 100% 추출
```

#### 4. 이미지 없는 RSS
```
텍스트만 있는 피드
예상: 플레이스홀더 반환
```

### 성공 기준
- 연합뉴스 RSS: 이미지 추출률 **80% 이상**
- 전체 RSS 피드: 이미지 추출률 **70% 이상**
- 플레이스홀더 비율: **30% 이하**

---

## 📈 모니터링 지표

### 추가할 로그
```java
log.info("이미지 추출 통계: source={}, total={}, enclosure={}, description={}, content={}, text={}, placeholder={}", 
    source, total, enclosureCount, descCount, contentCount, textCount, placeholderCount);
```

### 메트릭
- 이미지 추출 성공률 (%)
- 각 단계별 성공 횟수
- 평균 추출 시간
- 실패 원인 분포

---

## 🔗 참고 자료

### RSS 명세
- [RSS 2.0 Specification](https://www.rssboard.org/rss-specification)
- [Media RSS Specification](https://www.rssboard.org/media-rss)
- [Content Module](http://web.resource.org/rss/1.0/modules/content/)

### 라이브러리
- [Rome Tools (RSS Parser)](https://rometools.github.io/rome/)
- [Jsoup (HTML Parser)](https://jsoup.org/)

### 연합뉴스
- [연합뉴스 RSS 센터](https://www.yna.co.kr/rss)

---

## ⚠️ 주의사항

1. **저작권**: 이미지 사용 시 언론사 저작권 확인 필수
2. **성능**: OpenGraph 스크래핑은 캐싱 필수
3. **Rate Limiting**: 언론사 서버에 부담 주지 않도록
4. **에러 처리**: 각 단계마다 예외 처리 철저히
5. **로깅**: DEBUG 레벨로 상세 로그 남기기

---

**작성일**: 2025.12.15  
**버전**: 1.0  
**상태**: 전략 수립 완료, 구현 대기


