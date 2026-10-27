package com.uxight.api.repository.run;

import com.uxight.api.domain.run.AdminExperimentQueryRepository;
import com.uxight.api.domain.run.AdminExperimentSummary;
import com.uxight.api.domain.run.RunMode;
import com.uxight.api.domain.run.RunStatus;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

import java.time.LocalDateTime;
import java.util.List;

@Repository
public class JdbcTemplateAdminExperimentQueryRepository implements AdminExperimentQueryRepository {

  // 실험 = 최초 회차(first_run_id) 하나에 회차 여러 개. 한 줄은 실험의 마지막 회차(run_id 가 가장 큰 회차) 기준이다
  // (리서처 실험 목록과 같은 규칙). 운영자는 모든 사용자의 실험 · 삭제된 프로젝트의 실험도 본다.
  private static final String EXPERIMENTS_SQL = """
      SELECT f.run_id                      AS first_run_id,
             p.title                       AS project_title,
             p.deleted_at IS NOT NULL      AS project_deleted,
             u.email                       AS owner_email,
             t.goal                        AS task_goal,
             r.mode,
             (SELECT COUNT(*) FROM runs x WHERE x.first_run_id = r.first_run_id) AS round_count,
             r.status,
             f.created_at,
             r.finished_at
        FROM runs r
        JOIN runs f ON f.run_id = r.first_run_id
        JOIN projects p ON p.project_id = r.project_id
        JOIN users u ON u.user_id = p.user_id
        JOIN tasks t ON t.task_id = r.task_id
       WHERE r.run_id = (SELECT MAX(x.run_id) FROM runs x WHERE x.first_run_id = r.first_run_id)
       ORDER BY f.run_id DESC
       LIMIT ? OFFSET ?
      """;

  private final JdbcTemplate jdbcTemplate;

  @Autowired
  public JdbcTemplateAdminExperimentQueryRepository(JdbcTemplate jdbcTemplate) {
    this.jdbcTemplate = jdbcTemplate;
  }

  @Override
  public List<AdminExperimentSummary> findExperiments(int offset, int limit) {
    return jdbcTemplate.query(EXPERIMENTS_SQL, (rs, rowNum) -> new AdminExperimentSummary(
            rs.getLong("first_run_id"),
            rs.getString("project_title"),
            rs.getBoolean("project_deleted"),
            rs.getString("owner_email"),
            rs.getString("task_goal"),
            RunMode.valueOf(rs.getString("mode")),
            rs.getInt("round_count"),
            RunStatus.valueOf(rs.getString("status")),
            rs.getObject("created_at", LocalDateTime.class),
            rs.getObject("finished_at", LocalDateTime.class)),
        limit, offset);
  }

  @Override
  public long countExperiments() {
    // 최초 회차는 first_run_id 가 자기 자신이다
    return jdbcTemplate.queryForObject("SELECT COUNT(*) FROM runs WHERE run_id = first_run_id", Long.class);
  }
}
