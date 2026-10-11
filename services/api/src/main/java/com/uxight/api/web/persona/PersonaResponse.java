package com.uxight.api.web.persona;

import com.fasterxml.jackson.annotation.JsonRawValue;
import com.uxight.api.domain.persona.Persona;

public record PersonaResponse(
    Long personaId,
    String name,
    @JsonRawValue String profile,   // DB 의 JSON 객체를 그대로 싣는다
    boolean isCommon
) {
  public static PersonaResponse from(Persona persona) {
    return new PersonaResponse(persona.personaId(), persona.name(), persona.profile(), persona.isCommon());
  }
}
