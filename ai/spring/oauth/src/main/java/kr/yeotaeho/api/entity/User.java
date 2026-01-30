package kr.yeotaeho.api.entity;

import lombok.*;
import org.springframework.data.annotation.CreatedDate;
import org.springframework.data.annotation.LastModifiedDate;
import org.springframework.data.jpa.domain.support.AuditingEntityListener;

import jakarta.persistence.*;
import java.time.LocalDateTime;

/**
 * 사용자 엔티티
 * OAuth 제공자별로 사용자 정보를 저장
 */
@Entity
@Table(name = "users", uniqueConstraints = {
    @UniqueConstraint(columnNames = {"provider", "provider_id"})
})
@EntityListeners(AuditingEntityListener.class)
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class User {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    /**
     * OAuth 제공자 (kakao, google, naver)
     */
    @Column(nullable = false, length = 20)
    private String provider;

    /**
     * OAuth 제공자별 고유 ID
     */
    @Column(name = "provider_id", nullable = false, length = 100)
    private String providerId;

    /**
     * 이메일
     */
    @Column(length = 100)
    private String email;

    /**
     * 이름
     */
    @Column(length = 100)
    private String name;

    /**
     * 닉네임
     */
    @Column(length = 100)
    private String nickname;

    /**
     * 프로필 이미지 URL
     */
    @Column(name = "profile_image", length = 500)
    private String profileImage;

    /**
     * 사용자 권한 (기본값: USER)
     */
    @Column(length = 20)
    @Builder.Default
    private String role = "USER";

    /**
     * 생성 시간
     */
    @CreatedDate
    @Column(name = "created_at", nullable = false, updatable = false)
    private LocalDateTime createdAt;

    /**
     * 수정 시간
     */
    @LastModifiedDate
    @Column(name = "updated_at")
    private LocalDateTime updatedAt;

    /**
     * OAuth 제공자와 제공자 ID로 사용자 찾기
     */
    public static User of(String provider, String providerId, String email, String name, String nickname, String profileImage) {
        return User.builder()
                .provider(provider)
                .providerId(providerId)
                .email(email)
                .name(name)
                .nickname(nickname)
                .profileImage(profileImage)
                .build();
    }
}

