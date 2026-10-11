package com.uxight.api.domain.project;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

import java.util.List;

/**
 * 바꿀 항목만 보낸다. null(키 없음 · null 값)인 항목은 그대로 둔다. 설명을 지우려면 빈 문자열을 보낸다.
 * 검증 규칙은 ProjectCreateRequest 와 같다 — @Size · @Pattern 은 null 을 통과시키므로 보내지 않은 항목은 검사하지 않는다.
 */
public record ProjectUpdateRequest(
    @Size(max = 100)
    @Pattern(regexp = "^\\S(.*\\S)?$", message = "비어 있거나 앞뒤에 공백이 있으면 안 됩니다")
    String title,

    @Size(max = 2048)
    @Pattern(regexp = "^https?://.+", message = "http:// 또는 https://로 시작하는 URL이어야 합니다")
    String targetUrl,

    @Size(max = 1000)
    String description,

    List<@NotBlank String> allowedDomains
) {
}
