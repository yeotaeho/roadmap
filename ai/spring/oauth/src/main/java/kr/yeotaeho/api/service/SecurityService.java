package kr.yeotaeho.api.service;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicInteger;

/**
 * 보안 서비스
 * 해킹 위험 감지 및 토큰 무효화 처리
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class SecurityService {

    private final RefreshTokenService refreshTokenService;

    // 사용자별 실패 횟수 추적 (메모리 기반, 실제 운영 환경에서는 Redis 사용 권장)
    private final ConcurrentHashMap<Long, AtomicInteger> failedAttempts = new ConcurrentHashMap<>();
    private final ConcurrentHashMap<Long, Long> lastFailedTime = new ConcurrentHashMap<>();

    private static final int MAX_FAILED_ATTEMPTS = 5;
    private static final long LOCKOUT_DURATION = 15 * 60 * 1000; // 15분
    private static final long SUSPICIOUS_ACTIVITY_WINDOW = 5 * 60 * 1000; // 5분

    /**
     * 인증 실패 기록
     */
    public void recordFailedAttempt(Long userId) {
        if (userId == null) return;

        AtomicInteger attempts = failedAttempts.computeIfAbsent(userId, k -> new AtomicInteger(0));
        int currentAttempts = attempts.incrementAndGet();
        lastFailedTime.put(userId, System.currentTimeMillis());

        log.warn("인증 실패 기록: userId={}, 실패 횟수={}", userId, currentAttempts);

        if (currentAttempts >= MAX_FAILED_ATTEMPTS) {
            log.error("최대 실패 횟수 초과 - 모든 토큰 무효화: userId={}", userId);
            refreshTokenService.invalidateAllUserTokens(userId);
            failedAttempts.remove(userId);
        }
    }

    /**
     * 인증 성공 시 실패 횟수 초기화
     */
    public void recordSuccessfulAttempt(Long userId) {
        if (userId != null) {
            failedAttempts.remove(userId);
            lastFailedTime.remove(userId);
        }
    }

    /**
     * 의심스러운 활동 감지
     */
    public boolean detectSuspiciousActivity(Long userId) {
        if (userId == null) return false;

        Long lastFailed = lastFailedTime.get(userId);
        if (lastFailed != null) {
            long timeSinceLastFailed = System.currentTimeMillis() - lastFailed;
            if (timeSinceLastFailed < SUSPICIOUS_ACTIVITY_WINDOW) {
                AtomicInteger attempts = failedAttempts.get(userId);
                if (attempts != null && attempts.get() >= 3) {
                    log.warn("의심스러운 활동 감지: userId={}, 실패 횟수={}", userId, attempts.get());
                    return true;
                }
            }
        }
        return false;
    }

    /**
     * 보안 위협 처리 및 토큰 무효화
     */
    public void handleSecurityThreat(Long userId, String reason) {
        if (userId == null) return;

        log.error("보안 위협 감지 - 모든 토큰 무효화: userId={}, 사유={}", userId, reason);
        refreshTokenService.invalidateAllUserTokens(userId);
        failedAttempts.remove(userId);
        lastFailedTime.remove(userId);
    }

    /**
     * 계정 잠금 확인
     */
    public boolean isAccountLocked(Long userId) {
        if (userId == null) return false;

        AtomicInteger attempts = failedAttempts.get(userId);
        if (attempts != null && attempts.get() >= MAX_FAILED_ATTEMPTS) {
            Long lastFailed = lastFailedTime.get(userId);
            if (lastFailed != null) {
                long timeSinceLastFailed = System.currentTimeMillis() - lastFailed;
                if (timeSinceLastFailed < LOCKOUT_DURATION) {
                    return true;
                }
                // 잠금 시간 경과 시 초기화
                failedAttempts.remove(userId);
                lastFailedTime.remove(userId);
            }
        }
        return false;
    }

    /**
     * 리프레시 토큰 검증 시 보안 체크
     */
    public boolean checkSecurityThreat(String refreshToken, Long userId) {
        if (isAccountLocked(userId)) {
            log.warn("잠금된 계정의 토큰 사용 시도: userId={}", userId);
            return true;
        }

        if (detectSuspiciousActivity(userId)) {
            handleSecurityThreat(userId, "의심스러운 활동 감지");
            return true;
        }

        if (!refreshTokenService.isTokenValid(refreshToken)) {
            log.warn("무효화된 토큰 사용 시도: userId={}", userId);
            recordFailedAttempt(userId);
            return true;
        }

        return false;
    }
}

