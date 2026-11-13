package com.uxight.api.domain.user;

import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

/** 관리자의 리서처 계정 생성 요청. 검증은 이메일 가입(SignupRequest)과 같다 — 어긋나면 400 GLB-ERR-002. 비밀번호는 서버가 만든다. */
public record UserCreateRequest(
    @NotBlank @Email(message = "이메일 형식이 올바르지 않습니다.") @Size(max = 255)
    String email,

    @NotBlank @Size(max = 100)
    String name
) {
}
