package com.uxight.api.domain.persona;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

@Service
public class PersonaService {

  private final PersonaRepository personaRepository;

  @Autowired
  public PersonaService(PersonaRepository personaRepository) {
    this.personaRepository = personaRepository;
  }

  /** 본인 소유 Persona 와 공용 Persona. 삭제된 Persona 는 빠진다. */
  @Transactional(readOnly = true)
  public List<Persona> getPersonasByUser(Long userId) {
    return personaRepository.findUsableByUserId(userId);
  }
}
