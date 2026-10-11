package com.uxight.api.web.auth;

import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

public record SignupRequest(
    @NotBlank @Email(message = "이메일 형식이 올바르지 않습니다.") @Size(max = 255)
    String email,

    // 8~12자, 영어 소문자와 숫자를 각각 하나 이상. 12자 상한이라 BCrypt 72바이트 제한에 걸리지 않는다.
    @NotNull
    @Pattern(regexp = "^(?=.*[a-z])(?=.*\\d).{8,12}$", message = "비밀번호는 영어 소문자와 숫자를 포함한 8~12자여야 합니다")
    String password,

    @NotBlank @Size(max = 100)
    String name
) {
}
