package com.uxight.api.domain.user;

import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Pattern;

/** 계정 역할 변경 요청. 없는 역할 값은 400 GLB-ERR-002. */
public record RoleChangeRequest(
    @NotNull @Pattern(regexp = "admin|maintainer|researcher", message = "admin, maintainer, researcher 중 하나여야 합니다")
    String role
) {
}
