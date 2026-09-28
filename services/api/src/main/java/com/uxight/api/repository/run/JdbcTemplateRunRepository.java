package com.uxight.api.repository.run;

import com.uxight.api.domain.run.Run;
import com.uxight.api.domain.run.RunRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.support.GeneratedKeyHolder;
import org.springframework.jdbc.support.KeyHolder;
import org.springframework.stereotype.Repository;

import java.sql.PreparedStatement;
import java.sql.Statement;
import java.util.List;

@Repository
public class JdbcTemplateRunRepository implements RunRepository {

  private static final Logger log = LoggerFactory.getLogger(JdbcTemplateRunRepository.class);
  private static final RunRowMapper ROW_MAPPER = new RunRowMapper();

  private final JdbcTemplate jdbcTemplate;

  public JdbcTemplateRunRepository(JdbcTemplate jdbcTemplate) {
    this.jdbcTemplate = jdbcTemplate;
  }

  @Override
  public Long save(Run run) {
    // PreparedStatementCreator 람다라 JdbcTemplate이 SQL을 자동으로 못 찍어줘서 직접 남긴다.
    String sql = "INSERT INTO runs (project_id, task_id, mode, target_url_snapshot, task_snapshot, "
        + "policy_snapshot, persona_snapshot, cancel_requested, status, next_loop_requested) "
        + "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)";
    log.info("runs INSERT: {} [projectId={}, taskId={}, status={}]", sql, run.projectId(), run.taskId(), run.status());

    KeyHolder keyHolder = new GeneratedKeyHolder();

    jdbcTemplate.update(connection -> {
      PreparedStatement ps = connection.prepareStatement(sql, Statement.RETURN_GENERATED_KEYS);
      ps.setLong(1, run.projectId());
      ps.setLong(2, run.taskId());
      ps.setString(3, run.mode());
      ps.setString(4, run.targetUrlSnapshot());
      ps.setString(5, run.taskSnapshot());
      ps.setString(6, run.policySnapshot());
      ps.setString(7, run.personaSnapshot());
      ps.setBoolean(8, run.cancelRequested());
      ps.setString(9, run.status());
      ps.setBoolean(10, run.nextLoopRequested());
      return ps;
    }, keyHolder);

    return keyHolder.getKey().longValue();
  }

  @Override
  public void updateDispatchState(Long runId, String dispatchState) {
    jdbcTemplate.update("UPDATE runs SET dispatch_state = ? WHERE run_id = ?", dispatchState, runId);
  }

  @Override
  public List<Run> findActiveByUserId(Long userId) {
    return jdbcTemplate.query(
        "SELECT r.* FROM runs r JOIN projects p ON r.project_id = p.project_id "
        + "WHERE p.user_id = ? AND r.status IN ('queued', 'accepted', 'running') "
        + "ORDER BY r.created_at DESC",
        ROW_MAPPER, userId);
  }

  @Override
  public List<Run> findEndedByUserId(Long userId) {
    return jdbcTemplate.query(
        "SELECT r.* FROM runs r JOIN projects p ON r.project_id = p.project_id "
        + "WHERE p.user_id = ? AND (r.status IN ('done', 'failed', 'cancelled') OR r.cancel_requested = true) "
        + "ORDER BY r.created_at DESC",
        ROW_MAPPER, userId);
  }

  @Override
  public void requestCancel(Long runId) {
    jdbcTemplate.update(
        "UPDATE runs SET cancel_requested = true WHERE run_id = ? AND status NOT IN ('done', 'failed', 'cancelled')",
        runId);
  }
}
