package com.uxight.api.repository.project;

import com.uxight.api.domain.project.Project;
import com.uxight.api.domain.project.ProjectRepository;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.support.GeneratedKeyHolder;
import org.springframework.jdbc.support.KeyHolder;
import org.springframework.stereotype.Repository;

import java.sql.PreparedStatement;
import java.sql.Statement;
import java.util.List;
import java.util.Optional;

@Repository
public class JdbcTemplateProjectRepository implements ProjectRepository {

  private static final ProjectRowMapper ROW_MAPPER = new ProjectRowMapper();

  private final JdbcTemplate jdbcTemplate;

  public JdbcTemplateProjectRepository(JdbcTemplate jdbcTemplate) {
    this.jdbcTemplate = jdbcTemplate;
  }

  @Override
  public Optional<Project> findByIdAndUserId(Long projectId, Long userId) {
    return jdbcTemplate
        .query("SELECT * FROM projects WHERE project_id = ? AND user_id = ?", ROW_MAPPER, projectId, userId)
        .stream()
        .findFirst();
  }

  @Override
  public List<Project> findByUserId(Long userId) {
    return jdbcTemplate.query("SELECT * FROM projects WHERE user_id = ? ORDER BY created_at DESC", ROW_MAPPER, userId);
  }

  @Override
  public Long save(Project project) {
    KeyHolder keyHolder = new GeneratedKeyHolder();

    jdbcTemplate.update(connection -> {
      PreparedStatement ps = connection.prepareStatement(
          "INSERT INTO projects (user_id, title, target_url, description, allowed_domains) VALUES (?, ?, ?, ?, ?)",
          Statement.RETURN_GENERATED_KEYS);
      ps.setLong(1, project.userId());
      ps.setString(2, project.title());
      ps.setString(3, project.targetUrl());
      ps.setString(4, project.description());
      ps.setString(5, project.allowedDomains());
      return ps;
    }, keyHolder);

    return keyHolder.getKey().longValue();
  }
}
