package com.uxight.api.domain.run;

import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

import java.util.List;

public record ExperimentCreateRequest(
    @NotBlank @Size(max = 200)
    String goal,

    @NotBlank @Size(max = 2048)
    @Pattern(regexp = "^https?://.+", message = "http:// 또는 https://로 시작하는 URL이어야 합니다")
    String successUrl,

    @NotEmpty
    List<@NotNull Long> personaIds,

    @NotNull @Pattern(regexp = "diagnose|improve|loop", message = "diagnose, improve, loop 중 하나여야 합니다")
    String mode,

    @Min(1)
    Integer loopMax   // mode=loop 일 때 필수 — RunService 에서 검사
) {
}
