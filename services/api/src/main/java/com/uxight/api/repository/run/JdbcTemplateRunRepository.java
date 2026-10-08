package com.uxight.api.repository.run;

import com.uxight.api.domain.run.ExperimentSummary;
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
import java.sql.Types;
import java.util.List;
import java.util.Optional;

@Repository
public class JdbcTemplateRunRepository implements RunRepository {

  private static final Logger log = LoggerFactory.getLogger(JdbcTemplateRunRepository.class);
  private static final RunRowMapper ROW_MAPPER = new RunRowMapper();
  private static final ExperimentSummaryRowMapper EXPERIMENT_ROW_MAPPER = new ExperimentSummaryRowMapper();

  // running 인데 heartbeat_at 이 이 시간보다 오래되면 stale. 임계값 미정 — [확인 필요]
  private static final int STALE_AFTER_SECONDS = 60;

  // 실험 = first_run_id 가 같은 회차들. 한 줄은 실험의 마지막 회차(run_id 최대) 기준이다.
  // state · end_type 계산은 이 SQL 한 곳에만 둔다 (design-decision 2.6).
  // awaiting_approval 은 improvements · approvals 테이블을 도입할 때 추가한다 — 지금 done 은 모두 completed.
  private static final String EXPERIMENTS_SQL = """
      SELECT r.first_run_id, r.run_id, r.status, r.mode, r.progress,
             (SELECT COUNT(*) FROM runs x WHERE x.first_run_id = r.first_run_id) AS round_no,
             CASE
               WHEN r.cancel_requested OR r.status IN ('failed', 'cancelled') THEN 'stopped'
               WHEN r.status IN ('queued', 'accepted', 'running') THEN 'in_progress'
               ELSE 'completed'
             END AS state,
             CASE
               WHEN NOT (r.cancel_requested OR r.status IN ('failed', 'cancelled')) THEN NULL
               WHEN r.status IN ('queued', 'accepted', 'running') THEN 'cancelling'
               WHEN r.status = 'failed' THEN 'failed'
               ELSE 'cancelled'
             END AS end_type,
             COALESCE(r.status = 'running' AND r.heartbeat_at < NOW() - INTERVAL %d SECOND, false) AS stale,
             f.status = 'done' AS has_result,
             p.title AS project_title,
             t.goal AS task_goal,
             JSON_LENGTH(r.persona_snapshot) AS persona_count,
             (SELECT SUM(TIMESTAMPDIFF(SECOND, COALESCE(x.started_at, x.created_at), COALESCE(x.finished_at, NOW())))
                FROM runs x WHERE x.first_run_id = r.first_run_id) AS elapsed_seconds,
             f.created_at
        FROM runs r
        JOIN runs f ON f.run_id = r.first_run_id
        JOIN projects p ON p.project_id = r.project_id
        JOIN tasks t ON t.task_id = r.task_id
       WHERE p.user_id = ?
         AND r.run_id = (SELECT MAX(x.run_id) FROM runs x WHERE x.first_run_id = r.first_run_id)
      """.formatted(STALE_AFTER_SECONDS);

  private final JdbcTemplate jdbcTemplate;

  public JdbcTemplateRunRepository(JdbcTemplate jdbcTemplate) {
    this.jdbcTemplate = jdbcTemplate;
  }

  @Override
  public Long save(Run run) {
    // PreparedStatementCreator 람다라 JdbcTemplate이 SQL을 자동으로 못 찍어줘서 직접 남긴다.
    String sql = "INSERT INTO runs (project_id, task_id, mode, loop_max, target_url_snapshot, "
        + "allowed_domains_snapshot, task_snapshot, policy_snapshot, persona_snapshot, cancel_requested, status) "
        + "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)";
    log.info("runs INSERT: {} [projectId={}, taskId={}, mode={}, status={}]",
        sql, run.projectId(), run.taskId(), run.mode(), run.status());

    KeyHolder keyHolder = new GeneratedKeyHolder();

    jdbcTemplate.update(connection -> {
      PreparedStatement ps = connection.prepareStatement(sql, Statement.RETURN_GENERATED_KEYS);
      ps.setLong(1, run.projectId());
      ps.setLong(2, run.taskId());
      ps.setString(3, run.mode());
      ps.setObject(4, run.loopMax(), Types.INTEGER);
      ps.setString(5, run.targetUrlSnapshot());
      ps.setString(6, run.allowedDomainsSnapshot());
      ps.setString(7, run.taskSnapshot());
      ps.setString(8, run.policySnapshot());
      ps.setString(9, run.personaSnapshot());
      ps.setBoolean(10, run.cancelRequested());
      ps.setString(11, run.status());
      return ps;
    }, keyHolder);

    return keyHolder.getKey().longValue();
  }

  @Override
  public void updateFirstRunId(Long runId, Long firstRunId) {
    jdbcTemplate.update("UPDATE runs SET first_run_id = ? WHERE run_id = ?", firstRunId, runId);
  }

  @Override
  public void updateDispatchState(Long runId, String dispatchState) {
    jdbcTemplate.update("UPDATE runs SET dispatch_state = ? WHERE run_id = ?", dispatchState, runId);
  }

  @Override
  public Optional<Run> findLastRound(Long firstRunId, Long userId) {
    return jdbcTemplate.query(
        "SELECT r.* FROM runs r JOIN projects p ON r.project_id = p.project_id "
        + "WHERE r.first_run_id = ? AND p.user_id = ? ORDER BY r.run_id DESC LIMIT 1",
        ROW_MAPPER, firstRunId, userId)
        .stream()
        .findFirst();
  }

  @Override
  public boolean requestCancel(Long runId) {
    return jdbcTemplate.update(
        "UPDATE runs SET cancel_requested = true WHERE run_id = ? AND status IN ('queued', 'accepted', 'running')",
        runId) == 1;
  }

  @Override
  public List<ExperimentSummary> findExperiments(Long userId, String state, int offset, int limit) {
    return jdbcTemplate.query(
        "SELECT * FROM (" + EXPERIMENTS_SQL + ") e WHERE (? IS NULL OR e.state = ?) "
        + "ORDER BY e.first_run_id DESC LIMIT ? OFFSET ?",
        EXPERIMENT_ROW_MAPPER, userId, state, state, limit, offset);
  }

  @Override
  public long countExperiments(Long userId, String state) {
    return jdbcTemplate.queryForObject(
        "SELECT COUNT(*) FROM (" + EXPERIMENTS_SQL + ") e WHERE (? IS NULL OR e.state = ?)",
        Long.class, userId, state, state);
  }
}
