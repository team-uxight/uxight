package com.uxight.api.domain.persona;

import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

import java.util.Map;

/** profile 의 필수 속성은 Persona.create 가 확인한다 (Persona.REQUIRED_PROFILE_KEYS). */
public record PersonaCreateRequest(
    // 빈 값 · 공백뿐인 값 · 앞뒤 공백을 한 규칙으로 막는다 (프로젝트 제목과 같은 규칙)
    @NotNull @Size(max = 100)
    @Pattern(regexp = "^\\S(.*\\S)?$", message = "비어 있거나 앞뒤에 공백이 있으면 안 됩니다")
    String name,

    @NotNull
    Map<String, Object> profile   // JSON 객체. 키는 camelCase
) {
}
