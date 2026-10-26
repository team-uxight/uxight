package com.uxight.api.repository.runlog;

import com.uxight.api.domain.runlog.RunPersonaQueryRepository;
import com.uxight.api.domain.runlog.RunPersonaStatus;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

import java.sql.Timestamp;
import java.util.List;

@Repository
public class JdbcTemplateRunPersonaQueryRepository implements RunPersonaQueryRepository {

  private final JdbcTemplate jdbcTemplate;

  @Autowired
  public JdbcTemplateRunPersonaQueryRepository(JdbcTemplate jdbcTemplate) {
    this.jdbcTemplate = jdbcTemplate;
  }

  @Override
  public List<RunPersonaStatus> findByRunId(long runId) {
    return jdbcTemplate.query("SELECT persona_id, status, steps, finished_at FROM run_personas WHERE run_id = ?",
        (rs, rowNum) -> {
          Timestamp finishedAt = rs.getTimestamp("finished_at");
          return new RunPersonaStatus(rs.getLong("persona_id"), rs.getString("status"),
              rs.getObject("steps", Integer.class), finishedAt == null ? null : finishedAt.toLocalDateTime());
        },
        runId);
  }
}
