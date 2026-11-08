package com.uxight.api.repository.user;

import com.uxight.api.domain.user.AdminUserQueryRepository;
import com.uxight.api.domain.user.AdminUserSummary;
import com.uxight.api.domain.user.AuthProvider;
import com.uxight.api.domain.user.Role;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

import java.time.LocalDateTime;
import java.util.List;

@Repository
public class JdbcTemplateAdminUserQueryRepository implements AdminUserQueryRepository {

  // user_id 는 가입 순으로 늘어난다 — 같은 시각에 가입한 계정도 순서가 흔들리지 않게 created_at 대신 쓴다.
  // 누적 비용은 사용량과 같은 규칙: AI 모듈이 스텝마다 누적한 runs.cost_usd 의 합으로, 실패 · 취소 · 진행 중 회차와
  // 삭제된 프로젝트의 회차도 센다(이미 쓴 비용이다). 회차 · 프로젝트가 없는 계정은 0.
  private static final String USERS_SQL = """
      SELECT u.user_id, u.email, u.name, u.role, u.auth_provider, u.is_active, u.created_at, u.last_login_at,
             COALESCE(c.cost_usd, 0) AS total_cost_usd
        FROM users u
        LEFT JOIN (SELECT p.user_id, SUM(r.cost_usd) AS cost_usd
                     FROM runs r
                     JOIN projects p ON p.project_id = r.project_id
                    GROUP BY p.user_id) c ON c.user_id = u.user_id
       ORDER BY u.user_id DESC
       LIMIT ? OFFSET ?
      """;

  private final JdbcTemplate jdbcTemplate;

  @Autowired
  public JdbcTemplateAdminUserQueryRepository(JdbcTemplate jdbcTemplate) {
    this.jdbcTemplate = jdbcTemplate;
  }

  @Override
  public List<AdminUserSummary> findUsers(long offset, int limit) {
    return jdbcTemplate.query(USERS_SQL, (rs, rowNum) -> new AdminUserSummary(
            rs.getLong("user_id"),
            rs.getString("email"),
            rs.getString("name"),
            Role.valueOf(rs.getString("role")),
            AuthProvider.valueOf(rs.getString("auth_provider")),
            rs.getBoolean("is_active"),
            rs.getObject("created_at", LocalDateTime.class),
            rs.getObject("last_login_at", LocalDateTime.class),
            rs.getBigDecimal("total_cost_usd")),
        limit, offset);
  }

  @Override
  public long countUsers() {
    return jdbcTemplate.queryForObject("SELECT COUNT(*) FROM users", Long.class);
  }
}
