package kr.yeotaeho.api.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * 카카오 사용자 정보 DTO
 */
@Data
@NoArgsConstructor
public class KakaoUserInfo {

    @JsonProperty("id")
    private Long id;

    @JsonProperty("connected_at")
    private String connectedAt;

    @JsonProperty("kakao_account")
    private KakaoAccount kakaoAccount;

    @JsonProperty("properties")
    private Properties properties;

    @Data
    @NoArgsConstructor
    public static class KakaoAccount {
        @JsonProperty("profile_needs_agreement")
        private Boolean profileNeedsAgreement;

        @JsonProperty("profile")
        private Profile profile;

        @JsonProperty("email_needs_agreement")
        private Boolean emailNeedsAgreement;

        @JsonProperty("is_email_valid")
        private Boolean isEmailValid;

        @JsonProperty("is_email_verified")
        private Boolean isEmailVerified;

        @JsonProperty("email")
        private String email;
    }

    @Data
    @NoArgsConstructor
    public static class Profile {
        @JsonProperty("nickname")
        private String nickname;

        @JsonProperty("thumbnail_image_url")
        private String thumbnailImageUrl;

        @JsonProperty("profile_image_url")
        private String profileImageUrl;

        @JsonProperty("is_default_image")
        private Boolean isDefaultImage;
    }

    @Data
    @NoArgsConstructor
    public static class Properties {
        @JsonProperty("nickname")
        private String nickname;

        @JsonProperty("profile_image")
        private String profileImage;

        @JsonProperty("thumbnail_image")
        private String thumbnailImage;
    }
}
