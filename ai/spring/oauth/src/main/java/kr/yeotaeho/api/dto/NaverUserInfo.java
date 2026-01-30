package kr.yeotaeho.api.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * 네이버 사용자 정보 DTO
 */
@Data
@NoArgsConstructor
public class NaverUserInfo {

    @JsonProperty("resultcode")
    private String resultCode;

    @JsonProperty("message")
    private String message;

    @JsonProperty("response")
    private Response response;

    @Data
    @NoArgsConstructor
    public static class Response {
        @JsonProperty("id")
        private String id;

        @JsonProperty("nickname")
        private String nickname;

        @JsonProperty("name")
        private String name;

        @JsonProperty("email")
        private String email;

        @JsonProperty("gender")
        private String gender;

        @JsonProperty("age")
        private String age;

        @JsonProperty("birthday")
        private String birthday;

        @JsonProperty("profile_image")
        private String profileImage;

        @JsonProperty("birthyear")
        private String birthyear;

        @JsonProperty("mobile")
        private String mobile;
    }
}

