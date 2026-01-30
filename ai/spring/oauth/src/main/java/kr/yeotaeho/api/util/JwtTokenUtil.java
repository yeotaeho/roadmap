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
import java.util.function.Function;

/**
 * JWT 토큰 생성 및 검증 유틸리티 클래스
 * JJWT 0.12.x API 사용
 */
@Slf4j
@Component
public class JwtTokenUtil {

    @Value("${jwt.secret}")
    private String secret;

    @Value("${jwt.expiration}")
    private Long expiration;

    @Value("${jwt.refresh-expiration:1814400000}") // 기본 21일
    private Long refreshExpiration;

    /**
     * Secret Key 생성
     * HS512 알고리즘을 사용하려면 최소 512비트(64바이트)의 키가 필요합니다.
     */
    private SecretKey getSigningKey() {
        byte[] keyBytes = secret.getBytes(StandardCharsets.UTF_8);
        
        // HS512 알고리즘을 위한 최소 키 크기: 512비트 = 64바이트
        int minKeySize = 64;
        
        // 키가 너무 짧으면 반복하여 확장
        if (keyBytes.length < minKeySize) {
            byte[] expandedKey = new byte[minKeySize];
            for (int i = 0; i < minKeySize; i++) {
                expandedKey[i] = keyBytes[i % keyBytes.length];
            }
            keyBytes = expandedKey;
            log.warn("JWT secret key was too short ({} bytes). Expanded to {} bytes for HS512.", 
                    secret.getBytes(StandardCharsets.UTF_8).length, minKeySize);
        }
        
        return Keys.hmacShaKeyFor(keyBytes);
    }

    /**
     * JWT 토큰 생성
     * 
     * @param userId 사용자 ID
     * @param provider OAuth 제공자 (kakao, google, naver)
     * @param email 사용자 이메일
     * @param name 사용자 이름
     * @return JWT 토큰 문자열
     */
    public String generateToken(Long userId, String provider, String email, String name) {
        Map<String, Object> claims = new HashMap<>();
        claims.put("userId", userId);
        claims.put("provider", provider);
        claims.put("email", email);
        if (name != null) {
            claims.put("name", name);
        }
        
        return createToken(claims, userId.toString());
    }

    /**
     * JWT 토큰 생성 (내부 메서드)
     * JJWT 0.12.x API 사용
     */
    private String createToken(Map<String, Object> claims, String subject) {
        Date now = new Date();
        Date expiryDate = new Date(now.getTime() + expiration);

        return Jwts.builder()
                .claims(claims)
                .subject(subject)
                .issuedAt(now)
                .expiration(expiryDate)
                .signWith(getSigningKey())
                .compact();
    }

    /**
     * 토큰에서 클레임 추출
     * JJWT 0.12.x API 사용
     */
    public Claims extractAllClaims(String token) {
        try {
            return Jwts.parser()
                    .verifyWith(getSigningKey())
                    .build()
                    .parseSignedClaims(token)
                    .getPayload();
        } catch (Exception e) {
            log.error("토큰 파싱 실패: {}", e.getMessage());
            throw e;
        }
    }

    /**
     * 토큰에서 특정 클레임 추출
     */
    public <T> T extractClaim(String token, Function<Claims, T> claimsResolver) {
        final Claims claims = extractAllClaims(token);
        return claimsResolver.apply(claims);
    }

    /**
     * 토큰에서 사용자 ID 추출
     */
    public Long extractUserId(String token) {
        Claims claims = extractAllClaims(token);
        Object userIdObj = claims.get("userId");
        if (userIdObj instanceof Integer) {
            return ((Integer) userIdObj).longValue();
        } else if (userIdObj instanceof Long) {
            return (Long) userIdObj;
        }
        return Long.parseLong(userIdObj.toString());
    }

    /**
     * 토큰에서 OAuth 제공자 추출
     */
    public String extractProvider(String token) {
        return extractClaim(token, claims -> claims.get("provider", String.class));
    }

    /**
     * 토큰에서 이메일 추출
     */
    public String extractEmail(String token) {
        return extractClaim(token, claims -> claims.get("email", String.class));
    }

    /**
     * 토큰에서 만료 시간 추출
     */
    public Date extractExpiration(String token) {
        return extractClaim(token, Claims::getExpiration);
    }

    /**
     * 토큰에서 주제(subject) 추출
     */
    public String extractSubject(String token) {
        return extractClaim(token, Claims::getSubject);
    }

    /**
     * 토큰 만료 여부 확인
     */
    public Boolean isTokenExpired(String token) {
        try {
            return extractExpiration(token).before(new Date());
        } catch (Exception e) {
            return true;
        }
    }

    /**
     * 토큰 유효성 검증
     */
    public Boolean validateToken(String token) {
        try {
            return !isTokenExpired(token);
        } catch (Exception e) {
            log.error("토큰 검증 실패: {}", e.getMessage());
            return false;
        }
    }

    /**
     * 리프레시 토큰 생성
     * JJWT 0.12.x API 사용
     * 
     * @param userId 사용자 ID
     * @param provider OAuth 제공자 (kakao, google, naver)
     * @param email 사용자 이메일
     * @param name 사용자 이름
     * @return 리프레시 토큰 문자열
     */
    public String generateRefreshToken(Long userId, String provider, String email, String name) {
        Map<String, Object> claims = new HashMap<>();
        claims.put("type", "refresh");
        claims.put("userId", userId);
        claims.put("provider", provider);
        claims.put("email", email);
        if (name != null) {
            claims.put("name", name);
        }
        
        Date now = new Date();
        Date expiryDate = new Date(now.getTime() + refreshExpiration);
        
        return Jwts.builder()
                .claims(claims)
                .subject(userId.toString())
                .issuedAt(now)
                .expiration(expiryDate)
                .signWith(getSigningKey())
                .compact();
    }
}
