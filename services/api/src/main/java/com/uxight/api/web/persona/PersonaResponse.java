package com.uxight.api.web.persona;

import com.uxight.api.domain.persona.Persona;

import java.util.Map;

/** 프론트엔드는 isCommon 이 true 인 Persona 에 삭제 버튼을 보여 주지 않는다. */
public record PersonaResponse(
    Long personaId,
    String name,
    Map<String, Object> profile,   // DB 의 JSON 객체 그대로. 키 구성은 미확정 (GACA-66)
    boolean isCommon
) {
  public static PersonaResponse from(Persona persona) {
    return new PersonaResponse(persona.getId(), persona.getName(), persona.getProfile(), persona.isCommon());
  }
}
