package com.uxight.api.domain.persona;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.Collection;
import java.util.List;

/**
 * 리서처가 쓸 수 있는 Persona = 본인 소유 + 공용(user_id NULL), 삭제 표시된 것은 제외.
 * 남의 Persona 와 삭제된 Persona 는 없는 것과 같다.
 * "본인 소유 또는 공용"은 메서드 이름 규칙으로 쓰면 OR 와 AND 의 묶음이 드러나지 않아 JPQL 로 적는다.
 */
public interface PersonaRepository extends JpaRepository<Persona, Long> {

  /** Persona 목록 · 실험 요청 폼. persona_id 순. */
  @Query("SELECT p FROM Persona p WHERE (p.user.id = :userId OR p.user IS NULL) AND p.deletedAt IS NULL ORDER BY p.id")
  List<Persona> findUsableByUserId(@Param("userId") Long userId);

  /** 실험 요청 시 고른 Persona 확인. 쓸 수 없는 id 는 결과에서 빠지므로 개수로 판정한다. */
  @Query("SELECT p FROM Persona p WHERE p.id IN :personaIds AND (p.user.id = :userId OR p.user IS NULL) "
      + "AND p.deletedAt IS NULL ORDER BY p.id")
  List<Persona> findUsableByIds(@Param("userId") Long userId, @Param("personaIds") Collection<Long> personaIds);
}
