package com.uxight.api.domain.persona;

import java.util.List;
import java.util.Optional;

public interface PersonaRepository {

  Optional<Persona> findById(Long personaId);

  List<Persona> findByProjectId(Long projectId);

  void save(Persona persona);
}
