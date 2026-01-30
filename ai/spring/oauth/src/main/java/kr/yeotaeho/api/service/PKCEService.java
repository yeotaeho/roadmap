package kr.yeotaeho.api.service;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.stereotype.Service;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.security.SecureRandom;
import java.util.Base64;
import java.util.concurrent.TimeUnit;

/**
 * PKCE (Proof Key for Code Exchange) 서비스
 * SPA 및 모바일 앱에서 Authorization Code 가로채기 방지
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class PKCEService {

    private final RedisTemplate<String, String> redisTemplate;
    private static final String VERIFIER_KEY_PREFIX = "oauth:pkce:";
    private static final long VERIFIER_EXPIRATION_MINUTES = 10;
    private static final int CODE_VERIFIER_LENGTH = 128;

    /**
     * Code Verifier 생성 (43~128자의 랜덤 문자열)
     * 
     * @return Code Verifier
     */
    public String generateCodeVerifier() {
        SecureRandom secureRandom = new SecureRandom();
        byte[] codeVerifier = new byte[CODE_VERIFIER_LENGTH];
        secureRandom.nextBytes(codeVerifier);
        
        // Base64 URL 인코딩 (패딩 제거)
        String verifier = Base64.getUrlEncoder()
                .withoutPadding()
                .encodeToString(codeVerifier)
                .substring(0, CODE_VERIFIER_LENGTH);
        
        log.debug("Code Verifier 생성 완료: length={}", verifier.length());
        return verifier;
    }

    /**
     * Code Challenge 생성 (SHA-256 해시)
     * 
     * @param codeVerifier Code Verifier
     * @return Code Challenge
     */
    public String generateCodeChallenge(String codeVerifier) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] hash = digest.digest(codeVerifier.getBytes(StandardCharsets.US_ASCII));
            
            // Base64 URL 인코딩 (패딩 제거)
            String challenge = Base64.getUrlEncoder()
                    .withoutPadding()
                    .encodeToString(hash);
            
            log.debug("Code Challenge 생성 완료");
            return challenge;
            
        } catch (NoSuchAlgorithmException e) {
            log.error("SHA-256 알고리즘을 찾을 수 없음", e);
            throw new RuntimeException("Code Challenge 생성 실패", e);
        }
    }

    /**
     * Code Verifier를 Redis에 저장
     * 
     * @param state OAuth state (key로 사용)
     * @param codeVerifier 저장할 Code Verifier
     */
    public void storeCodeVerifier(String state, String codeVerifier) {
        String key = VERIFIER_KEY_PREFIX + state;
        redisTemplate.opsForValue().set(key, codeVerifier, VERIFIER_EXPIRATION_MINUTES, TimeUnit.MINUTES);
        log.info("Code Verifier 저장: state={}", state);
    }

    /**
     * Code Verifier를 Redis에서 조회 및 삭제
     * 
     * @param state OAuth state (key로 사용)
     * @return Code Verifier (없으면 null)
     */
    public String getAndRemoveCodeVerifier(String state) {
        if (state == null || state.isEmpty()) {
            log.warn("Code Verifier 조회 실패: state가 null 또는 빈 문자열");
            return null;
        }
        
        String key = VERIFIER_KEY_PREFIX + state;
        String codeVerifier = redisTemplate.opsForValue().get(key);
        
        if (codeVerifier != null) {
            // 조회 후 삭제 (재사용 방지)
            redisTemplate.delete(key);
            log.info("Code Verifier 조회 및 삭제 성공: state={}", state);
            return codeVerifier;
        }
        
        log.warn("Code Verifier 조회 실패: state={} (만료되었거나 존재하지 않음)", state);
        return null;
    }
}

