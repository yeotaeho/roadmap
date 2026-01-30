# RSS 이미지 추출 전략 (Jsoup 활용)

## 📌 개요

RSS 뉴스 피드에서 이미지를 추출하는 3단계 폴백(Fallback) 전략을 구현하여, 다양한 RSS 피드 형식에서 안정적으로 이미지를 가져올 수 있도록 합니다.

---

## 🎯 3단계 추출 전략

### 1단계: Enclosure/Media 태그 확인
**우선순위: 최상**

RSS 표준 확장 태그에서 이미지를 직접 추출합니다.

#### 지원 태그
- `<enclosure>` (RSS 2.0 표준)
- `<media:content>` (Media RSS 확장)
- `<media:thumbnail>` (Media RSS 확장)

#### 구현 코드
```java
List<SyndEnclosure> enclosures = entry.getEnclosures();
if (!enclosures.isEmpty()) {
    SyndEnclosure enclosure = enclosures.get(0);
    if (enclosure.getType() != null && enclosure.getType().startsWith("image/")) {
        return enclosure.getUrl();
    }
}
```

#### RSS 피드 예시
```xml
<item>
    <title>뉴스 제목</title>
    <enclosure url="https://example.com/image.jpg" type="image/jpeg" length="24816"/>
</item>
```

또는

```xml
<item>
    <title>뉴스 제목</title>
    <media:content url="https://example.com/image.jpg" type="image/jpeg"/>
</item>
```

---

### 2단계: HTML Description 파싱 (Jsoup)
**우선순위: 중간**

Enclosure가 없는 경우, `<description>` 또는 `<content:encoded>` 태그 내부의 HTML을 Jsoup으로 파싱하여 `<img>` 태그를 찾습니다.

#### 구현 코드
```java
if (entry.getDescription() != null) {
    String html = entry.getDescription().getValue();
    if (html != null && !html.isEmpty()) {
        try {
            Document doc = Jsoup.parse(html);
            Element img = doc.selectFirst("img");
            if (img != null) {
                String src = img.attr("src");
                if (src != null && !src.isEmpty()) {
                    return src;
                }
            }
        } catch (Exception e) {
            log.debug("이미지 추출 실패: entry={}", entry.getTitle());
        }
    }
}
```

#### RSS 피드 예시
```xml
<item>
    <title>뉴스 제목</title>
    <description>
        <![CDATA[
            <p>뉴스 내용입니다.</p>
            <img src="https://example.com/news-image.jpg" alt="뉴스 이미지"/>
            <p>추가 내용...</p>
        ]]>
    </description>
</item>
```

#### Jsoup 선택자 활용
- `doc.selectFirst("img")`: 첫 번째 이미지 선택
- `img.attr("src")`: src 속성값 추출
- `img.attr("data-src")`: lazy loading 이미지 대응 (필요 시 확장 가능)

---

### 3단계: 기본 이미지 반환
**우선순위: 최하 (Fallback)**

모든 추출 시도가 실패한 경우, 플레이스홀더 이미지를 반환하여 사용자 경험을 유지합니다.

#### 구현 코드
```java
return "https://placehold.co/400x250/000000/FFFFFF?text=RSS";
```

#### 플레이스홀더 이미지 특징
- 크기: 400x250 (16:10 비율)
- 배경색: 검정 (#000000)
- 텍스트: 흰색 "RSS" (#FFFFFF)
- 서비스: placehold.co (무료 플레이스홀더 이미지 서비스)

#### 대안 플레이스홀더 옵션
```java
// 옵션 1: 로컬 기본 이미지
return "/images/default-news.png";

// 옵션 2: 카테고리별 기본 이미지
return "https://placehold.co/400x250/000000/FFFFFF?text=" + category;

// 옵션 3: Lorem Picsum (랜덤 이미지)
return "https://picsum.photos/400/250";
```

---

## 📊 전체 흐름도

```
┌─────────────────────────────────────┐
│     RSS Entry 수신                  │
└─────────────────────────────────────┘
                ↓
┌─────────────────────────────────────┐
│ ▶ 1단계: Enclosure/Media 확인       │
│   - <enclosure type="image/*">      │
│   - <media:content>                 │
│   - <media:thumbnail>               │
└─────────────────────────────────────┘
                ↓ 실패
┌─────────────────────────────────────┐
│ ▶ 2단계: Description HTML 파싱      │
│   - Jsoup.parse(html)               │
│   - doc.selectFirst("img")          │
│   - img.attr("src")                 │
└─────────────────────────────────────┘
                ↓ 실패
┌─────────────────────────────────────┐
│ ▶ 3단계: 기본 이미지 반환            │
│   - Placeholder 이미지 URL          │
│   - 사용자 경험 유지                │
└─────────────────────────────────────┘
                ↓
┌─────────────────────────────────────┐
│     이미지 URL 반환                 │
└─────────────────────────────────────┘
```

---

## 🔧 사용 라이브러리

### Rome (ROME Fetcher)
- **용도**: RSS/Atom 피드 파싱
- **주요 클래스**:
  - `SyndFeed`: 피드 전체 정보
  - `SyndEntry`: 개별 기사 정보
  - `SyndEnclosure`: 첨부파일 정보 (이미지, 오디오 등)

### Jsoup
- **용도**: HTML 파싱 및 DOM 조작
- **주요 메서드**:
  - `Jsoup.parse(html)`: HTML 문자열 파싱
  - `doc.selectFirst(selector)`: CSS 선택자로 요소 선택
  - `element.attr(attributeName)`: 속성값 추출

---

## 📝 전체 구현 코드

### RssService.java - extractImageUrl 메서드

```java
/**
 * 이미지 URL 추출 (Jsoup 활용)
 * 
 * 3단계 폴백 전략:
 * 1. Enclosure/Media 태그 확인
 * 2. Description HTML 파싱
 * 3. 기본 이미지 반환
 */
private String extractImageUrl(SyndEntry entry) {
    // ============================================
    // 1단계: Enclosure/Media 태그 확인
    // ============================================
    List<SyndEnclosure> enclosures = entry.getEnclosures();
    if (!enclosures.isEmpty()) {
        SyndEnclosure enclosure = enclosures.get(0);
        if (enclosure.getType() != null && enclosure.getType().startsWith("image/")) {
            log.debug("이미지 추출 성공 (Enclosure): {}", enclosure.getUrl());
            return enclosure.getUrl();
        }
    }
    
    // ============================================
    // 2단계: Description HTML 파싱 (Jsoup)
    // ============================================
    if (entry.getDescription() != null) {
        String html = entry.getDescription().getValue();
        if (html != null && !html.isEmpty()) {
            try {
                Document doc = Jsoup.parse(html);
                Element img = doc.selectFirst("img");
                if (img != null) {
                    String src = img.attr("src");
                    if (src != null && !src.isEmpty()) {
                        log.debug("이미지 추출 성공 (Description HTML): {}", src);
                        return src;
                    }
                }
            } catch (Exception e) {
                log.debug("이미지 추출 실패: entry={}", entry.getTitle());
            }
        }
    }
    
    // ============================================
    // 3단계: 기본 이미지 반환
    // ============================================
    log.debug("기본 이미지 반환: entry={}", entry.getTitle());
    return "https://placehold.co/400x250/000000/FFFFFF?text=RSS";
}
```

---

## 🚀 확장 가능성

### 1. Content:Encoded 태그 지원
일부 RSS 피드는 `<content:encoded>` 태그에 더 풍부한 HTML을 제공합니다.

```java
// Description 체크 후 추가
if (entry.getContents() != null && !entry.getContents().isEmpty()) {
    SyndContent content = entry.getContents().get(0);
    String html = content.getValue();
    // Jsoup 파싱 로직 동일
}
```

### 2. Lazy Loading 이미지 대응
최근 웹사이트는 `data-src` 속성을 사용합니다.

```java
String src = img.attr("src");
if (src == null || src.isEmpty()) {
    src = img.attr("data-src"); // Lazy loading 대응
}
```

### 3. Open Graph 메타 태그 추출
링크를 방문하여 Open Graph 이미지 추출 (성능 고려 필요)

```java
Document doc = Jsoup.connect(entry.getLink()).get();
Element ogImage = doc.selectFirst("meta[property=og:image]");
if (ogImage != null) {
    return ogImage.attr("content");
}
```

### 4. 이미지 유효성 검증
추출한 이미지 URL이 실제로 접근 가능한지 검증

```java
private boolean isValidImageUrl(String imageUrl) {
    try {
        HttpURLConnection connection = (HttpURLConnection) new URL(imageUrl).openConnection();
        connection.setRequestMethod("HEAD");
        connection.setConnectTimeout(3000);
        int responseCode = connection.getResponseCode();
        return responseCode == 200;
    } catch (Exception e) {
        return false;
    }
}
```

---

## 📊 테스트 케이스

### 1. Enclosure 태그가 있는 RSS
```xml
<item>
    <title>테스트 뉴스</title>
    <enclosure url="https://example.com/image.jpg" type="image/jpeg"/>
</item>
```
**예상 결과**: `https://example.com/image.jpg`

### 2. Description에 img 태그가 있는 RSS
```xml
<item>
    <title>테스트 뉴스</title>
    <description><![CDATA[<img src="https://example.com/news.jpg"/>뉴스 내용]]></description>
</item>
```
**예상 결과**: `https://example.com/news.jpg`

### 3. 이미지가 없는 RSS
```xml
<item>
    <title>테스트 뉴스</title>
    <description>단순 텍스트 뉴스 내용</description>
</item>
```
**예상 결과**: `https://placehold.co/400x250/000000/FFFFFF?text=RSS`

---

## 📚 참고 자료

- [RSS 2.0 Specification](https://www.rssboard.org/rss-specification)
- [Media RSS Specification](https://www.rssboard.org/media-rss)
- [Jsoup Documentation](https://jsoup.org/)
- [Rome Documentation](https://rometools.github.io/rome/)

---

## 📌 주의사항

1. **성능 고려**: 
   - Jsoup 파싱은 CPU를 사용하므로, 대량의 RSS 항목 처리 시 비동기 처리 권장
   - 현재 `@Async` 적용되어 있음 (`RssService.fetchNewsFromRss`)

2. **예외 처리**:
   - 모든 단계에서 null 체크 및 예외 처리 필수
   - 로그 레벨 적절히 조정 (debug/warn/error)

3. **보안**:
   - 이미지 URL 검증 (악성 URL 차단)
   - HTTPS 우선 사용 권장

4. **캐싱**:
   - Redis 캐싱 활용 중 (현재 구현됨)
   - 이미지 URL도 캐싱하여 반복 요청 최소화

---

## ✅ 구현 상태

- [x] 1단계: Enclosure/Media 태그 확인
- [x] 2단계: HTML Description 파싱 (Jsoup)
- [x] 3단계: 기본 이미지 반환
- [x] 로깅 추가
- [x] 예외 처리
- [ ] Content:Encoded 지원 (확장 가능)
- [ ] Lazy Loading 이미지 대응 (확장 가능)
- [ ] 이미지 URL 유효성 검증 (확장 가능)

---

**작성일**: 2025.12.15  
**파일 위치**: `service/news/src/main/java/kr/yeotaeho/api/service/RssService.java`  
**메서드**: `extractImageUrl(SyndEntry entry)`



