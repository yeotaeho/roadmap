package kr.yeotaeho.api.service;

import kr.yeotaeho.api.config.RssUrlMapper;
import kr.yeotaeho.api.dto.NaverNewsResponse;
import kr.yeotaeho.api.dto.NewsArticle;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.util.UriComponentsBuilder;

import java.time.LocalDateTime;
import java.time.ZonedDateTime;
import java.time.format.DateTimeFormatter;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ExecutorService;
import java.util.stream.Collectors;

@Slf4j
@Service
public class NewsService {

    private final RestTemplate restTemplate;
    private final RssService rssService;
    private final RssUrlMapper rssUrlMapper;
    private final ExecutorService rssExecutor;
    
    public NewsService(
            RestTemplate restTemplate,
            RssService rssService,
            RssUrlMapper rssUrlMapper,
            @Qualifier("rssExecutor") ExecutorService rssExecutor
    ) {
        this.restTemplate = restTemplate;
        this.rssService = rssService;
        this.rssUrlMapper = rssUrlMapper;
        this.rssExecutor = rssExecutor;
    }

    @Value("${naver.client-id}")
    private String naverClientId;

    @Value("${naver.client-secret}")
    private String naverClientSecret;

    private static final String NAVER_NEWS_API_URL = "https://openapi.naver.com/v1/search/news.json";

    /**
     * 뉴스 검색 (RSS 우선, 필요시 네이버 API 폴백)
     * 
     * @param query 검색어 또는 카테고리명
     * @param display 표시할 결과 수 (기본값: 20)
     * @param start 시작 위치 (기본값: 1)
     * @return 뉴스 기사 목록
     */
    public List<NewsArticle> searchNews(String query, Integer display, Integer start) {
        // 1. query가 정의된 카테고리명인지 확인
        if (rssUrlMapper.isCategory(query)) {
            log.info("카테고리로 인식: query={}, RSS 피드 사용", query);
            return searchNewsFromRss(query, display, start);
        } else {
            log.info("검색어로 인식: query={}, 네이버 API 사용", query);
            // 자유 검색어 → 네이버 API 호출 (제한적)
            return searchNewsFromNaverApi(query, display, start);
        }
    }
    
    /**
     * RSS 피드를 통한 뉴스 검색 (비동기 병렬 처리)
     */
    private List<NewsArticle> searchNewsFromRss(String category, Integer display, Integer start) {
        try {
            // 1. 카테고리별 RSS URL 목록 조회
            List<String> rssUrls = rssUrlMapper.getRssUrlsByCategory(category);
            
            if (rssUrls.isEmpty()) {
                log.warn("카테고리에 해당하는 RSS URL이 없습니다: category={}", category);
                return List.of();
            }
            
            log.info("RSS 피드 수집 시작: category={}, RSS URL 개수={}", category, rssUrls.size());
            
            // 2. 비동기 병렬 처리로 여러 RSS 피드 수집
            List<NewsArticle> allArticles = fetchMultipleRssFeeds(rssUrls);
            
            log.info("RSS 피드 수집 완료: category={}, 총 기사 수={}", category, allArticles.size());
            
            // 3. 중복 제거 (제목 기준) - LinkedHashMap으로 순서 보장
            List<NewsArticle> uniqueArticles = allArticles.stream()
                    .collect(Collectors.toMap(
                            NewsArticle::getTitle,
                            article -> article,
                            (existing, replacement) -> existing,
                            LinkedHashMap::new
                    ))
                    .values()
                    .stream()
                    .collect(Collectors.toList());
            
            log.info("중복 제거 후 기사 수: category={}, 기사 수={}", category, uniqueArticles.size());
            
            // 4. 날짜순 정렬 (이미 RssService에서 정렬되어 있을 수 있지만 재정렬)
            uniqueArticles.sort((a, b) -> {
                try {
                    DateTimeFormatter formatter = DateTimeFormatter.ofPattern("yyyy.MM.dd");
                    java.time.LocalDate dateA = java.time.LocalDate.parse(a.getDate(), formatter);
                    java.time.LocalDate dateB = java.time.LocalDate.parse(b.getDate(), formatter);
                    return dateB.compareTo(dateA); // 내림차순 (최신이 먼저)
                } catch (Exception e) {
                    log.warn("날짜 정렬 실패: dateA={}, dateB={}", a.getDate(), b.getDate());
                    return 0;
                }
            });
            
            // 5. 페이징 처리
            return applyPaging(uniqueArticles, display, start);
            
        } catch (Exception e) {
            log.error("RSS 뉴스 검색 실패: category={}, error={}", category, e.getMessage(), e);
            return List.of();
        }
    }
    
    /**
     * 여러 RSS 피드를 비동기 병렬로 수집
     */
    private List<NewsArticle> fetchMultipleRssFeeds(List<String> rssUrls) {
        // 1. 각 RSS URL에 대해 CompletableFuture 생성
        List<CompletableFuture<List<NewsArticle>>> futures = rssUrls.stream()
                .map(url -> CompletableFuture.supplyAsync(() -> {
                    try {
                        return rssService.fetchNewsFromRss(url);
                    } catch (Exception e) {
                        log.error("RSS 피드 수집 실패: URL={}, error={}", url, e.getMessage());
                        return List.<NewsArticle>of(); // 빈 리스트 반환
                    }
                }, rssExecutor))
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
    
    /**
     * 메모리 페이징 처리
     */
    private List<NewsArticle> applyPaging(
            List<NewsArticle> articles, 
            Integer display, 
            Integer start
    ) {
        // 기본값 설정
        if (display == null || display <= 0) {
            display = 20;
        }
        if (start == null || start < 1) {
            start = 1;
        }
        
        // start 파라미터로 offset 적용
        int offset = start - 1;
        int fromIndex = Math.min(offset, articles.size());
        
        // display 파라미터로 limit 적용
        int toIndex = Math.min(fromIndex + display, articles.size());
        
        // 서브리스트 반환
        if (fromIndex >= toIndex) {
            return List.of();
        }
        
        return articles.subList(fromIndex, toIndex);
    }
    
    /**
     * 네이버 API를 통한 뉴스 검색 (폴백)
     */
    private List<NewsArticle> searchNewsFromNaverApi(String query, Integer display, Integer start) {
        try {
            // 기본값 설정
            if (display == null || display <= 0) {
                display = 20;
            }
            if (start == null || start < 1) {
                start = 1;
            }

            // URL 생성
            UriComponentsBuilder builder = UriComponentsBuilder.fromHttpUrl(NAVER_NEWS_API_URL)
                    .queryParam("query", query)
                    .queryParam("display", display)
                    .queryParam("start", start)
                    .queryParam("sort", "date"); // 날짜순 정렬

            // 헤더 설정
            HttpHeaders headers = new HttpHeaders();
            headers.set("X-Naver-Client-Id", naverClientId);
            headers.set("X-Naver-Client-Secret", naverClientSecret);
            HttpEntity<String> entity = new HttpEntity<>(headers);

            // API 호출
            ResponseEntity<NaverNewsResponse> response = restTemplate.exchange(
                    builder.toUriString(),
                    HttpMethod.GET,
                    entity,
                    NaverNewsResponse.class
            );

            NaverNewsResponse newsResponse = response.getBody();
            if (newsResponse == null || newsResponse.getItems() == null) {
                log.warn("네이버 뉴스 API 응답이 비어있습니다.");
                return List.of();
            }

            log.info("네이버 뉴스 API 응답: 총 {}개 기사", newsResponse.getItems().size());

            // 원본 pubDate를 사용하여 날짜 기준 내림차순 정렬 (최신 기사 우선)
            DateTimeFormatter rfc822Formatter = DateTimeFormatter.RFC_1123_DATE_TIME;
            //ZonedDateTime now = ZonedDateTime.now();
            //ZonedDateTime sevenDaysAgo = now.minusDays(7); // 최근 7일 이내 기사만

            // 날짜 기준 내림차순 정렬 및 최근 7일 이내 기사만 필터링
            List<NaverNewsResponse.NaverNewsItem> sortedItems = newsResponse.getItems().stream()
                    //.filter(item -> {
                    //    try {
                    //        ZonedDateTime pubDate = ZonedDateTime.parse(item.getPubDate(), rfc822Formatter);
                    //        // 최근 7일 이내 기사만 포함
                    //        return !pubDate.isBefore(sevenDaysAgo);
                    //    } catch (Exception e) {
                    //        log.warn("날짜 필터링 실패: pubDate={}, error={}", item.getPubDate(), e.getMessage());
                    //        return false; // 날짜 파싱 실패 시 제외
                    //    }
                    //})
                    .sorted((a, b) -> {
                        // 원본 pubDate를 사용하여 정렬 (최신 기사가 먼저)
                        try {
                            ZonedDateTime dateA = ZonedDateTime.parse(a.getPubDate(), rfc822Formatter);
                            ZonedDateTime dateB = ZonedDateTime.parse(b.getPubDate(), rfc822Formatter);
                            return dateB.compareTo(dateA); // 내림차순 (최신이 먼저)
                        } catch (Exception e) {
                            log.warn("날짜 정렬 실패: pubDate={}, error={}", a.getPubDate(), e.getMessage());
                            return 0;
                        }
                    })
                    .collect(Collectors.toList());

            log.info("정렬 및 필터링 후 기사 수: {}개 (최근 7일 이내)", sortedItems.size());

            // DTO 변환
            List<NewsArticle> articles = sortedItems.stream()
                    .map(item -> convertToNewsArticle(item, query))
                    .collect(Collectors.toList());

            log.info("최종 변환된 기사 수: {}개", articles.size());
            return articles;

        } catch (Exception e) {
            log.error("네이버 뉴스 API 호출 실패: {}", e.getMessage(), e);
            return List.of();
        }
    }

    /**
     * 네이버 뉴스 아이템을 NewsArticle로 변환
     */
    private NewsArticle convertToNewsArticle(NaverNewsResponse.NaverNewsItem item, String query) {
        // HTML 태그 제거
        String cleanTitle = item.getTitle()
                .replaceAll("<[^>]*>", "")
                .replaceAll("&quot;", "\"")
                .replaceAll("&amp;", "&")
                .replaceAll("&lt;", "<")
                .replaceAll("&gt;", ">");

        String cleanDescription = item.getDescription()
                .replaceAll("<[^>]*>", "")
                .replaceAll("&quot;", "\"")
                .replaceAll("&amp;", "&")
                .replaceAll("&lt;", "<")
                .replaceAll("&gt;", ">");

        // 날짜 포맷팅 (네이버 API는 RFC 822 형식: "Wed, 13 Dec 2025 10:30:00 +0900")
        String formattedDate = formatDate(item.getPubDate());

        // 이미지 추출 (설명에서 이미지 URL이 있는 경우)
        String imageUrl = extractImageUrl(item.getDescription());

        return NewsArticle.builder()
                .type(query != null ? query : "뉴스")
                .title(cleanTitle)
                .date(formattedDate)
                .image(imageUrl)
                .link(item.getLink())
                .description(cleanDescription)
                .build();
    }

    /**
     * 날짜 포맷팅 (RFC 822 -> YYYY.MM.DD)
     */
    private String formatDate(String pubDate) {
        try {
            // RFC 822 형식 파싱 (예: "Wed, 13 Dec 2025 10:30:00 +0900")
            DateTimeFormatter rfc822Formatter = DateTimeFormatter.RFC_1123_DATE_TIME;
            ZonedDateTime zonedDateTime = ZonedDateTime.parse(pubDate, rfc822Formatter);
            return zonedDateTime.format(DateTimeFormatter.ofPattern("yyyy.MM.dd"));
        } catch (Exception e) {
            log.warn("날짜 파싱 실패: {}, 현재 날짜 반환", pubDate);
            // 날짜 파싱 실패 시 현재 날짜 반환
            return LocalDateTime.now().format(DateTimeFormatter.ofPattern("yyyy.MM.dd"));
        }
    }

    /**
     * 설명에서 이미지 URL 추출
     */
    private String extractImageUrl(String description) {
        // 간단한 이미지 URL 추출 (실제로는 더 복잡한 로직이 필요할 수 있음)
        if (description == null) {
            return "https://placehold.co/400x250/000000/FFFFFF?text=NEWS";
        }
        
        // img 태그에서 src 추출 시도
        String imgPattern = "<img[^>]+src\\s*=\\s*['\"]([^'\"]+)['\"]";
        java.util.regex.Pattern pattern = java.util.regex.Pattern.compile(imgPattern);
        java.util.regex.Matcher matcher = pattern.matcher(description);
        
        if (matcher.find()) {
            return matcher.group(1);
        }
        
        // 이미지 URL이 없으면 기본 이미지
        return "https://placehold.co/400x250/000000/FFFFFF?text=NEWS";
    }
}
