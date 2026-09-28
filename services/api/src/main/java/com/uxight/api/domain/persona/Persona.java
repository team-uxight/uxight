package com.uxight.api.domain.persona;

import java.time.LocalDateTime;

public record Persona(
    Long personaId,
    Long projectId,
    String name,
    String profile,
    LocalDateTime createdAt,
    LocalDateTime updatedAt
) {
  public static Persona newPersona(Long projectId, String name, String profile) {
    return new Persona(null, projectId, name, profile, null, null);
  }
}
