package kr.yeotaeho.api.config;

import lombok.Getter;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.client.RestTemplate;

/**
 * 카카오 OAuth 설정
 */
@Getter
@Configuration
public class KakaoOAuthConfig {

    @Value("${kakao.client-id}")
    private String clientId;

    @Value("${kakao.client-secret:}")
    private String clientSecret;

    @Value("${kakao.redirect-uri}")
    private String redirectUri;

    @Value("${kakao.admin-key:}")
    private String adminKey;

    // 카카오 OAuth URLs
    public static final String KAKAO_AUTH_URL = "https://kauth.kakao.com/oauth/authorize";
    public static final String KAKAO_TOKEN_URL = "https://kauth.kakao.com/oauth/token";
    public static final String KAKAO_USER_INFO_URL = "https://kapi.kakao.com/v2/user/me";

    @Bean
    public RestTemplate restTemplate() {
        return new RestTemplate();
    }
}

