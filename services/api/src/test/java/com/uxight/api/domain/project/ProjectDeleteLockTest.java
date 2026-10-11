package com.uxight.api.domain.project;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.catchThrowableOfType;

import com.uxight.api.common.ApiException;
import com.uxight.api.common.ErrorCode;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.transaction.support.TransactionTemplate;

import java.time.Duration;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;

/**
 * 프로젝트 삭제가 프로젝트 행 잠금으로 실험 요청과 차례로 처리되는지 본다.
 * 두 트랜잭션이 실제로 동시에 돌아야 하므로 테스트 트랜잭션(롤백)을 쓰지 않고, 만든 행은 끝나고 지운다.
 */
@SpringBootTest
class ProjectDeleteLockTest {

  private static final Duration HOLD = Duration.ofMillis(1500);

  @Autowired
  private ProjectService projectService;

  @Autowired
  private ProjectRepository projectRepository;

  @Autowired
  private TransactionTemplate transactionTemplate;

  @Autowired
  private JdbcTemplate jdbcTemplate;

  private Long userId;
  private Long projectId;

  @BeforeEach
  void setUp() {
    String email = "lock-test-" + System.nanoTime() + "@uxight.com";
    jdbcTemplate.update("INSERT INTO users (email, password_hash, auth_provider, name, role, is_active) "
        + "VALUES (?, 'hash', 'local', '잠금', 'researcher', TRUE)", email);
    userId = jdbcTemplate.queryForObject("SELECT user_id FROM users WHERE email = ?", Long.class, email);
    jdbcTemplate.update("INSERT INTO projects (user_id, title, target_url, allowed_domains) "
        + "VALUES (?, '잠금', 'https://a.example.com', JSON_ARRAY('a.example.com'))", userId);
    projectId = jdbcTemplate.queryForObject("SELECT project_id FROM projects WHERE user_id = ?", Long.class, userId);
  }

  @AfterEach
  void tearDown() {
    jdbcTemplate.update("DELETE FROM runs WHERE project_id = ?", projectId);
    jdbcTemplate.update("DELETE FROM tasks WHERE project_id = ?", projectId);
    jdbcTemplate.update("DELETE FROM projects WHERE project_id = ?", projectId);
    jdbcTemplate.update("DELETE FROM users WHERE user_id = ?", userId);
  }

  @Test
  void delete_waitsForLockHolder_andSeesExperimentCreatedMeanwhile() throws Exception {
    CountDownLatch locked = new CountDownLatch(1);

    // 실험 요청 대역: 프로젝트 행을 잠근 채 진행 중인 회차를 만들고, 잠시 뒤 커밋한다
    CompletableFuture<Void> experiment = CompletableFuture.runAsync(() -> transactionTemplate.executeWithoutResult(tx -> {
      projectRepository.findForUpdate(projectId, userId).orElseThrow();
      locked.countDown();
      sleep(HOLD);
      insertQueuedRun();
    }));
    assertThat(locked.await(10, TimeUnit.SECONDS)).isTrue();

    // 잠금이 없으면 삭제는 회차가 커밋되기 전에 "진행 중인 실험 없음"으로 판단해 성공한다
    long start = System.nanoTime();
    ApiException e = catchThrowableOfType(ApiException.class, () -> projectService.deleteProject(userId, projectId));
    Duration waited = Duration.ofNanos(System.nanoTime() - start);
    experiment.get(10, TimeUnit.SECONDS);

    assertThat(e).isNotNull();
    assertThat(e.errorCode()).isEqualTo(ErrorCode.EXPERIMENT_IN_PROGRESS);
    assertThat(waited).isGreaterThan(HOLD.minusMillis(500));   // 잠금이 풀릴 때까지 기다렸다
    assertThat(jdbcTemplate.queryForObject("SELECT deleted_at FROM projects WHERE project_id = ?", String.class,
        projectId)).isNull();
  }

  private void insertQueuedRun() {
    jdbcTemplate.update("INSERT INTO tasks (project_id, goal, success_rule, success_url) "
        + "VALUES (?, '구매', 'rule', 'https://a.example.com/done')", projectId);
    Long taskId = jdbcTemplate.queryForObject("SELECT LAST_INSERT_ID()", Long.class);
    jdbcTemplate.update("INSERT INTO runs (project_id, task_id, mode, target_url_snapshot, allowed_domains_snapshot, "
        + "task_snapshot, policy_snapshot, persona_snapshot, status) "
        + "VALUES (?, ?, 'diagnose', 'https://a.example.com', JSON_ARRAY(), JSON_OBJECT(), JSON_OBJECT(), JSON_ARRAY(), "
        + "'queued')", projectId, taskId);
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
