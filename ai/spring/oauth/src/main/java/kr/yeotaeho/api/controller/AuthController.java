package kr.yeotaeho.api.controller;

import kr.yeotaeho.api.service.RefreshTokenService;
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
 * 인증 관련 컨트롤러
 * 로그아웃 및 토큰 무효화 처리
 */
@Slf4j
@RestController
@RequestMapping("/auth")
@RequiredArgsConstructor
public class AuthController {

    private final RefreshTokenService refreshTokenService;
    private final JwtTokenUtil jwtTokenUtil;
    private final CookieUtil cookieUtil;

    /**
     * 로그아웃
     * 리프레시 토큰을 무효화하고 쿠키 삭제
     * 
     * @param refreshToken HttpOnly 쿠키에서 추출한 리프레시 토큰
     * @param authorization Authorization 헤더에서 액세스 토큰 추출 (선택적)
     * @return 로그아웃 결과
     */
    @PostMapping("/logout")
    public ResponseEntity<Map<String, Object>> logout(
            @CookieValue(value = "refreshToken", required = false) String refreshToken,
            @RequestHeader(value = "Authorization", required = false) String authorization) {
        
        try {
            Long userId = extractUserIdFromTokens(refreshToken, authorization);

            // 사용자 ID가 확인되면 모든 토큰 무효화
            if (userId != null) {
                refreshTokenService.invalidateAllUserTokens(userId);
                log.info("사용자의 모든 리프레시 토큰 무효화 완료: userId={}", userId);
            }

            return ResponseEntity.ok()
                    .header(HttpHeaders.SET_COOKIE, cookieUtil.createDeleteRefreshTokenCookie().toString())
                    .body(Map.of("success", true, "message", "로그아웃 성공"));

        } catch (Exception e) {
            log.error("로그아웃 처리 중 오류 발생: {}", e.getMessage(), e);
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                    .body(Map.of("success", false, "message", "로그아웃 처리 중 오류가 발생했습니다."));
        }
    }

    /**
     * 강제 로그아웃 (관리자 또는 해킹 위험 감지 시)
     * 특정 사용자의 모든 리프레시 토큰을 무효화
     * 
     * @param userId 무효화할 사용자 ID
     * @return 무효화 결과
     */
    @PostMapping("/force-logout/{userId}")
    public ResponseEntity<Map<String, Object>> forceLogout(@PathVariable Long userId) {
        try {
            // 사용자의 모든 토큰 무효화
            refreshTokenService.invalidateAllUserTokens(userId);
            log.warn("강제 로그아웃 실행: userId={}", userId);
            
            return ResponseEntity.ok(Map.of(
                    "success", true,
                    "message", "사용자의 모든 토큰이 무효화되었습니다.",
                    "userId", userId
            ));

        } catch (Exception e) {
            log.error("강제 로그아웃 처리 중 오류 발생: userId={}, error={}", userId, e.getMessage(), e);
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                    .body(Map.of("success", false, "message", "강제 로그아웃 처리 중 오류가 발생했습니다."));
        }
    }

    /**
     * 리프레시 토큰 또는 액세스 토큰에서 사용자 ID 추출
     */
    private Long extractUserIdFromTokens(String refreshToken, String authorization) {
        Long userId = null;

        // 리프레시 토큰에서 사용자 ID 추출 시도
        if (refreshToken != null) {
            try {
                userId = refreshTokenService.validateRefreshToken(refreshToken);
                if (userId != null) {
                    refreshTokenService.deleteRefreshToken(refreshToken);
                    log.info("리프레시 토큰 무효화 완료: userId={}", userId);
                }
            } catch (Exception e) {
                log.warn("리프레시 토큰 처리 중 오류: {}", e.getMessage());
            }
        }

        // 액세스 토큰에서 사용자 ID 추출 (백업)
        if (userId == null && authorization != null && authorization.startsWith("Bearer ")) {
            try {
                String accessToken = authorization.substring(7);
                userId = jwtTokenUtil.extractUserId(accessToken);
                log.info("액세스 토큰에서 사용자 ID 추출: userId={}", userId);
            } catch (Exception e) {
                log.warn("액세스 토큰 처리 중 오류: {}", e.getMessage());
            }
        }

        return userId;
    }
}

