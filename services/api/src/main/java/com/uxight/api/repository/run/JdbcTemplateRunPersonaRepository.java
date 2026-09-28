package com.uxight.api.repository.run;

import com.uxight.api.domain.run.RunPersona;
import com.uxight.api.domain.run.RunPersonaRepository;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public class JdbcTemplateRunPersonaRepository implements RunPersonaRepository {

  private static final RunPersonaRowMapper ROW_MAPPER = new RunPersonaRowMapper();

  private final JdbcTemplate jdbcTemplate;

  public JdbcTemplateRunPersonaRepository(JdbcTemplate jdbcTemplate) {
    this.jdbcTemplate = jdbcTemplate;
  }

  @Override
  public List<RunPersona> findByRunId(Long runId) {
    return jdbcTemplate.query("SELECT * FROM run_personas WHERE run_id = ?", ROW_MAPPER, runId);
  }
}
