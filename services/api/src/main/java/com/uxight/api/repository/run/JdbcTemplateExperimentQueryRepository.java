package com.uxight.api.repository.run;

import com.uxight.api.domain.run.ExperimentQueryRepository;
import com.uxight.api.domain.run.ExperimentSummary;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

import java.util.List;

/** 실험 목록 · 건수 집계 SQL. 회차의 저장 · 변경은 RunRepository(JPA) 가 한다. */
@Repository
public class JdbcTemplateExperimentQueryRepository implements ExperimentQueryRepository {

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

  @Autowired
  public JdbcTemplateExperimentQueryRepository(JdbcTemplate jdbcTemplate) {
    this.jdbcTemplate = jdbcTemplate;
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
