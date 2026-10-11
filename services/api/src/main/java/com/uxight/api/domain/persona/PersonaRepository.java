package com.uxight.api.domain.persona;

import java.util.Collection;
import java.util.List;

/** 리서처가 쓸 수 있는 Persona = 본인 소유 + 공용(user_id NULL). 남의 Persona 는 없는 것과 같다. */
public interface PersonaRepository {

  List<Persona> findUsableByUserId(Long userId);

  List<Persona> findUsableByIds(Long userId, Collection<Long> personaIds);
}
