package kr.yeotaeho.api.controller;

import io.jsonwebtoken.Claims;
import kr.yeotaeho.api.entity.User;
import kr.yeotaeho.api.service.RefreshTokenService;
import kr.yeotaeho.api.service.UserService;
import kr.yeotaeho.api.util.CookieUtil;
import kr.yeotaeho.api.util.JwtTokenUtil;
import kr.yeotaeho.api.util.SignupTokenUtil;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.HashMap;
import java.util.Map;

/**
 * 회원가입 관련 컨트롤러 (토큰 기반)
 */
@Slf4j
@RestController
@RequestMapping("/signup")
@RequiredArgsConstructor
public class SignupController {

    private final UserService userService;
    private final JwtTokenUtil jwtTokenUtil;
    private final RefreshTokenService refreshTokenService;
    private final CookieUtil cookieUtil;
    private final SignupTokenUtil signupTokenUtil;

    /**
     * OAuth 회원가입 처리 (토큰 기반)
     * 
     * @param body 회원가입 토큰 (signupToken)
     * @return 사용자 정보 및 JWT 토큰
     */
    @PostMapping("/oauth")
    public ResponseEntity<Map<String, Object>> oauthSignup(@RequestBody Map<String, String> body) {
        String signupToken = body.get("signupToken");

        log.info("OAuth 회원가입 처리 시작: signupToken={}", signupToken != null ? "있음" : "없음");

        try {
            // 1. 회원가입 토큰 검증
            if (signupToken == null || signupToken.isEmpty()) {
                Map<String, Object> errorResponse = new HashMap<>();
                errorResponse.put("success", false);
                errorResponse.put("message", "회원가입 토큰이 누락되었습니다.");
                return ResponseEntity.status(HttpStatus.BAD_REQUEST).body(errorResponse);
            }

            Claims claims = signupTokenUtil.validateSignupToken(signupToken);
            if (claims == null) {
                Map<String, Object> errorResponse = new HashMap<>();
                errorResponse.put("success", false);
                errorResponse.put("message", "유효하지 않거나 만료된 회원가입 토큰입니다.");
                return ResponseEntity.status(HttpStatus.UNAUTHORIZED).body(errorResponse);
            }

            // 2. OAuth 정보 추출
            Map<String, String> oauthInfo = signupTokenUtil.extractOAuthInfo(claims);
            String provider = oauthInfo.get("provider");
            String providerId = oauthInfo.get("providerId");
            String email = oauthInfo.get("email");
            String name = oauthInfo.get("name");
            String nickname = oauthInfo.get("nickname");
            String profileImage = oauthInfo.get("profileImage");

            log.info("OAuth 정보 추출 완료: provider={}, providerId={}", provider, providerId);

            // 3. 사용자 조회 (이미 존재하는지 확인)
            java.util.Optional<User> existingUser = userService.findUser(provider, providerId);

            User user;
            if (existingUser.isPresent()) {
                // 이미 존재하는 사용자 - 정보 업데이트 후 로그인 처리
                user = existingUser.get();
                user.setEmail(email);
                user.setName(name);
                user.setNickname(nickname);
                user.setProfileImage(profileImage);
                user = userService.save(user);
                log.info("기존 사용자 정보 업데이트 및 로그인: provider={}, providerId={}, userId={}",
                        provider, providerId, user.getId());
            } else {
                // 신규 사용자 생성 시도
                try {
                    User newUser = User.of(provider, providerId, email, name, nickname, profileImage);
                    user = userService.save(newUser);
                    log.info("신규 사용자 생성: provider={}, providerId={}, userId={}",
                            provider, providerId, user.getId());
                } catch (DataIntegrityViolationException e) {
                    // 동시성 문제로 인한 중복 키 에러 발생 시 기존 사용자 조회
                    log.warn("중복 키 제약 위반 발생, 기존 사용자 조회: provider={}, providerId={}",
                            provider, providerId);
                    existingUser = userService.findUser(provider, providerId);
                    if (existingUser.isPresent()) {
                        user = existingUser.get();
                        user.setEmail(email);
                        user.setName(name);
                        user.setNickname(nickname);
                        user.setProfileImage(profileImage);
                        user = userService.save(user);
                        log.info("중복 키 에러 후 기존 사용자 정보 업데이트: provider={}, providerId={}, userId={}",
                                provider, providerId, user.getId());
                    } else {
                        // 예상치 못한 상황
                        throw new RuntimeException("사용자 생성 실패 및 조회 실패", e);
                    }
                }
            }

            // JWT 토큰 생성
            String accessToken = jwtTokenUtil.generateToken(user.getId(), provider, email, name);
            String refreshToken = jwtTokenUtil.generateRefreshToken(user.getId(), provider, email, name);

            // 리프레시 토큰을 Redis에 저장
            refreshTokenService.saveRefreshToken(user.getId(), refreshToken);

            // 응답 생성
            Map<String, Object> response = new HashMap<>();
            response.put("success", true);
            response.put("message", "회원가입 성공");
            response.put("userId", user.getId());
            response.put("email", email);
            response.put("name", name);
            response.put("nickname", nickname);
            response.put("profileImage", profileImage);
            response.put("accessToken", accessToken);
            response.put("tokenType", "Bearer");

            log.info("OAuth 회원가입 성공: userId={}, provider={}, providerId={}", user.getId(), provider, providerId);
            return ResponseEntity.ok()
                    .header(HttpHeaders.SET_COOKIE, cookieUtil.createRefreshTokenCookie(refreshToken).toString())
                    .body(response);

        } catch (Exception e) {
            log.error("OAuth 회원가입 실패: {}", e.getMessage(), e);
            Map<String, Object> errorResponse = new HashMap<>();
            errorResponse.put("success", false);
            errorResponse.put("message", "회원가입 실패: " + e.getMessage());
            errorResponse.put("error", e.getClass().getSimpleName());
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(errorResponse);
        }
    }
}
