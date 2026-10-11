package com.uxight.api.web.persona;

import com.uxight.api.domain.persona.PersonaService;
import com.uxight.api.web.common.AuthConst;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestAttribute;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/personas")
public class PersonaController {

  private final PersonaService personaService;

  @Autowired
  public PersonaController(PersonaService personaService) {
    this.personaService = personaService;
  }

  /** 실험 요청 폼의 Persona 선택 목록 — 본인 소유와 공용을 함께, 삭제된 Persona 는 빼고. */
  @GetMapping
  public PersonaListResponse personas(@RequestAttribute(AuthConst.LOGIN_USER_ID) Long userId) {
    return new PersonaListResponse(personaService.getPersonasByUser(userId).stream()
        .map(PersonaResponse::from)
        .toList());
  }
}
