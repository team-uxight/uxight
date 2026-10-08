package com.uxight.api.domain.persona;

import java.time.LocalDateTime;

public record Persona(
    Long personaId,
    Long userId,         // NULL = 관리자 소유 공용 Persona
    String name,
    String profile,      // JSON 객체 원문
    LocalDateTime createdAt,
    LocalDateTime updatedAt
) {
  public boolean isCommon() {
    return userId == null;
  }
}
