package kr.yeotaeho.api.repository;

import kr.yeotaeho.api.entity.User;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

/**
 * 사용자 Repository
 */
@Repository
public interface UserRepository extends JpaRepository<User, Long> {

    /**
     * OAuth 제공자와 제공자 ID로 사용자 찾기
     */
    List<User> findByProviderAndProviderId(String provider, String providerId);

    /**
     * 이메일로 사용자 찾기
     */
    Optional<User> findByEmail(String email);
}

