package com.uxight.api.repository.persona;

import com.uxight.api.domain.persona.Persona;
import com.uxight.api.domain.persona.PersonaRepository;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

import java.util.ArrayList;
import java.util.Collection;
import java.util.Collections;
import java.util.List;

@Repository
public class JdbcTemplatePersonaRepository implements PersonaRepository {

  private static final PersonaRowMapper ROW_MAPPER = new PersonaRowMapper();

  private final JdbcTemplate jdbcTemplate;

  public JdbcTemplatePersonaRepository(JdbcTemplate jdbcTemplate) {
    this.jdbcTemplate = jdbcTemplate;
  }

  @Override
  public List<Persona> findUsableByUserId(Long userId) {
    return jdbcTemplate.query(
        "SELECT * FROM personas WHERE user_id = ? OR user_id IS NULL ORDER BY persona_id",
        ROW_MAPPER, userId);
  }

  @Override
  public List<Persona> findUsableByIds(Long userId, Collection<Long> personaIds) {
    if (personaIds.isEmpty()) {
      return List.of();
    }
    String placeholders = String.join(", ", Collections.nCopies(personaIds.size(), "?"));
    List<Object> args = new ArrayList<>(personaIds);
    args.add(userId);
    return jdbcTemplate.query(
        "SELECT * FROM personas WHERE persona_id IN (" + placeholders + ") "
        + "AND (user_id = ? OR user_id IS NULL) ORDER BY persona_id",
        ROW_MAPPER, args.toArray());
  }
}
