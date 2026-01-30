package kr.yeotaeho.api.controller;

import io.jsonwebtoken.Claims;
import kr.yeotaeho.api.service.RefreshTokenService;
import kr.yeotaeho.api.service.SecurityService;
import kr.yeotaeho.api.service.UserService;
import kr.yeotaeho.api.util.CookieUtil;
import kr.yeotaeho.api.util.JwtTokenUtil;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

/**
 * 리프레시 토큰 컨트롤러
 * 액세스 토큰 만료 시 리프레시 토큰으로 새 액세스 토큰을 발급받는 엔드포인트
 */
@Slf4j
@RestController
@RequestMapping("/refresh")
@RequiredArgsConstructor
public class RefreshTokenController {

    private final JwtTokenUtil jwtTokenUtil;
    private final RefreshTokenService refreshTokenService;
    private final SecurityService securityService;
    private final CookieUtil cookieUtil;
    private final UserService userService;

    /**
     * 리프레시 토큰으로 새 액세스 토큰 발급
     * 
     * @param refreshToken HttpOnly 쿠키에서 추출한 리프레시 토큰
     * @return 새 액세스 토큰
     */
    @PostMapping
    public ResponseEntity<Map<String, Object>> refreshToken(
            @CookieValue(value = "refreshToken", required = false) String refreshToken) {
        
        if (refreshToken == null) {
            log.warn("리프레시 토큰이 없습니다.");
            return createUnauthorizedResponse("리프레시 토큰이 없습니다.");
        }

        try {
            // 1. JWT 토큰 검증
            Claims claims = jwtTokenUtil.extractAllClaims(refreshToken);
            
            // 토큰 타입 확인
            Object tokenType = claims.get("type");
            if (tokenType == null || !"refresh".equals(tokenType.toString())) {
                log.warn("유효하지 않은 리프레시 토큰 타입: {}", tokenType);
                throw new IllegalArgumentException("유효하지 않은 리프레시 토큰입니다.");
            }

            // 토큰 만료 확인
            if (jwtTokenUtil.isTokenExpired(refreshToken)) {
                log.warn("리프레시 토큰이 만료되었습니다.");
                refreshTokenService.deleteRefreshToken(refreshToken);
                return createUnauthorizedResponse("리프레시 토큰이 만료되었습니다.");
            }

            Long userId = jwtTokenUtil.extractUserId(refreshToken);
            String email = jwtTokenUtil.extractEmail(refreshToken);
            String provider = jwtTokenUtil.extractProvider(refreshToken);

            // 2. 보안 체크 (해킹 위험 감지)
            if (securityService.checkSecurityThreat(refreshToken, userId)) {
                log.error("보안 위협 감지 - 토큰 갱신 거부: userId={}", userId);
                return createUnauthorizedResponse("보안 위협이 감지되어 토큰이 무효화되었습니다.");
            }

            // 3. Redis에서 토큰 검증
            Long redisUserId = refreshTokenService.validateRefreshToken(refreshToken);
            if (redisUserId == null) {
                log.warn("리프레시 토큰이 Redis에 존재하지 않음 (무효화됨): userId={}", userId);
                securityService.recordFailedAttempt(userId);
                return createUnauthorizedResponse("리프레시 토큰이 무효화되었습니다.");
            }

            // 사용자 ID 일치 확인
            if (!redisUserId.equals(userId)) {
                log.error("리프레시 토큰의 사용자 ID 불일치: tokenUserId={}, redisUserId={}", userId, redisUserId);
                securityService.recordFailedAttempt(userId);
                return createUnauthorizedResponse("리프레시 토큰이 유효하지 않습니다.");
            }

            // 4. 인증 성공 기록
            securityService.recordSuccessfulAttempt(userId);

            // 5. 사용자 정보 조회 (name 추출)
            String name = userService.findById(userId)
                    .map(user -> user.getName())
                    .orElse(null);

            // 6. 새 토큰 생성 및 로테이션
            String newAccessToken = jwtTokenUtil.generateToken(userId, provider, email, name);
            String newRefreshToken = jwtTokenUtil.generateRefreshToken(userId, provider, email, name);
            refreshTokenService.rotateRefreshToken(userId, refreshToken, newRefreshToken);

            log.info("토큰 갱신 성공: userId={}", userId);
            return ResponseEntity.ok()
                    .header(HttpHeaders.SET_COOKIE, cookieUtil.createRefreshTokenCookie(newRefreshToken).toString())
                    .body(Map.of(
                            "success", true,
                            "accessToken", newAccessToken,
                            "tokenType", "Bearer"
                    ));

        } catch (IllegalArgumentException e) {
            log.error("리프레시 토큰 검증 실패: {}", e.getMessage());
            return createUnauthorizedResponse(e.getMessage());
        } catch (Exception e) {
            log.error("리프레시 토큰 처리 중 오류 발생: {}", e.getMessage(), e);
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                    .body(Map.of("success", false, "message", "토큰 갱신 중 오류가 발생했습니다."));
        }
    }

    private ResponseEntity<Map<String, Object>> createUnauthorizedResponse(String message) {
        return ResponseEntity.status(HttpStatus.UNAUTHORIZED)
                .body(Map.of("success", false, "message", message));
    }
}

