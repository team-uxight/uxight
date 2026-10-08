package com.uxight.api.repository.run;

import com.uxight.api.domain.run.Run;
import org.springframework.jdbc.core.RowMapper;

import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Timestamp;
import java.time.LocalDateTime;

public class RunRowMapper implements RowMapper<Run> {

  @Override
  public Run mapRow(ResultSet rs, int rowNum) throws SQLException {
    return new Run(
        rs.getLong("run_id"),
        rs.getLong("project_id"),
        rs.getLong("task_id"),
        rs.getString("mode"),
        (Integer) rs.getObject("loop_max"),
        (Long) rs.getObject("parent_run_id"),
        (Long) rs.getObject("first_run_id"),
        (Long) rs.getObject("improvement_id"),
        rs.getString("target_url_snapshot"),
        rs.getString("allowed_domains_snapshot"),
        rs.getString("task_snapshot"),
        rs.getString("policy_snapshot"),
        rs.getString("persona_snapshot"),
        rs.getString("dispatch_state"),
        rs.getBoolean("cancel_requested"),
        rs.getString("status"),
        (Integer) rs.getObject("progress"),
        toLocalDateTime(rs.getTimestamp("heartbeat_at")),
        rs.getString("error"),
        (Long) rs.getObject("tokens"),
        rs.getBigDecimal("cost_usd"),
        toLocalDateTime(rs.getTimestamp("accepted_at")),
        toLocalDateTime(rs.getTimestamp("started_at")),
        toLocalDateTime(rs.getTimestamp("finished_at")),
        rs.getTimestamp("created_at").toLocalDateTime()
    );
  }

  private static LocalDateTime toLocalDateTime(Timestamp timestamp) {
    return timestamp != null ? timestamp.toLocalDateTime() : null;
  }
}
