package kr.yeotaeho.api.util;

import org.springframework.http.ResponseCookie;
import org.springframework.stereotype.Component;

/**
 * 쿠키 관련 유틸리티 클래스
 * HttpOnly 쿠키 생성 등 공통 로직 처리
 */
@Component
public class CookieUtil {

    private static final int REFRESH_TOKEN_MAX_AGE = 21 * 24 * 60 * 60; // 21일 (초 단위)

    /**
     * 리프레시 토큰용 HttpOnly 쿠키 생성
     * 
     * @param refreshToken 리프레시 토큰
     * @return ResponseCookie
     */
    public ResponseCookie createRefreshTokenCookie(String refreshToken) {
        return ResponseCookie.from("refreshToken", refreshToken)
                .httpOnly(true)
                .secure(true) // HTTPS 환경에서만
                .path("/")
                .maxAge(REFRESH_TOKEN_MAX_AGE)
                .sameSite("Lax") // CSRF 방지
                .build();
    }

    /**
     * 리프레시 토큰 쿠키 삭제 (로그아웃 시 사용)
     * 
     * @return 만료된 ResponseCookie
     */
    public ResponseCookie createDeleteRefreshTokenCookie() {
        return ResponseCookie.from("refreshToken", "")
                .httpOnly(true)
                .secure(true)
                .path("/")
                .maxAge(0) // 즉시 삭제
                .sameSite("Lax")
                .build();
    }
}

