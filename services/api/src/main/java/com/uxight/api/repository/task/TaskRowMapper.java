package com.uxight.api.repository.task;

import com.uxight.api.domain.task.Task;
import org.springframework.jdbc.core.RowMapper;

import java.sql.ResultSet;
import java.sql.SQLException;

public class TaskRowMapper implements RowMapper<Task> {

  @Override
  public Task mapRow(ResultSet rs, int rowNum) throws SQLException {
    return new Task(
        rs.getLong("task_id"),
        rs.getLong("project_id"),
        rs.getString("goal"),
        rs.getString("success_criteria"),
        rs.getBoolean("is_one_shot"),
        rs.getTimestamp("created_at").toLocalDateTime(),
        rs.getTimestamp("updated_at").toLocalDateTime()
    );
  }
}
