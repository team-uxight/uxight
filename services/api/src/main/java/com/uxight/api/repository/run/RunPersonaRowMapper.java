package com.uxight.api.repository.run;

import com.uxight.api.domain.run.RunPersona;
import org.springframework.jdbc.core.RowMapper;

import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Timestamp;

public class RunPersonaRowMapper implements RowMapper<RunPersona> {

  @Override
  public RunPersona mapRow(ResultSet rs, int rowNum) throws SQLException {
    Timestamp startedAt = rs.getTimestamp("started_at");
    Timestamp finishedAt = rs.getTimestamp("finished_at");

    return new RunPersona(
        rs.getLong("run_persona_id"),
        rs.getLong("run_id"),
        rs.getLong("persona_id"),
        rs.getString("status"),
        (Boolean) rs.getObject("agent_done"),
        (Boolean) rs.getObject("rule_success"),
        (Integer) rs.getObject("steps"),
        (Integer) rs.getObject("backtracks"),
        (Long) rs.getObject("tokens"),
        rs.getBigDecimal("cost_usd"),
        rs.getString("log_path"),
        startedAt != null ? startedAt.toLocalDateTime() : null,
        finishedAt != null ? finishedAt.toLocalDateTime() : null
    );
  }
}
