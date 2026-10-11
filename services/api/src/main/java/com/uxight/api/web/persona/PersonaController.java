package com.uxight.api.web.persona;

import com.uxight.api.domain.persona.PersonaCreateRequest;
import com.uxight.api.domain.persona.PersonaService;
import com.uxight.api.web.common.AuthConst;
import jakarta.validation.Valid;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestAttribute;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
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

  /** 요청한 리서처 소유의 Persona 를 만든다. 수정 API 는 없다 — 바꾸려면 삭제한 뒤 다시 생성한다. */
  @PostMapping
  @ResponseStatus(HttpStatus.CREATED)
  public PersonaCreateResponse createPersona(@Valid @RequestBody PersonaCreateRequest request,
      @RequestAttribute(AuthConst.LOGIN_USER_ID) Long userId) {
    return new PersonaCreateResponse(personaService.createPersona(userId, request));
  }

  /** 삭제 표시만 한다. 없거나 · 남의 것이거나 · 공용이거나 · 이미 삭제한 Persona 는 404 EXP-ERR-003. */
  @DeleteMapping("/{personaId}")
  @ResponseStatus(HttpStatus.NO_CONTENT)
  public void deletePersona(@PathVariable Long personaId, @RequestAttribute(AuthConst.LOGIN_USER_ID) Long userId) {
    personaService.deletePersona(userId, personaId);
  }
}
