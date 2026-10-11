package com.uxight.api.web.auth;

import jakarta.validation.constraints.NotBlank;

public record GoogleLoginRequest(
    @NotBlank
    String idToken   // Google 이 프론트엔드에 발급한 ID 토큰
) {
}
