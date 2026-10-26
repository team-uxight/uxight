package com.uxight.api.repository.usage;

import com.uxight.api.domain.usage.UsageDay;
import com.uxight.api.domain.usage.UsageQueryRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

import java.time.LocalDate;
import java.util.List;

@Repository
public class JdbcTemplateUsageQueryRepository implements UsageQueryRepository {

  // 회차를 요청한 시각(created_at, KST — MySQL 시간대 +09:00)의 날짜로 묶는다. 회차는 정책상 몇 분이라 자정을 넘기는 경우는 무시한다.
  // tokens · cost_usd 는 AI 모듈이 스텝마다 누적하는 값 — 실패 · 취소 · 진행 중 회차도 지금까지 쓴 만큼 들어간다.
  // 비용은 이미 쓴 것이라 삭제된 프로젝트의 회차도 센다.
  private static final String DAILY_SQL = """
      SELECT DATE(created_at)              AS day,
             COALESCE(SUM(cost_usd), 0)    AS cost_usd,
             COALESCE(SUM(tokens), 0)      AS tokens,
             COUNT(*)                      AS run_count
        FROM runs
       WHERE created_at >= ? AND created_at < ?
       GROUP BY DATE(created_at)
       ORDER BY day
      """;

  private final JdbcTemplate jdbcTemplate;

  @Autowired
  public JdbcTemplateUsageQueryRepository(JdbcTemplate jdbcTemplate) {
    this.jdbcTemplate = jdbcTemplate;
  }

  @Override
  public List<UsageDay> findDaily(LocalDate from, LocalDate to) {
    return jdbcTemplate.query(DAILY_SQL, (rs, rowNum) -> new UsageDay(
            rs.getDate("day").toLocalDate(),
            rs.getBigDecimal("cost_usd"),
            rs.getLong("tokens"),
            rs.getLong("run_count")),
        from.atStartOfDay(), to.plusDays(1).atStartOfDay());
  }
}
