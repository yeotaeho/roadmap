package kr.yeotaeho.api.service;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.stereotype.Service;

import java.util.UUID;
import java.util.concurrent.TimeUnit;

/**
 * OAuth State 파라미터 관리 서비스
 * CSRF 공격 방지를 위한 state 생성 및 검증
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class OAuthStateService {

    private final RedisTemplate<String, String> redisTemplate;
    private static final String STATE_KEY_PREFIX = "oauth:state:";
    private static final long STATE_EXPIRATION_MINUTES = 10;

    /**
     * State 생성 및 Redis에 저장
     * 
     * @return 생성된 state 값
     */
    public String generateAndStoreState() {
        String state = UUID.randomUUID().toString();
        String key = STATE_KEY_PREFIX + state;
        
        redisTemplate.opsForValue().set(key, "valid", STATE_EXPIRATION_MINUTES, TimeUnit.MINUTES);
        log.info("OAuth State 생성 및 저장: state={}", state);
        
        return state;
    }

    /**
     * State 검증 (한 번만 사용 가능)
     * 
     * @param state 검증할 state 값
     * @return 검증 성공 여부
     */
    public boolean validateAndRemoveState(String state) {
        if (state == null || state.isEmpty()) {
            log.warn("State 검증 실패: state가 null 또는 빈 문자열");
            return false;
        }
        
        String key = STATE_KEY_PREFIX + state;
        String value = redisTemplate.opsForValue().get(key);
        
        if (value != null) {
            // 검증 성공 후 삭제 (재사용 방지)
            redisTemplate.delete(key);
            log.info("OAuth State 검증 성공: state={}", state);
            return true;
        }
        
        log.warn("OAuth State 검증 실패: state={} (만료되었거나 존재하지 않음)", state);
        return false;
    }
}

