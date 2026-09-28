package com.uxight.api.repository.task;

import com.uxight.api.domain.task.Task;
import com.uxight.api.domain.task.TaskRepository;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.support.GeneratedKeyHolder;
import org.springframework.jdbc.support.KeyHolder;
import org.springframework.stereotype.Repository;

import java.sql.PreparedStatement;
import java.sql.Statement;
import java.util.Optional;

@Repository
public class JdbcTemplateTaskRepository implements TaskRepository {

  private static final TaskRowMapper ROW_MAPPER = new TaskRowMapper();

  private final JdbcTemplate jdbcTemplate;

  public JdbcTemplateTaskRepository(JdbcTemplate jdbcTemplate) {
    this.jdbcTemplate = jdbcTemplate;
  }

  @Override
  public Optional<Task> findById(Long taskId) {
    return jdbcTemplate
        .query("SELECT * FROM tasks WHERE task_id = ?", ROW_MAPPER, taskId)
        .stream()
        .findFirst();
  }

  @Override
  public Long save(Task task) {
    KeyHolder keyHolder = new GeneratedKeyHolder();

    jdbcTemplate.update(connection -> {
      PreparedStatement ps = connection.prepareStatement(
          "INSERT INTO tasks (project_id, goal, success_criteria, is_one_shot) VALUES (?, ?, ?, ?)",
          Statement.RETURN_GENERATED_KEYS);
      ps.setLong(1, task.projectId());
      ps.setString(2, task.goal());
      ps.setString(3, task.successCriteria());
      ps.setBoolean(4, task.isOneShot());
      return ps;
    }, keyHolder);

    return keyHolder.getKey().longValue();
  }
}
