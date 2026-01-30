package kr.yeotaeho.api.service;

import kr.yeotaeho.api.config.GoogleOAuthConfig;
import kr.yeotaeho.api.dto.GoogleTokenResponse;
import kr.yeotaeho.api.dto.GoogleUserInfo;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Service;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.util.UriComponentsBuilder;

import java.util.HashMap;
import java.util.Map;

/**
 * 구글 OAuth 서비스 (RestTemplate 사용)
 * State 파라미터 및 PKCE 지원
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class GoogleOAuthService {

    private final GoogleOAuthConfig googleConfig;
    private final RestTemplate restTemplate;
    private final OAuthStateService stateService;
    private final PKCEService pkceService;

    /**
     * 구글 로그인 URL 생성 (State 및 PKCE 지원)
     *
     * @return Map<String, String> {authUrl, state}
     */
    public Map<String, String> getAuthorizationUrl() {
        // 1. State 생성 및 저장
        String state = stateService.generateAndStoreState();

        // 2. PKCE Code Verifier & Challenge 생성
        String codeVerifier = pkceService.generateCodeVerifier();
        String codeChallenge = pkceService.generateCodeChallenge(codeVerifier);

        // 3. Code Verifier를 Redis에 저장
        pkceService.storeCodeVerifier(state, codeVerifier);

        // 4. Authorization URL 생성
        String authUrl = UriComponentsBuilder
                .fromUriString(GoogleOAuthConfig.GOOGLE_AUTH_URL)
                .queryParam("client_id", googleConfig.getClientId())
                .queryParam("redirect_uri", googleConfig.getRedirectUri())
                .queryParam("response_type", "code")
                .queryParam("scope", "email profile")
                .queryParam("access_type", "offline")
                .queryParam("prompt", "consent")
                .queryParam("state", state)
                .queryParam("code_challenge", codeChallenge)
                .queryParam("code_challenge_method", "S256")
                .build()
                .toUriString();

        log.info("구글 인증 URL 생성 완료: state={}", state);

        Map<String, String> result = new HashMap<>();
        result.put("authUrl", authUrl);
        result.put("state", state);
        return result;
    }

    /**
     * 인가 코드로 액세스 토큰 발급 (PKCE 지원)
     *
     * @param code  인가 코드
     * @param state OAuth state (PKCE code_verifier 조회용)
     * @return 구글 토큰 응답
     */
    public GoogleTokenResponse getAccessToken(String code, String state) {
        log.info("구글 액세스 토큰 요청: code={}, state={}", code, state);

        // HTTP 헤더 설정
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_FORM_URLENCODED);

        // HTTP 바디 파라미터 설정
        MultiValueMap<String, String> params = new LinkedMultiValueMap<>();
        params.add("grant_type", "authorization_code");
        params.add("client_id", googleConfig.getClientId());
        params.add("client_secret", googleConfig.getClientSecret());
        params.add("redirect_uri", googleConfig.getRedirectUri());
        params.add("code", code);

        // PKCE Code Verifier 추가 (Redis에서 조회)
        if (state != null) {
            String codeVerifier = pkceService.getAndRemoveCodeVerifier(state);
            if (codeVerifier != null) {
                params.add("code_verifier", codeVerifier);
                log.info("PKCE Code Verifier 추가됨");
            } else {
                log.warn("Code Verifier를 찾을 수 없음: state={}", state);
            }
        }

        // HTTP 요청 엔티티 생성
        HttpEntity<MultiValueMap<String, String>> request = new HttpEntity<>(params, headers);

        try {
            // 구글 토큰 API 호출
            ResponseEntity<GoogleTokenResponse> response = restTemplate.postForEntity(
                    GoogleOAuthConfig.GOOGLE_TOKEN_URL,
                    request,
                    GoogleTokenResponse.class);

            log.info("구글 액세스 토큰 발급 성공");
            return response.getBody();

        } catch (Exception e) {
            log.error("구글 액세스 토큰 발급 실패: {}", e.getMessage());
            throw new RuntimeException("구글 토큰 발급 실패: " + e.getMessage());
        }
    }

    /**
     * 액세스 토큰으로 사용자 정보 조회
     *
     * @param accessToken 액세스 토큰
     * @return 구글 사용자 정보
     */
    public GoogleUserInfo getUserInfo(String accessToken) {
        log.info("구글 사용자 정보 조회");

        // HTTP 헤더 설정
        HttpHeaders headers = new HttpHeaders();
        headers.set("Authorization", "Bearer " + accessToken);

        // HTTP 요청 엔티티 생성
        HttpEntity<Void> request = new HttpEntity<>(headers);

        try {
            // 구글 사용자 정보 API 호출
            ResponseEntity<GoogleUserInfo> response = restTemplate.exchange(
                    GoogleOAuthConfig.GOOGLE_USER_INFO_URL,
                    HttpMethod.GET,
                    request,
                    GoogleUserInfo.class);

            GoogleUserInfo userInfo = response.getBody();
            log.info("구글 사용자 정보 조회 성공: id={}", userInfo.getId());
            return userInfo;

        } catch (Exception e) {
            log.error("구글 사용자 정보 조회 실패: {}", e.getMessage());
            throw new RuntimeException("구글 사용자 정보 조회 실패: " + e.getMessage());
        }
    }

    /**
     * 전체 OAuth 플로우 실행 (State 검증 및 PKCE 지원)
     *
     * @param code  인가 코드
     * @param state OAuth state
     * @return 구글 사용자 정보
     */
    public GoogleUserInfo processOAuth(String code, String state) {
        // 1. State 검증
        if (!stateService.validateAndRemoveState(state)) {
            throw new RuntimeException("State 검증 실패: CSRF 공격 가능성");
        }

        // 2. 토큰 발급 (PKCE code_verifier 포함)
        GoogleTokenResponse tokenResponse = getAccessToken(code, state);

        // 3. 사용자 정보 조회
        return getUserInfo(tokenResponse.getAccessToken());
    }
}
