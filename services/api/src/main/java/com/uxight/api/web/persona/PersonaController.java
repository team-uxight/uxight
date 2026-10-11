package com.uxight.api.web.persona;

import com.uxight.api.domain.persona.PersonaRepository;
import com.uxight.api.web.common.AuthConst;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.bind.annotation.RequestAttribute;

import java.util.List;
import java.util.Map;

@RestController
public class PersonaController {

  private final PersonaRepository personaRepository;

  public PersonaController(PersonaRepository personaRepository) {
    this.personaRepository = personaRepository;
  }

  /** 실험 요청 폼의 Persona 선택 목록 — 본인 소유와 공용을 함께. */
  @GetMapping("/api/personas")
  public Map<String, List<PersonaResponse>> personas(@RequestAttribute(AuthConst.LOGIN_USER_ID) Long userId) {
    List<PersonaResponse> personas = personaRepository.findUsableByUserId(userId).stream()
        .map(PersonaResponse::from)
        .toList();
    return Map.of("personas", personas);
  }
}
