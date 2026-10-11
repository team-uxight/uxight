package com.uxight.api.repository.run;

import com.uxight.api.domain.run.ExperimentSummary;
import org.springframework.jdbc.core.RowMapper;

import java.sql.ResultSet;
import java.sql.SQLException;

public class ExperimentSummaryRowMapper implements RowMapper<ExperimentSummary> {

  @Override
  public ExperimentSummary mapRow(ResultSet rs, int rowNum) throws SQLException {
    return new ExperimentSummary(
        rs.getLong("first_run_id"),
        rs.getLong("run_id"),
        rs.getInt("round_no"),
        rs.getString("status"),
        rs.getString("state"),
        rs.getString("end_type"),
        rs.getBoolean("stale"),
        rs.getBoolean("has_result"),
        rs.getString("project_title"),
        rs.getString("task_goal"),
        rs.getString("mode"),
        (Integer) rs.getObject("progress"),
        rs.getInt("persona_count"),
        rs.getLong("elapsed_seconds"),
        rs.getTimestamp("created_at").toLocalDateTime()
    );
  }
}
