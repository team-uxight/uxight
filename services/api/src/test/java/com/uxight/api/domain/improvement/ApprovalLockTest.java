package com.uxight.api.domain.improvement;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.catchThrowableOfType;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.Mockito.when;

import com.uxight.api.common.ApiException;
import com.uxight.api.common.ErrorCode;
import com.uxight.api.domain.run.AgentClient;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.transaction.support.TransactionTemplate;

import java.time.Duration;
import java.util.Optional;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;

/**
 * 승인 버튼 연타(같은 회차의 개선안 두 개를 동시에 승인)에도 다음 회차가 하나만 생기는지 — 프로젝트 행 잠금으로 차례로 처리되는지 본다.
 * 두 트랜잭션이 실제로 동시에 돌아야 하므로 테스트 트랜잭션(롤백)을 쓰지 않고, 만든 행은 끝나고 지운다.
 */
@SpringBootTest
class ApprovalLockTest {

  private static final Duration HOLD = Duration.ofMillis(1500);

  @Autowired
  private ImprovementService improvementService;

  @Autowired
  private TransactionTemplate transactionTemplate;

  @Autowired
  private JdbcTemplate jdbcTemplate;

  @MockitoBean
  private AgentClient agentClient;

  private Long userId;
  private Long projectId;
  private Long runId;
  private Long option1;
  private Long option2;

  @BeforeEach
  void setUp() {
    when(agentClient.dispatch(anyLong())).thenReturn(CompletableFuture.completedFuture(Optional.empty()));
    String email = "approval-lock-" + System.nanoTime() + "@uxight.com";
    jdbcTemplate.update("INSERT INTO users (email, password_hash, auth_provider, name, role, is_active) "
        + "VALUES (?, 'hash', 'local', '잠금', 'researcher', TRUE)", email);
    userId = jdbcTemplate.queryForObject("SELECT user_id FROM users WHERE email = ?", Long.class, email);
    jdbcTemplate.update("INSERT INTO projects (user_id, title, target_url, allowed_domains) "
        + "VALUES (?, '승인 잠금', 'https://a.example.com', JSON_ARRAY('a.example.com'))", userId);
    projectId = jdbcTemplate.queryForObject("SELECT project_id FROM projects WHERE user_id = ?", Long.class, userId);
    jdbcTemplate.update("INSERT INTO tasks (project_id, goal, success_rule, success_url) "
        + "VALUES (?, '구매', 'rule', 'https://a.example.com/done')", projectId);
    Long taskId = jdbcTemplate.queryForObject("SELECT task_id FROM tasks WHERE project_id = ?", Long.class, projectId);
    jdbcTemplate.update("INSERT INTO runs (project_id, task_id, mode, loop_max, target_url_snapshot, allowed_domains_snapshot, "
        + "task_snapshot, policy_snapshot, persona_snapshot, status) "
        + "VALUES (?, ?, 'loop', 3, 'https://a.example.com', JSON_ARRAY(), JSON_OBJECT(), JSON_OBJECT(), JSON_ARRAY(), 'done')",
        projectId, taskId);
    runId = jdbcTemplate.queryForObject("SELECT run_id FROM runs WHERE task_id = ?", Long.class, taskId);
    jdbcTemplate.update("UPDATE runs SET first_run_id = run_id WHERE run_id = ?", runId);
    option1 = insertImprovement(1);
    option2 = insertImprovement(2);
  }

  @AfterEach
  void tearDown() {
    jdbcTemplate.update("DELETE FROM audit_log WHERE actor = ?", "user:" + userId);
    jdbcTemplate.update("DELETE FROM approvals WHERE user_id = ?", userId);
    jdbcTemplate.update("DELETE FROM runs WHERE parent_run_id = ?", runId);
    jdbcTemplate.update("DELETE FROM improvements WHERE run_id = ?", runId);
    jdbcTemplate.update("UPDATE runs SET first_run_id = NULL WHERE run_id = ?", runId);   // 최초 회차는 자기 자신을 가리킨다
    jdbcTemplate.update("DELETE FROM runs WHERE run_id = ?", runId);
    jdbcTemplate.update("DELETE FROM tasks WHERE project_id = ?", projectId);
    jdbcTemplate.update("DELETE FROM projects WHERE project_id = ?", projectId);
    jdbcTemplate.update("DELETE FROM users WHERE user_id = ?", userId);
  }

  @Test
  void twoConcurrentApprovals_createOneNextRound_secondWaitsAndGetsConflict() throws Exception {
    CountDownLatch decided = new CountDownLatch(1);

    // 1안 승인 — 프로젝트 행 잠금을 쥔 채 잠시 뒤 커밋한다
    CompletableFuture<Void> first = CompletableFuture.runAsync(() -> transactionTemplate.executeWithoutResult(tx -> {
      improvementService.decide(userId, runId, new ApprovalCreateRequest(option1, "approve", null));
      decided.countDown();
      sleep(HOLD);
    }));
    assertThat(decided.await(10, TimeUnit.SECONDS)).isTrue();

    // 잠금이 없으면 2안 승인도 "아직 승인된 개선안 없음"을 보고 통과해 다음 회차가 두 개 생긴다
    long start = System.nanoTime();
    ApiException e = catchThrowableOfType(ApiException.class,
        () -> improvementService.decide(userId, runId, new ApprovalCreateRequest(option2, "approve", null)));
    Duration waited = Duration.ofNanos(System.nanoTime() - start);
    first.get(10, TimeUnit.SECONDS);

    assertThat(e).isNotNull();
    assertThat(e.errorCode()).isEqualTo(ErrorCode.NOT_DECIDABLE);
    assertThat(waited).isGreaterThan(HOLD.minusMillis(500));   // 앞 승인이 커밋될 때까지 기다렸다
    assertThat(jdbcTemplate.queryForObject("SELECT COUNT(*) FROM runs WHERE parent_run_id = ?", Integer.class, runId))
        .isEqualTo(1);
  }

  private Long insertImprovement(int optionNo) {
    jdbcTemplate.update("INSERT INTO improvements (run_id, finding_ids, option_no, patch_kind, patch) "
        + "VALUES (?, JSON_ARRAY(), ?, 'relabel', JSON_OBJECT())", runId, optionNo);
    return jdbcTemplate.queryForObject("SELECT improvement_id FROM improvements WHERE run_id = ? AND option_no = ?",
        Long.class, runId, optionNo);
  }

  private static void sleep(Duration duration) {
    try {
      Thread.sleep(duration);
    } catch (InterruptedException e) {
      Thread.currentThread().interrupt();
      throw new IllegalStateException(e);
    }
  }
}
