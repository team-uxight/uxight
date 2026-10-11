package com.uxight.api.domain.project;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

import java.util.List;

public record ProjectCreateRequest(
    // 빈 값 · 공백뿐인 값 · 앞뒤 공백을 한 규칙으로 막는다 (@NotBlank 를 겹치면 공백뿐인 값에 오류가 두 개 나온다).
    @NotNull @Size(max = 100)
    @Pattern(regexp = "^\\S(.*\\S)?$", message = "비어 있거나 앞뒤에 공백이 있으면 안 됩니다")
    String title,

    @NotBlank @Size(max = 2048)
    // agent 가 여는 것은 웹 페이지뿐 — file:/ · javascript: 같은 스킴은 막는다 (agent-safety §2.2).
    @Pattern(regexp = "^https?://.+", message = "http:// 또는 https://로 시작하는 URL이어야 합니다")
    String targetUrl,

    @Size(max = 1000)   // 길이 상한 미정 (API 명세) — 정해지면 바꾼다
    String description,

    @NotNull
    List<@NotBlank String> allowedDomains
) {
}
