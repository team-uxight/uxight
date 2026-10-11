package com.uxight.api.repository.task;

import com.uxight.api.domain.task.Task;
import com.uxight.api.domain.task.TaskRepository;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.support.GeneratedKeyHolder;
import org.springframework.jdbc.support.KeyHolder;
import org.springframework.stereotype.Repository;

import java.sql.PreparedStatement;
import java.sql.Statement;

@Repository
public class JdbcTemplateTaskRepository implements TaskRepository {

  private final JdbcTemplate jdbcTemplate;

  public JdbcTemplateTaskRepository(JdbcTemplate jdbcTemplate) {
    this.jdbcTemplate = jdbcTemplate;
  }

  @Override
  public Long save(Task task) {
    KeyHolder keyHolder = new GeneratedKeyHolder();

    jdbcTemplate.update(connection -> {
      PreparedStatement ps = connection.prepareStatement(
          "INSERT INTO tasks (project_id, goal, success_rule, success_url, is_one_shot) VALUES (?, ?, ?, ?, ?)",
          Statement.RETURN_GENERATED_KEYS);
      ps.setLong(1, task.projectId());
      ps.setString(2, task.goal());
      ps.setString(3, task.successRule());
      ps.setString(4, task.successUrl());
      ps.setBoolean(5, task.isOneShot());
      return ps;
    }, keyHolder);

    return keyHolder.getKey().longValue();
  }
}
