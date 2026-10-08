package com.uxight.api.repository.project;

import com.uxight.api.domain.project.Project;
import org.springframework.jdbc.core.RowMapper;

import java.sql.ResultSet;
import java.sql.SQLException;

public class ProjectRowMapper implements RowMapper<Project> {

  @Override
  public Project mapRow(ResultSet rs, int rowNum) throws SQLException {
    return new Project(
        rs.getLong("project_id"),
        rs.getLong("user_id"),
        rs.getString("title"),
        rs.getString("target_url"),
        rs.getString("description"),
        rs.getString("allowed_domains"),
        rs.getTimestamp("created_at").toLocalDateTime(),
        rs.getTimestamp("updated_at").toLocalDateTime()
    );
  }
}
