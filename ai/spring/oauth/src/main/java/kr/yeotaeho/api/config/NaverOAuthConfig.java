package kr.yeotaeho.api.config;

import lombok.Getter;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Configuration;

/**
 * 네이버 OAuth 설정
 */
@Getter
@Configuration
public class NaverOAuthConfig {

    @Value("${naver.client-id}")
    private String clientId;

    @Value("${naver.client-secret}")
    private String clientSecret;

    @Value("${naver.redirect-uri}")
    private String redirectUri;

    // 네이버 OAuth URLs
    public static final String NAVER_AUTH_URL = "https://nid.naver.com/oauth2.0/authorize";
    public static final String NAVER_TOKEN_URL = "https://nid.naver.com/oauth2.0/token";
    public static final String NAVER_USER_INFO_URL = "https://openapi.naver.com/v1/nid/me";
}

