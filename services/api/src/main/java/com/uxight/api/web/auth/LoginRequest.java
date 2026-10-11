package com.uxight.api.web.auth;

import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;

// 비밀번호 형식(8~12자 등)은 가입에서만 본다 — 로그인은 해시 비교가 판정한다.
public record LoginRequest(
    @NotBlank @Email(message = "이메일 형식이 올바르지 않습니다.")
    String email,

    @NotBlank
    String password
) {
}
