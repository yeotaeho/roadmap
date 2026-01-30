package kr.yeotaeho.api.util;

import io.jsonwebtoken.Claims;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import javax.crypto.SecretKey;
import java.nio.charset.StandardCharsets;
import java.util.Date;
import java.util.HashMap;
import java.util.Map;

/**
 * 회원가입 임시 토큰 유틸리티
 * OAuth 정보를 안전하게 전달하기 위한 JWT 토큰 생성/검증
 * JJWT 0.12.x API 사용
 */
@Slf4j
@Component
public class SignupTokenUtil {

    private final String secret;
    private static final long SIGNUP_TOKEN_EXPIRATION = 10 * 60 * 1000; // 10분

    public SignupTokenUtil(@Value("${jwt.secret}") String secret) {
        this.secret = secret;
    }
    
    /**
     * Secret Key 생성
     */
    private SecretKey getSigningKey() {
        byte[] keyBytes = secret.getBytes(StandardCharsets.UTF_8);
        
        // HS256 알고리즘을 위한 최소 키 크기: 256비트 = 32바이트
        int minKeySize = 32;
        
        // 키가 너무 짧으면 반복하여 확장
        if (keyBytes.length < minKeySize) {
            byte[] expandedKey = new byte[minKeySize];
            for (int i = 0; i < minKeySize; i++) {
                expandedKey[i] = keyBytes[i % keyBytes.length];
            }
            keyBytes = expandedKey;
        }
        
        return Keys.hmacShaKeyFor(keyBytes);
    }

    /**
     * 회원가입 토큰 생성
     * 
     * @param provider OAuth 제공자 (kakao, google, naver)
     * @param providerId OAuth 제공자별 고유 ID
     * @param email 이메일
     * @param name 이름
     * @param nickname 닉네임
     * @param profileImage 프로필 이미지 URL
     * @return 회원가입 토큰
     */
    public String generateSignupToken(String provider, String providerId, String email, 
                                      String name, String nickname, String profileImage) {
        Map<String, Object> claims = new HashMap<>();
        claims.put("provider", provider);
        claims.put("providerId", providerId);
        claims.put("email", email);
        claims.put("name", name);
        claims.put("nickname", nickname);
        claims.put("profileImage", profileImage);
        claims.put("tokenType", "signup");

        Date now = new Date();
        Date expiryDate = new Date(now.getTime() + SIGNUP_TOKEN_EXPIRATION);

        String token = Jwts.builder()
                .claims(claims)
                .issuedAt(now)
                .expiration(expiryDate)
                .signWith(getSigningKey())
                .compact();

        log.info("회원가입 토큰 생성: provider={}, providerId={}", provider, providerId);
        return token;
    }

    /**
     * 회원가입 토큰 검증 및 Claims 추출
     * 
     * @param token 회원가입 토큰
     * @return Claims (검증 실패 시 null)
     */
    public Claims validateSignupToken(String token) {
        try {
            Claims claims = Jwts.parser()
                    .verifyWith(getSigningKey())
                    .build()
                    .parseSignedClaims(token)
                    .getPayload();

            // tokenType 검증
            String tokenType = claims.get("tokenType", String.class);
            if (!"signup".equals(tokenType)) {
                log.warn("회원가입 토큰 검증 실패: 잘못된 tokenType={}", tokenType);
                return null;
            }

            log.info("회원가입 토큰 검증 성공: provider={}, providerId={}", 
                    claims.get("provider"), claims.get("providerId"));
            return claims;

        } catch (Exception e) {
            log.error("회원가입 토큰 검증 실패: {}", e.getMessage());
            return null;
        }
    }

    /**
     * Claims에서 OAuth 정보 추출
     * 
     * @param claims JWT Claims
     * @return OAuth 정보 Map
     */
    public Map<String, String> extractOAuthInfo(Claims claims) {
        Map<String, String> oauthInfo = new HashMap<>();
        oauthInfo.put("provider", claims.get("provider", String.class));
        oauthInfo.put("providerId", claims.get("providerId", String.class));
        oauthInfo.put("email", claims.get("email", String.class));
        oauthInfo.put("name", claims.get("name", String.class));
        oauthInfo.put("nickname", claims.get("nickname", String.class));
        oauthInfo.put("profileImage", claims.get("profileImage", String.class));
        return oauthInfo;
    }
}

