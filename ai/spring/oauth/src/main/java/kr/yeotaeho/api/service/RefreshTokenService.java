package kr.yeotaeho.api.service;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.stereotype.Service;

import java.util.Set;
import java.util.concurrent.TimeUnit;

/**
 * 리프레시 토큰 관리 서비스
 * Redis에 리프레시 토큰을 저장하고 관리
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class RefreshTokenService {

    private final RedisTemplate<String, String> redisTemplate;

    @Value("${redis.key.refresh-token-prefix:refreshToken:}")
    private String refreshTokenPrefix;

    @Value("${redis.key.user-tokens-prefix:user:tokens:}")
    private String userTokensPrefix;

    @Value("${jwt.refresh-expiration:1814400000}") // 기본 21일
    private Long refreshExpiration;

    /**
     * 리프레시 토큰 저장
     * 
     * @param userId 사용자 ID
     * @param refreshToken 리프레시 토큰
     */
    public void saveRefreshToken(Long userId, String refreshToken) {
        try {
            // 토큰을 키로 사용하여 사용자 ID 저장
            String tokenKey = refreshTokenPrefix + refreshToken;
            redisTemplate.opsForValue().set(
                tokenKey, 
                userId.toString(), 
                refreshExpiration, 
                TimeUnit.MILLISECONDS
            );

            // 사용자별 토큰 목록에도 추가 (모든 토큰 무효화 시 사용)
            String userTokensKey = userTokensPrefix + userId;
            redisTemplate.opsForSet().add(userTokensKey, refreshToken);
            redisTemplate.expire(userTokensKey, refreshExpiration, TimeUnit.MILLISECONDS);

            log.debug("리프레시 토큰 저장 완료: userId={}", userId);
        } catch (Exception e) {
            log.error("리프레시 토큰 저장 실패: userId={}, error={}", userId, e.getMessage(), e);
            throw new RuntimeException("리프레시 토큰 저장 실패", e);
        }
    }

    /**
     * 리프레시 토큰 검증 (Redis에 존재하는지 확인)
     * 
     * @param refreshToken 리프레시 토큰
     * @return 토큰이 유효하면 사용자 ID, 없으면 null
     */
    public Long validateRefreshToken(String refreshToken) {
        try {
            String tokenKey = refreshTokenPrefix + refreshToken;
            String userId = redisTemplate.opsForValue().get(tokenKey);
            
            if (userId == null) {
                log.warn("리프레시 토큰이 Redis에 존재하지 않음: token={}", refreshToken.substring(0, Math.min(20, refreshToken.length())));
                return null;
            }

            return Long.parseLong(userId);
        } catch (Exception e) {
            log.error("리프레시 토큰 검증 실패: error={}", e.getMessage(), e);
            return null;
        }
    }

    /**
     * 리프레시 토큰 삭제 (단일 토큰 무효화)
     * 
     * @param refreshToken 리프레시 토큰
     */
    public void deleteRefreshToken(String refreshToken) {
        try {
            String tokenKey = refreshTokenPrefix + refreshToken;
            String userId = redisTemplate.opsForValue().get(tokenKey);
            
            if (userId != null) {
                // 토큰 삭제
                redisTemplate.delete(tokenKey);
                
                // 사용자별 토큰 목록에서도 제거
                String userTokensKey = userTokensPrefix + userId;
                redisTemplate.opsForSet().remove(userTokensKey, refreshToken);
                
                log.info("리프레시 토큰 삭제 완료: userId={}", userId);
            }
        } catch (Exception e) {
            log.error("리프레시 토큰 삭제 실패: error={}", e.getMessage(), e);
        }
    }

    /**
     * 사용자의 모든 리프레시 토큰 무효화 (로그아웃 또는 해킹 위험 시)
     * 
     * @param userId 사용자 ID
     */
    public void invalidateAllUserTokens(Long userId) {
        try {
            String userTokensKey = userTokensPrefix + userId;
            Set<String> tokens = redisTemplate.opsForSet().members(userTokensKey);
            
            if (tokens != null && !tokens.isEmpty()) {
                // 모든 토큰 삭제
                for (String token : tokens) {
                    String tokenKey = refreshTokenPrefix + token;
                    redisTemplate.delete(tokenKey);
                }
                
                // 사용자별 토큰 목록도 삭제
                redisTemplate.delete(userTokensKey);
                
                log.info("사용자의 모든 리프레시 토큰 무효화 완료: userId={}, count={}", userId, tokens.size());
            }
        } catch (Exception e) {
            log.error("사용자 토큰 무효화 실패: userId={}, error={}", userId, e.getMessage(), e);
            throw new RuntimeException("토큰 무효화 실패", e);
        }
    }

    /**
     * 리프레시 토큰 교체 (토큰 로테이션)
     * 이전 토큰을 삭제하고 새 토큰을 저장
     * 
     * @param userId 사용자 ID
     * @param oldRefreshToken 이전 리프레시 토큰
     * @param newRefreshToken 새 리프레시 토큰
     */
    public void rotateRefreshToken(Long userId, String oldRefreshToken, String newRefreshToken) {
        try {
            // 이전 토큰 삭제
            deleteRefreshToken(oldRefreshToken);
            
            // 새 토큰 저장
            saveRefreshToken(userId, newRefreshToken);
            
            log.info("리프레시 토큰 로테이션 완료: userId={}", userId);
        } catch (Exception e) {
            log.error("리프레시 토큰 로테이션 실패: userId={}, error={}", userId, e.getMessage(), e);
            throw new RuntimeException("토큰 로테이션 실패", e);
        }
    }

    /**
     * 특정 토큰이 유효한지 확인
     */
    public boolean isTokenValid(String refreshToken) {
        return validateRefreshToken(refreshToken) != null;
    }
}
