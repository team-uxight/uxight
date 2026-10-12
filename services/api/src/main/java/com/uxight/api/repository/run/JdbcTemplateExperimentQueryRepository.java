package com.uxight.api.repository.run;

import com.uxight.api.domain.run.ExperimentFilter;
import com.uxight.api.domain.run.ExperimentQueryRepository;
import com.uxight.api.domain.run.ExperimentStats;
import com.uxight.api.domain.run.ExperimentSummary;
import com.uxight.api.domain.run.RoundSummary;
import com.uxight.api.domain.run.RunMetrics;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

import java.time.LocalDateTime;
import java.time.OffsetDateTime;
import java.time.ZoneId;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;

/** 실험 목록 · 건수 집계 SQL. 회차의 저장 · 변경은 RunRepository(JPA) 가 한다. */
@Repository
public class JdbcTemplateExperimentQueryRepository implements ExperimentQueryRepository {

  private static final ExperimentSummaryRowMapper EXPERIMENT_ROW_MAPPER = new ExperimentSummaryRowMapper();

  // DB 의 DATETIME 은 KST 로 쌓인다(compose MySQL --default-time-zone=+09:00). 시각 조건은 이 시간대로 바꿔 비교한다.
  private static final ZoneId DB_ZONE = ZoneId.of("Asia/Seoul");

  // running 인데 heartbeat_at 이 이 시간보다 오래되면 stale — AI 모듈이 회차를 놓쳤을 수 있다는 표시만, status 는 바꾸지 않는다 (GACA-104)
  private static final int STALE_AFTER_SECONDS = 60;

  // 실험 = first_run_id 가 같은 회차들. 한 줄은 실험의 마지막 회차(run_id 최대) 기준이다.
  // state · end_type 계산은 이 SQL 한 곳에만 둔다 (design-decision 2.6) — 목록 · 건수 · (다음 회차 승인)이 같은 정의를 쓴다.
  // 리서처는 자기가 삭제한 프로젝트의 실험을 보지 않는다(목록 · 건수 · 토큰 합 모두). 관리자 조회는 관리자 API 에서 따로 정한다.
  // agent_unreachable: 마지막 회차가 queued 인데 POST /runs 가 닿지 않았다(unreachable · timeout) — 웹 배너용. status 를 함께 봐야
  //   timeout 뒤 AI 모듈이 실제로 받아 accepted 가 된 회차에 배너가 뜨지 않는다. 재전송이 닿으면 sent 가 되어 사라진다.
  // state 는 겹치지 않는 네 분류다. 진행 중은 취소 요청을 뺀 것이라 실험 요청의 409(진행 중인 실험) 범위와 다르다.
  // TODO(승인): improvements · approvals 도입 때 state 에 awaiting_approval 을 넣는다 — 마지막 회차가 done 이고
  //   취소 요청이 없으며 다음 회차 승인 가능 조건(design-decision 2.2)을 충족하는 개선안이 있으면 awaiting_approval,
  //   아니면 completed. 개선안을 전부 반려해 끝난 실험의 완료 시각(finished_at)은 마지막 반려 시각으로 바꾼다.
  //   지금은 done 이 모두 completed 다.
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
             COALESCE(r.status = 'queued' AND r.dispatch_state IN ('unreachable', 'timeout'), false) AS agent_unreachable,
             f.status = 'done' AS has_result,
             p.title AS project_title,
             t.goal AS task_goal,
             JSON_LENGTH(r.persona_snapshot) AS persona_count,
             (SELECT SUM(TIMESTAMPDIFF(SECOND, COALESCE(x.started_at, x.created_at), COALESCE(x.finished_at, NOW())))
                FROM runs x WHERE x.first_run_id = r.first_run_id) AS elapsed_seconds,
             (SELECT COALESCE(SUM(x.tokens), 0) FROM runs x WHERE x.first_run_id = r.first_run_id) AS tokens,
             r.finished_at,
             f.created_at
        FROM runs r
        JOIN runs f ON f.run_id = r.first_run_id
        JOIN projects p ON p.project_id = r.project_id
        JOIN tasks t ON t.task_id = r.task_id
       WHERE p.user_id = ?
         AND p.deleted_at IS NULL
         AND r.run_id = (SELECT MAX(x.run_id) FROM runs x WHERE x.first_run_id = r.first_run_id)
      """.formatted(STALE_AFTER_SECONDS);

  // 목록 · 건수 조건. ? 순서: 위 SQL 의 userId → state × 2 → keyword × 3 → finishedFrom × 2
  private static final String FILTER = """
       WHERE (? IS NULL OR e.state = ?)
         AND (? IS NULL OR e.project_title LIKE ? ESCAPE '!' OR e.task_goal LIKE ? ESCAPE '!')
         AND (? IS NULL OR e.finished_at >= ?)
      """;

  // ? 순서: thisWeekFrom → 위 SQL 의 userId (SELECT 절이 FROM 절보다 앞에 온다)
  private static final String STATS_SQL = """
      SELECT COUNT(*) AS total_count,
             COALESCE(SUM(e.state = 'in_progress'), 0) AS in_progress_count,
             COALESCE(SUM(e.state = 'completed'), 0) AS completed_count,
             COALESCE(SUM(e.state = 'completed' AND e.finished_at >= ?), 0) AS completed_this_week_count,
             COALESCE(SUM(e.state = 'awaiting_approval'), 0) AS awaiting_approval_count,
             COALESCE(SUM(e.tokens), 0) AS total_tokens
        FROM (%s) e
      """.formatted(EXPERIMENTS_SQL);

  // 실험의 회차 — 본인 · 삭제하지 않은 프로젝트만(실험 목록과 같은 규칙). 몇 번째 회차인지는 runId 순번이다.
  // 다음 회차는 이전 회차가 끝나고 승인된 뒤에만 생기므로 run_id 순서가 회차 순서와 같다.
  // 지표는 Python 이 회차 종료 때 확정해 run_metrics 에 쓴다 — 아직 없으면 metric_run_id 가 NULL 이다.
  private static final String ROUNDS_SQL = """
      SELECT r.run_id, ROW_NUMBER() OVER (ORDER BY r.run_id) AS round_no, r.status, r.improvement_id,
             r.created_at, r.finished_at,
             m.run_id AS metric_run_id, m.success_rate, m.avg_steps, m.avg_backtracks, m.avg_seconds, m.tokens, m.cost_usd
        FROM runs r
        JOIN projects p ON p.project_id = r.project_id
        LEFT JOIN run_metrics m ON m.run_id = r.run_id
       WHERE r.first_run_id = ?
         AND p.user_id = ?
         AND p.deleted_at IS NULL
       ORDER BY r.run_id
      """;

  private final JdbcTemplate jdbcTemplate;

  @Autowired
  public JdbcTemplateExperimentQueryRepository(JdbcTemplate jdbcTemplate) {
    this.jdbcTemplate = jdbcTemplate;
  }

  @Override
  public List<ExperimentSummary> findExperiments(Long userId, ExperimentFilter filter, int offset, int limit) {
    List<Object> args = filterArgs(userId, filter);
    args.add(limit);
    args.add(offset);
    return jdbcTemplate.query(
        "SELECT * FROM (" + EXPERIMENTS_SQL + ") e" + FILTER + " ORDER BY e.first_run_id DESC LIMIT ? OFFSET ?",
        EXPERIMENT_ROW_MAPPER, args.toArray());
  }

  @Override
  public long countExperiments(Long userId, ExperimentFilter filter) {
    return jdbcTemplate.queryForObject("SELECT COUNT(*) FROM (" + EXPERIMENTS_SQL + ") e" + FILTER,
        Long.class, filterArgs(userId, filter).toArray());
  }

  @Override
  public ExperimentStats findStats(Long userId, OffsetDateTime thisWeekFrom) {
    return jdbcTemplate.queryForObject(STATS_SQL, (rs, rowNum) -> new ExperimentStats(
        rs.getLong("total_count"),
        rs.getLong("in_progress_count"),
        rs.getLong("completed_count"),
        rs.getLong("completed_this_week_count"),
        rs.getLong("awaiting_approval_count"),
        rs.getLong("total_tokens"),
        thisWeekFrom), toDbTime(thisWeekFrom), userId);
  }

  @Override
  public Optional<ExperimentSummary> findExperiment(Long userId, Long firstRunId) {
    return jdbcTemplate.query("SELECT * FROM (" + EXPERIMENTS_SQL + ") e WHERE e.first_run_id = ?",
            EXPERIMENT_ROW_MAPPER, userId, firstRunId)
        .stream()
        .findFirst();
  }

  @Override
  public List<RoundSummary> findRounds(Long userId, Long firstRunId) {
    return jdbcTemplate.query(ROUNDS_SQL, (rs, rowNum) -> new RoundSummary(
        rs.getLong("run_id"),
        rs.getInt("round_no"),
        rs.getString("status"),
        rs.getObject("improvement_id", Long.class),
        rs.getObject("created_at", LocalDateTime.class),
        rs.getObject("finished_at", LocalDateTime.class),
        rs.getObject("metric_run_id") == null ? null : new RunMetrics(
            rs.getBigDecimal("success_rate"),
            rs.getBigDecimal("avg_steps"),
            rs.getBigDecimal("avg_backtracks"),
            rs.getBigDecimal("avg_seconds"),
            rs.getObject("tokens", Long.class),
            rs.getBigDecimal("cost_usd"))), firstRunId, userId);
  }

  private static List<Object> filterArgs(Long userId, ExperimentFilter filter) {
    String like = filter.keyword() == null ? null : "%" + escapeLike(filter.keyword()) + "%";
    LocalDateTime finishedFrom = filter.finishedFrom() == null ? null : toDbTime(filter.finishedFrom());
    List<Object> args = new ArrayList<>();
    args.add(userId);
    args.add(filter.state());
    args.add(filter.state());
    args.add(like);
    args.add(like);
    args.add(like);
    args.add(finishedFrom);
    args.add(finishedFrom);
    return args;
  }

  private static LocalDateTime toDbTime(OffsetDateTime time) {
    return time.atZoneSameInstant(DB_ZONE).toLocalDateTime();
  }

  // 검색어의 % · _ 를 와일드카드가 아니라 글자로 찾게 한다 (ESCAPE '!')
  private static String escapeLike(String keyword) {
    return keyword.replace("!", "!!").replace("%", "!%").replace("_", "!_");
  }
}
