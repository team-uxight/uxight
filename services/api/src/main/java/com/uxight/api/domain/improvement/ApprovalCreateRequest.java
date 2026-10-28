package com.uxight.api.domain.improvement;

import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Pattern;

/**
 * 다음 회차 승인 · 반려 요청. 빠진 값 · 없는 결정 값은 400 GLB-ERR-002.
 *
 * @param improvementId 결정할 개선안 — 경로의 회차에서 산출한 개선안이어야 한다
 * @param note          결정 사유(선택). 빈 값은 저장하지 않는다
 */
public record ApprovalCreateRequest(
    @NotNull
    Long improvementId,

    @NotNull @Pattern(regexp = "approve|reject", message = "approve, reject 중 하나여야 합니다")
    String decision,

    String note
) {
}
