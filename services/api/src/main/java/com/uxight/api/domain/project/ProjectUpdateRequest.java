package com.uxight.api.domain.project;

import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

/**
 * 프로젝트 수정은 제목과 설명만 가능하다. 대상 URL · 허용 도메인은 화면에서 읽기 전용으로 보여 준다.
 * 다른 항목을 함께 보내도 무시한다 (수정 폼이 기존 값을 통째로 보내도 된다).
 * null(키 없음 · null 값)인 항목은 그대로 둔다. 설명을 지우려면 빈 문자열을 보낸다.
 * 검증 규칙은 ProjectCreateRequest 와 같다 — @Size · @Pattern 은 null 을 통과시키므로 보내지 않은 항목은 검사하지 않는다.
 */
public record ProjectUpdateRequest(
    @Size(max = 100)
    @Pattern(regexp = "^\\S(.*\\S)?$", message = "비어 있거나 앞뒤에 공백이 있으면 안 됩니다")
    String title,

    @Size(max = 1000)
    String description
) {
}
