package kr.yeotaeho.api.service;

import kr.yeotaeho.api.entity.User;
import kr.yeotaeho.api.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.Optional;

/**
 * 사용자 관리 서비스
 * OAuth 제공자별 사용자 정보를 통합 관리
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class UserService {

    private final UserRepository userRepository;

    /**
     * OAuth 제공자 정보로 사용자 찾기 또는 생성
     * 
     * @param provider     OAuth 제공자 (kakao, google, naver)
     * @param providerId   OAuth 제공자별 고유 ID
     * @param email        이메일
     * @param name         이름
     * @param nickname     닉네임
     * @param profileImage 프로필 이미지 URL
     * @return 사용자 엔티티
     */
    @Transactional
    public User findOrCreateUser(String provider, String providerId, String email,
            String name, String nickname, String profileImage) {
        // 기존 사용자 조회 (중복 가능성 대비)
        List<User> existingUsers = userRepository.findByProviderAndProviderId(provider, providerId);

        if (!existingUsers.isEmpty()) {
            // 중복 레코드가 있는 경우 첫 번째 레코드 사용
            User user = existingUsers.get(0);

            // 중복 레코드가 2개 이상인 경우 나머지 삭제
            if (existingUsers.size() > 1) {
                log.warn("중복 사용자 레코드 발견: provider={}, providerId={}, count={}",
                        provider, providerId, existingUsers.size());

                // 첫 번째 레코드를 제외한 나머지 삭제
                for (int i = 1; i < existingUsers.size(); i++) {
                    userRepository.delete(existingUsers.get(i));
                    log.info("중복 사용자 레코드 삭제: userId={}", existingUsers.get(i).getId());
                }
            }

            // 기존 사용자 정보 업데이트
            user.setEmail(email);
            user.setName(name);
            user.setNickname(nickname);
            user.setProfileImage(profileImage);

            log.info("기존 사용자 정보 업데이트: provider={}, providerId={}, userId={}",
                    provider, providerId, user.getId());

            return userRepository.save(user);
        } else {
            // 신규 사용자 생성
            User newUser = User.of(provider, providerId, email, name, nickname, profileImage);
            User savedUser = userRepository.save(newUser);

            log.info("신규 사용자 생성: provider={}, providerId={}, userId={}",
                    provider, providerId, savedUser.getId());

            return savedUser;
        }
    }

    /**
     * OAuth 제공자 정보로 사용자 찾기 (생성하지 않음)
     * 
     * @param provider   OAuth 제공자 (kakao, google, naver)
     * @param providerId OAuth 제공자별 고유 ID
     * @return 사용자 엔티티 (없으면 Optional.empty())
     */
    public Optional<User> findUser(String provider, String providerId) {
        List<User> users = userRepository.findByProviderAndProviderId(provider, providerId);
        return users.isEmpty() ? Optional.empty() : Optional.of(users.get(0));
    }

    /**
     * 사용자 정보 업데이트 및 저장
     */
    @Transactional
    public User save(User user) {
        return userRepository.save(user);
    }

    /**
     * 사용자 ID로 사용자 찾기
     */
    public Optional<User> findById(Long userId) {
        return userRepository.findById(userId);
    }
}
