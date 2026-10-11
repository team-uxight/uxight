package com.uxight.api.domain.persona;

import com.uxight.api.common.ApiException;
import com.uxight.api.common.ErrorCode;
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

  /**
   * 본인 소유이고 아직 삭제되지 않은 Persona 만 삭제 표시한다. 없거나 · 남의 것이거나 · 공용이거나 · 이미 삭제됐으면 404.
   * 진행 중인 실험에서 쓰는 Persona 도 삭제할 수 있다 — 회차는 Persona 스냅샷으로 실행되므로 프로젝트 행을 잠그지 않는다.
   */
  @Transactional
  public void deletePersona(Long userId, Long personaId) {
    Persona persona = personaRepository.findByIdAndUserIdAndDeletedAtIsNull(personaId, userId)
        .orElseThrow(() -> new ApiException(ErrorCode.PERSONA_NOT_FOUND));
    persona.delete();
  }

  /** 본인 소유 Persona 와 공용 Persona. 삭제된 Persona 는 빠진다. */
  @Transactional(readOnly = true)
  public List<Persona> getPersonasByUser(Long userId) {
    return personaRepository.findUsableByUserId(userId);
  }
}
