package kr.yeotaeho.api.controller;

import kr.yeotaeho.api.dto.NewsArticle;
import kr.yeotaeho.api.service.NewsService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

@Slf4j
@RestController
@RequestMapping("/news")
@RequiredArgsConstructor
public class NewsController {

    private final NewsService newsService;

    /**
     * 네이버 뉴스 검색
     * 
     * @param query 검색어 (기본값: "삼성")
     * @param display 표시할 결과 수 (기본값: 20)
     * @param start 시작 위치 (기본값: 1)
     * @return 뉴스 기사 목록
     */
    @GetMapping("/search")
    public ResponseEntity<Map<String, Object>> searchNews(
            @RequestParam(required = false, defaultValue = "삼성") String query,
            @RequestParam(required = false) Integer display,
            @RequestParam(required = false) Integer start
    ) {
        log.info("뉴스 검색 요청: query={}, display={}, start={}", query, display, start);

        try {
            List<NewsArticle> articles = newsService.searchNews(query, display, start);

            Map<String, Object> response = new HashMap<>();
            response.put("success", true);
            response.put("articles", articles);
            response.put("count", articles.size());

            return ResponseEntity.ok(response);
        } catch (Exception e) {
            log.error("뉴스 검색 실패: {}", e.getMessage(), e);

            Map<String, Object> errorResponse = new HashMap<>();
            errorResponse.put("success", false);
            errorResponse.put("message", "뉴스 검색 실패: " + e.getMessage());
            errorResponse.put("articles", List.of());

            return ResponseEntity.status(500).body(errorResponse);
        }
    }

    /**
     * 최신 뉴스 조회 (여러 카테고리의 최신 뉴스 통합)
     */
    @GetMapping("/latest")
    public ResponseEntity<Map<String, Object>> getLatestNews(
            @RequestParam(required = false, defaultValue = "100") Integer display
    ) {
        log.info("최신 뉴스 조회 요청: display={}", display);

        try {
            // 각 카테고리마다 가져오기 (각 카테고리당 15개씩)
            int perCategory = 15;
            List<NewsArticle> articlesNews = newsService.searchNews("경제", perCategory, 1);
            List<NewsArticle> articlesEconomy = newsService.searchNews("개발", perCategory, 1);
            List<NewsArticle> articlesIssue = newsService.searchNews("이슈", perCategory, 1);
            List<NewsArticle> articlesPolitics = newsService.searchNews("정치", perCategory, 1);
            List<NewsArticle> articlesSociety = newsService.searchNews("사회", perCategory, 1);
            List<NewsArticle> articlesScience = newsService.searchNews("과학", perCategory, 1);
            List<NewsArticle> articlesTechnology = newsService.searchNews("기술", perCategory, 1);
            List<NewsArticle> articlesEntertainment = newsService.searchNews("엔터테인먼트", perCategory, 1);
            List<NewsArticle> articlesSports = newsService.searchNews("스포츠", perCategory, 1);
            List<NewsArticle> articlesWorld = newsService.searchNews("세계", perCategory, 1);

            // 각 카테고리에서 가져온 기사 수 로깅
            log.info("각 카테고리별 기사 수 - 경제: {}, 개발: {}, 이슈: {}, 정치: {}, 사회: {}, 과학: {}, 기술: {}, 엔터테인먼트: {}, 스포츠: {}, 세계: {}",
                    articlesNews.size(), articlesEconomy.size(), articlesIssue.size(), articlesPolitics.size(),
                    articlesSociety.size(), articlesScience.size(), articlesTechnology.size(),
                    articlesEntertainment.size(), articlesSports.size(), articlesWorld.size());

            // 모든 카테고리의 뉴스를 하나의 리스트로 합치기
            List<NewsArticle> allArticles = new java.util.ArrayList<>();
            allArticles.addAll(articlesNews);
            allArticles.addAll(articlesEconomy);
            allArticles.addAll(articlesIssue);
            allArticles.addAll(articlesPolitics);
            allArticles.addAll(articlesSociety);
            allArticles.addAll(articlesScience);
            allArticles.addAll(articlesTechnology);
            allArticles.addAll(articlesEntertainment);
            allArticles.addAll(articlesSports);
            allArticles.addAll(articlesWorld);

            log.info("병합 전 전체 기사 수: {}개", allArticles.size());

            // 날짜 기준으로 정렬 (최신 기사가 먼저)
            // 날짜 파싱 실패한 기사는 리스트 끝으로 이동
            java.time.format.DateTimeFormatter formatter = java.time.format.DateTimeFormatter.ofPattern("yyyy.MM.dd");
            allArticles.sort((a, b) -> {
                try {
                    java.time.LocalDate dateA = java.time.LocalDate.parse(a.getDate(), formatter);
                    java.time.LocalDate dateB = java.time.LocalDate.parse(b.getDate(), formatter);
                    return dateB.compareTo(dateA); // 내림차순 (최신이 먼저)
                } catch (Exception e) {
                    // 날짜 파싱 실패 시, 둘 다 실패하면 0, 하나만 실패하면 실패한 것을 뒤로
                    boolean aValid = false;
                    boolean bValid = false;
                    try {
                        java.time.LocalDate.parse(a.getDate(), formatter);
                        aValid = true;
                    } catch (Exception ignored) {
                    }
                    try {
                        java.time.LocalDate.parse(b.getDate(), formatter);
                        bValid = true;
                    } catch (Exception ignored) {
                    }
                    
                    if (aValid && !bValid) {
                        return -1; // a는 정상, b는 실패 -> a가 앞으로
                    } else if (!aValid && bValid) {
                        return 1; // b는 정상, a는 실패 -> b가 앞으로
                    } else {
                        log.warn("날짜 정렬 실패: dateA={}, dateB={}", a.getDate(), b.getDate());
                        return 0; // 둘 다 실패
                    }
                }
            });

            log.info("정렬 후 기사 수: {}개", allArticles.size());

            // 중복 제거 (제목 기준) - LinkedHashMap을 사용하여 순서 보장
            List<NewsArticle> uniqueArticles = allArticles.stream()
                    .collect(java.util.stream.Collectors.toMap(
                            NewsArticle::getTitle,
                            article -> article,
                            (existing, replacement) -> existing,
                            java.util.LinkedHashMap::new
                    ))
                    .values()
                    .stream()
                    .collect(java.util.stream.Collectors.toList());

            log.info("중복 제거 후 기사 수: {}개", uniqueArticles.size());

            // 요청한 개수만큼만 반환
            List<NewsArticle> finalArticles = uniqueArticles.stream()
                    .limit(display != null ? display : 100)
                    .collect(java.util.stream.Collectors.toList());

            log.info("최종 반환 기사 수: {}개", finalArticles.size());

            Map<String, Object> response = new HashMap<>();
            response.put("success", true);
            response.put("articles", finalArticles);
            response.put("count", finalArticles.size());

            return ResponseEntity.ok(response);
        } catch (Exception e) {
            log.error("최신 뉴스 조회 실패: {}", e.getMessage(), e);

            Map<String, Object> errorResponse = new HashMap<>();
            errorResponse.put("success", false);
            errorResponse.put("message", "최신 뉴스 조회 실패: " + e.getMessage());
            errorResponse.put("articles", List.of());

            return ResponseEntity.status(500).body(errorResponse);
        }
    }
}
