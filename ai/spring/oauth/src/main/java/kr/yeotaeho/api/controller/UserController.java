package kr.yeotaeho.api.controller;

import kr.yeotaeho.api.entity.User;
import kr.yeotaeho.api.service.UserService;
import kr.yeotaeho.api.util.JwtTokenUtil;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.nio.file.StandardCopyOption;
import java.util.HashMap;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;

/**
 * 사용자 정보 조회 컨트롤러
 * DB에서 사용자 정보를 조회하는 API 제공
 */
@Slf4j
@RestController
@RequestMapping("/user")
@RequiredArgsConstructor
public class UserController {

    private final UserService userService;
    private final JwtTokenUtil jwtTokenUtil;
    
    @Value("${app.upload.dir:./uploads}")
    private String uploadDir;
    
    @Value("${app.base-url:http://localhost:8080}")
    private String baseUrl;

    /**
     * 현재 로그인한 사용자 정보 조회
     * JWT 토큰에서 userId를 추출하여 DB에서 사용자 정보를 가져옴
     * 
     * @param authorization Authorization 헤더 (Bearer 토큰)
     * @return 사용자 정보
     */
    @GetMapping("/me")
    public ResponseEntity<Map<String, Object>> getCurrentUser(
            @RequestHeader(value = "Authorization", required = false) String authorization
    ) {
        try {
            // Authorization 헤더에서 토큰 추출
            if (authorization == null || !authorization.startsWith("Bearer ")) {
                return ResponseEntity.status(401).body(Map.of("error", "인증 토큰이 필요합니다."));
            }

            String token = authorization.substring(7);
            
            // 토큰 유효성 검증
            if (!jwtTokenUtil.validateToken(token)) {
                return ResponseEntity.status(401).body(Map.of("error", "유효하지 않은 토큰입니다."));
            }

            // 토큰에서 userId 추출
            Long userId = jwtTokenUtil.extractUserId(token);

            if (userId == null) {
                return ResponseEntity.status(401).body(Map.of("error", "사용자 ID를 추출할 수 없습니다."));
            }

            // DB에서 사용자 정보 조회
            Optional<User> userOpt = userService.findById(userId);
            
            if (userOpt.isEmpty()) {
                log.warn("사용자를 찾을 수 없습니다: userId={}", userId);
                return ResponseEntity.status(404).body(Map.of("error", "사용자를 찾을 수 없습니다."));
            }

            User user = userOpt.get();
            
            // 사용자 정보 반환
            Map<String, Object> response = new HashMap<>();
            response.put("id", user.getId());
            response.put("name", user.getName());
            response.put("email", user.getEmail());
            response.put("nickname", user.getNickname());
            response.put("profileImage", user.getProfileImage());
            response.put("provider", user.getProvider());

            log.info("사용자 정보 조회 성공: userId={}, name={}", userId, user.getName());
            return ResponseEntity.ok(response);
        } catch (Exception e) {
            log.error("사용자 정보 조회 중 오류 발생", e);
            return ResponseEntity.status(500).body(Map.of("error", "서버 오류가 발생했습니다."));
        }
    }

    /**
     * 현재 로그인한 사용자 프로필 정보 업데이트
     * 이름과 프로필 이미지 URL을 업데이트
     * 
     * @param authorization Authorization 헤더 (Bearer 토큰)
     * @param requestBody 업데이트할 정보 (name, profileImage)
     * @return 업데이트된 사용자 정보
     */
    @PutMapping("/me")
    public ResponseEntity<Map<String, Object>> updateCurrentUser(
            @RequestHeader(value = "Authorization", required = false) String authorization,
            @RequestBody Map<String, String> requestBody
    ) {
        try {
            // Authorization 헤더에서 토큰 추출
            if (authorization == null || !authorization.startsWith("Bearer ")) {
                return ResponseEntity.status(401).body(Map.of("error", "인증 토큰이 필요합니다."));
            }

            String token = authorization.substring(7);
            
            // 토큰 유효성 검증
            if (!jwtTokenUtil.validateToken(token)) {
                return ResponseEntity.status(401).body(Map.of("error", "유효하지 않은 토큰입니다."));
            }

            // 토큰에서 userId 추출
            Long userId = jwtTokenUtil.extractUserId(token);

            if (userId == null) {
                return ResponseEntity.status(401).body(Map.of("error", "사용자 ID를 추출할 수 없습니다."));
            }

            // DB에서 사용자 정보 조회
            Optional<User> userOpt = userService.findById(userId);
            
            if (userOpt.isEmpty()) {
                log.warn("사용자를 찾을 수 없습니다: userId={}", userId);
                return ResponseEntity.status(404).body(Map.of("error", "사용자를 찾을 수 없습니다."));
            }

            User user = userOpt.get();
            
            // 업데이트할 정보 추출 및 설정
            String name = requestBody.get("name");
            String profileImage = requestBody.get("profileImage");
            
            if (name != null && !name.trim().isEmpty()) {
                user.setName(name.trim());
            }
            
            if (profileImage != null) {
                user.setProfileImage(profileImage.trim().isEmpty() ? null : profileImage.trim());
            }
            
            // 사용자 정보 저장
            User updatedUser = userService.save(user);
            
            // 업데이트된 사용자 정보 반환
            Map<String, Object> response = new HashMap<>();
            response.put("id", updatedUser.getId());
            response.put("name", updatedUser.getName());
            response.put("email", updatedUser.getEmail());
            response.put("nickname", updatedUser.getNickname());
            response.put("profileImage", updatedUser.getProfileImage());
            response.put("provider", updatedUser.getProvider());

            log.info("사용자 정보 업데이트 성공: userId={}, name={}, profileImage={}", 
                    userId, updatedUser.getName(), updatedUser.getProfileImage());
            return ResponseEntity.ok(response);
        } catch (Exception e) {
            log.error("사용자 정보 업데이트 중 오류 발생", e);
            return ResponseEntity.status(500).body(Map.of("error", "서버 오류가 발생했습니다."));
        }
    }

    /**
     * 프로필 이미지 파일 업로드
     * 
     * @param authorization Authorization 헤더 (Bearer 토큰)
     * @param file 업로드할 이미지 파일
     * @return 업로드된 이미지 URL
     */
    @PostMapping("/me/profile-image")
    public ResponseEntity<Map<String, Object>> uploadProfileImage(
            @RequestHeader(value = "Authorization", required = false) String authorization,
            @RequestParam("file") MultipartFile file
    ) {
        try {
            // Authorization 헤더에서 토큰 추출
            if (authorization == null || !authorization.startsWith("Bearer ")) {
                return ResponseEntity.status(401).body(Map.of("error", "인증 토큰이 필요합니다."));
            }

            String token = authorization.substring(7);
            
            // 토큰 유효성 검증
            if (!jwtTokenUtil.validateToken(token)) {
                return ResponseEntity.status(401).body(Map.of("error", "유효하지 않은 토큰입니다."));
            }

            // 토큰에서 userId 추출
            Long userId = jwtTokenUtil.extractUserId(token);

            if (userId == null) {
                return ResponseEntity.status(401).body(Map.of("error", "사용자 ID를 추출할 수 없습니다."));
            }

            // 파일 유효성 검증
            if (file == null || file.isEmpty()) {
                return ResponseEntity.status(400).body(Map.of("error", "파일이 없습니다."));
            }

            // 이미지 파일만 허용
            String contentType = file.getContentType();
            if (contentType == null || !contentType.startsWith("image/")) {
                return ResponseEntity.status(400).body(Map.of("error", "이미지 파일만 업로드 가능합니다."));
            }

            // 파일 크기 제한 (5MB)
            if (file.getSize() > 5 * 1024 * 1024) {
                return ResponseEntity.status(400).body(Map.of("error", "파일 크기는 5MB 이하여야 합니다."));
            }

            // 업로드 디렉토리 생성
            Path uploadPath = Paths.get(uploadDir, "profiles");
            Files.createDirectories(uploadPath);

            // 파일명 생성 (UUID + 원본 확장자)
            String originalFilename = file.getOriginalFilename();
            String extension = originalFilename != null && originalFilename.contains(".") 
                    ? originalFilename.substring(originalFilename.lastIndexOf(".")) 
                    : ".jpg";
            String filename = userId + "_" + UUID.randomUUID().toString() + extension;

            // 파일 저장
            Path filePath = uploadPath.resolve(filename);
            Files.copy(file.getInputStream(), filePath, StandardCopyOption.REPLACE_EXISTING);

            // 파일 URL 생성 (Gateway를 통해 접근 가능한 경로)
            // Gateway에서 /uploads/** → /oauth/uploads/** 로 라우팅됨
            String fileUrl = baseUrl + "/uploads/profiles/" + filename;

            log.info("프로필 이미지 업로드 성공: userId={}, filename={}, url={}", userId, filename, fileUrl);

            Map<String, Object> response = new HashMap<>();
            response.put("url", fileUrl);
            response.put("filename", filename);

            return ResponseEntity.ok(response);
        } catch (IOException e) {
            log.error("프로필 이미지 업로드 중 파일 저장 오류 발생", e);
            return ResponseEntity.status(500).body(Map.of("error", "파일 저장 중 오류가 발생했습니다."));
        } catch (Exception e) {
            log.error("프로필 이미지 업로드 중 오류 발생", e);
            return ResponseEntity.status(500).body(Map.of("error", "서버 오류가 발생했습니다."));
        }
    }
}
