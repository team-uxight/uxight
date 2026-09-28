package com.uxight.api.repository.persona;

import com.uxight.api.domain.persona.Persona;
import com.uxight.api.domain.persona.PersonaRepository;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

@Repository
public class JdbcTemplatePersonaRepository implements PersonaRepository {

  private static final PersonaRowMapper ROW_MAPPER = new PersonaRowMapper();

  private final JdbcTemplate jdbcTemplate;

  public JdbcTemplatePersonaRepository(JdbcTemplate jdbcTemplate) {
    this.jdbcTemplate = jdbcTemplate;
  }

  @Override
  public Optional<Persona> findById(Long personaId) {
    return jdbcTemplate
        .query("SELECT * FROM personas WHERE persona_id = ?", ROW_MAPPER, personaId)
        .stream()
        .findFirst();
  }

  @Override
  public List<Persona> findByProjectId(Long projectId) {
    return jdbcTemplate.query("SELECT * FROM personas WHERE project_id = ?", ROW_MAPPER, projectId);
  }

  @Override
  public void save(Persona persona) {
    jdbcTemplate.update(
        "INSERT INTO personas (project_id, name, profile) VALUES (?, ?, ?)",
        persona.projectId(), persona.name(), persona.profile());
  }
}
