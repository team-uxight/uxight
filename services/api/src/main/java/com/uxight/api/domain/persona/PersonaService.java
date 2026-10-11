package com.uxight.api.domain.persona;

import com.uxight.api.domain.user.UserRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

@Service
public class PersonaService {

  private final PersonaRepository personaRepository;
  private final UserRepository userRepository;

  @Autowired
  public PersonaService(PersonaRepository personaRepository, UserRepository userRepository) {
    this.personaRepository = personaRepository;
    this.userRepository = userRepository;
  }

  /** 요청한 리서처 소유로 저장한다. 이름 · 속성이 같은 Persona 가 있어도 새로 만든다. */
  @Transactional
  public Long createPersona(Long userId, PersonaCreateRequest request) {
    // 소유자는 user_id FK 만 쓰면 된다 — 사용자 행은 읽지 않는다 (LoginCheckInterceptor 가 이미 확인했다).
    Persona persona = Persona.create(userRepository.getReferenceById(userId), request.name(), request.profile());
    return personaRepository.save(persona).getId();
  }

  /** 본인 소유 Persona 와 공용 Persona. 삭제된 Persona 는 빠진다. */
  @Transactional(readOnly = true)
  public List<Persona> getPersonasByUser(Long userId) {
    return personaRepository.findUsableByUserId(userId);
  }
}
