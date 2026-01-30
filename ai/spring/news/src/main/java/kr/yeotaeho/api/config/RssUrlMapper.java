package kr.yeotaeho.api.config;

import lombok.Getter;
import lombok.Setter;
import lombok.extern.slf4j.Slf4j;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.context.annotation.Configuration;

import java.util.*;
import java.util.stream.Collectors;

@Slf4j
@Configuration
@ConfigurationProperties(prefix = "rss")
@Getter
@Setter
public class RssUrlMapper {
    
    private Map<String, List<RssSource>> sources = new HashMap<>();
    
    // 카테고리명 매핑 (한글 -> 영문 키)
    private static final Map<String, String> CATEGORY_MAPPING;
    
    static {
        Map<String, String> map = new HashMap<>();
        map.put("경제", "economy");
        map.put("정치", "politics");
        map.put("사회", "society");
        map.put("문화", "culture");
        map.put("세계", "world");
        map.put("IT/과학", "it-science");
        map.put("IT", "it-science");
        map.put("과학", "it-science");
        map.put("스포츠", "sports");
        map.put("연예", "entertainment");
        map.put("엔터테인먼트", "entertainment");
        map.put("개발", "it-science");
        map.put("이슈", "society");
        CATEGORY_MAPPING = Collections.unmodifiableMap(map);
    }
    
    @Getter
    @Setter
    public static class RssSource {
        private String name;
        private String url;
        private boolean enabled;
    }
    
    /**
     * 카테고리명으로 RSS URL 목록 조회
     */
    public List<String> getRssUrlsByCategory(String category) {
        String categoryKey = CATEGORY_MAPPING.getOrDefault(category, category.toLowerCase());
        List<RssSource> sources = this.sources.get(categoryKey);
        
        if (sources == null || sources.isEmpty()) {
            log.warn("카테고리에 해당하는 RSS URL이 없습니다: category={}", category);
            return List.of();
        }
        
        // enabled가 true인 것만 필터링
        return sources.stream()
                .filter(RssSource::isEnabled)
                .map(RssSource::getUrl)
                .collect(Collectors.toList());
    }
    
    /**
     * 카테고리명인지 확인
     */
    public boolean isCategory(String query) {
        return CATEGORY_MAPPING.containsKey(query) || 
               sources.containsKey(query.toLowerCase());
    }
    
    /**
     * 모든 카테고리 목록 조회
     */
    public List<String> getAllCategories() {
        return new ArrayList<>(CATEGORY_MAPPING.keySet());
    }
}

