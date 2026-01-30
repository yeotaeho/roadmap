package kr.yeotaeho.api.naver;

import kr.yeotaeho.api.dto.NaverUserInfo;
import kr.yeotaeho.api.entity.User;
import kr.yeotaeho.api.service.NaverOAuthService;
import kr.yeotaeho.api.service.RefreshTokenService;
import kr.yeotaeho.api.service.UserService;
import kr.yeotaeho.api.util.CookieUtil;
import kr.yeotaeho.api.util.JwtTokenUtil;
import kr.yeotaeho.api.util.SignupTokenUtil;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.HashMap;
import java.util.Map;

/**
 * 네이버 로그인 관련 컨트롤러
 * 
 * 주의: CORS는 Gateway에서 처리하므로 여기서는 설정하지 않습니다.
 * Gateway의 application.yaml에서 globalcors 설정을 확인하세요.
 */
@Slf4j
@RestController
@RequestMapping("/naver")
@RequiredArgsConstructor
public class NaverController {

    private final NaverOAuthService naverOAuthService;
    private final UserService userService;
    private final JwtTokenUtil jwtTokenUtil;
    private final RefreshTokenService refreshTokenService;
    private final CookieUtil cookieUtil;
    private final SignupTokenUtil signupTokenUtil;

    /**
     * 네이버 로그인 URL 요청 (State 검증 지원)
     * 
     * @return 네이버 인증 URL 및 state
     */
    @GetMapping("/login")
    public ResponseEntity<Map<String, String>> getNaverLoginUrl() {
        log.info("네이버 로그인 URL 요청");

        Map<String, String> authData = naverOAuthService.getAuthorizationUrl();
        String authUrl = authData.get("authUrl");
        String state = authData.get("state");

        Map<String, String> response = new HashMap<>();
        response.put("authUrl", authUrl);
        response.put("state", state);
        response.put("message", "네이버 로그인 페이지로 이동하세요");

        return ResponseEntity.ok(response);
    }

    /**
     * 네이버 로그인 콜백 처리 (프론트에서 code와 state를 POST로 전송)
     * 
     * @param body code와 state를 포함한 요청 바디
     * @return 사용자 정보 및 JWT 토큰
     */
    @PostMapping("/callback")
    public ResponseEntity<Map<String, Object>> naverCallback(@RequestBody Map<String, String> body) {
        String code = body.get("code");
        String state = body.get("state");
        log.info("네이버 로그인 콜백 처리 시작: code={}, state={}", code, state);

        try {
            // State 검증 없이 진행하면 예외 발생
            if (state == null || state.isEmpty()) {
                Map<String, Object> errorResponse = new HashMap<>();
                errorResponse.put("success", false);
                errorResponse.put("message", "State 파라미터가 누락되었습니다.");
                return ResponseEntity.status(HttpStatus.BAD_REQUEST).body(errorResponse);
            }

            // OAuth 플로우 실행 (State 검증 + 토큰 발급 + 사용자 정보 조회)
            NaverUserInfo userInfo = naverOAuthService.processOAuth(code, state);

            // 사용자 정보 추출
            String providerId = null;
            String email = null;
            String name = null;
            String nickname = null;
            String profileImage = null;

            if (userInfo.getResponse() != null) {
                providerId = userInfo.getResponse().getId();
                email = userInfo.getResponse().getEmail();
                nickname = userInfo.getResponse().getNickname();
                name = userInfo.getResponse().getName();
                profileImage = userInfo.getResponse().getProfileImage();
            }

            // 1. 사용자 조회 (생성하지 않음)
            java.util.Optional<User> existingUser = userService.findUser("naver", providerId);

            Map<String, Object> response = new HashMap<>();

            if (existingUser.isEmpty()) {
                // 신규 사용자 - 회원가입 필요 (토큰 방식)
                String signupToken = signupTokenUtil.generateSignupToken(
                        "naver", providerId, email, name, nickname, profileImage);

                response.put("success", false);
                response.put("isNewUser", true);
                response.put("message", "회원가입이 필요합니다.");
                response.put("signupToken", signupToken);

                log.info("신규 사용자 감지 (회원가입 토큰 발급): provider=naver, providerId={}", providerId);
                return ResponseEntity.status(HttpStatus.OK).body(response);
            }

            // 기존 사용자 - 로그인 처리
            User user = existingUser.get();

            // 사용자 정보 업데이트
            user.setEmail(email);
            user.setName(name);
            user.setNickname(nickname);
            user.setProfileImage(profileImage);
            userService.save(user);

            // 2. JWT 토큰 생성
            String accessToken = jwtTokenUtil.generateToken(user.getId(), "naver", email, name);
            String refreshToken = jwtTokenUtil.generateRefreshToken(user.getId(), "naver", email, name);

            // 3. 리프레시 토큰을 Redis에 저장
            refreshTokenService.saveRefreshToken(user.getId(), refreshToken);

            // 4. 응답 생성
            response.put("success", true);
            response.put("isNewUser", false);
            response.put("message", "네이버 로그인 성공");
            response.put("userId", user.getId());
            response.put("naverId", providerId);
            response.put("email", email);
            response.put("nickname", nickname);
            response.put("name", name);
            response.put("profileImage", profileImage);
            response.put("accessToken", accessToken);
            response.put("tokenType", "Bearer");

            log.info("네이버 로그인 성공: userId={}, naverId={}", user.getId(), providerId);
            return ResponseEntity.ok()
                    .header(HttpHeaders.SET_COOKIE, cookieUtil.createRefreshTokenCookie(refreshToken).toString())
                    .body(response);

        } catch (Exception e) {
            log.error("네이버 로그인 실패: {}", e.getMessage(), e);
            Map<String, Object> errorResponse = new HashMap<>();
            errorResponse.put("success", false);
            errorResponse.put("isNewUser", false);
            errorResponse.put("message", "네이버 로그인 실패: " + e.getMessage());
            errorResponse.put("error", e.getClass().getSimpleName());
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(errorResponse);
        }
    }
}
