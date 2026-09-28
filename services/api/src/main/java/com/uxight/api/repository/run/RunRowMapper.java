package com.uxight.api.repository.run;

import com.uxight.api.domain.run.Run;
import org.springframework.jdbc.core.RowMapper;

import java.math.BigDecimal;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Timestamp;

public class RunRowMapper implements RowMapper<Run> {

  @Override
  public Run mapRow(ResultSet rs, int rowNum) throws SQLException {
    Timestamp heartbeatAt = rs.getTimestamp("heartbeat_at");
    Timestamp acceptedAt = rs.getTimestamp("accepted_at");
    Timestamp startedAt = rs.getTimestamp("started_at");

    return new Run(
        rs.getLong("run_id"),
        rs.getLong("project_id"),
        rs.getLong("task_id"),
        rs.getString("mode"),
        (Integer) rs.getObject("loop_max"),
        (Long) rs.getObject("parent_run_id"),
        (Long) rs.getObject("improvement_id"),
        rs.getString("target_url_snapshot"),
        rs.getString("task_snapshot"),
        rs.getString("policy_snapshot"),
        rs.getString("persona_snapshot"),
        rs.getString("dispatch_state"),
        rs.getBoolean("cancel_requested"),
        rs.getString("status"),
        (Integer) rs.getObject("progress"),
        heartbeatAt != null ? heartbeatAt.toLocalDateTime() : null,
        rs.getBoolean("next_loop_requested"),
        rs.getString("error"),
        (Long) rs.getObject("tokens"),
        rs.getBigDecimal("cost_usd"),
        acceptedAt != null ? acceptedAt.toLocalDateTime() : null,
        startedAt != null ? startedAt.toLocalDateTime() : null,
        rs.getTimestamp("created_at").toLocalDateTime()
    );
  }
}
