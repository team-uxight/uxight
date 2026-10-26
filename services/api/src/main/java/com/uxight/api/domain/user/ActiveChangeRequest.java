package com.uxight.api.domain.user;

import jakarta.validation.constraints.NotNull;

/** 계정 활성 상태 변경 요청. false 면 비활성화, true 면 활성화. 빠지면 400 GLB-ERR-002. */
public record ActiveChangeRequest(
    @NotNull
    Boolean isActive
) {
}
