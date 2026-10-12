package com.uxight.api.domain.run;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.when;

import com.uxight.api.common.ApiException;
import com.uxight.api.common.ErrorCode;
import com.uxight.api.domain.project.ProjectRepository;
import com.uxight.api.domain.task.SuccessRuleClient;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.transaction.support.TransactionTemplate;

import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.CyclicBarrier;
import java.util.concurrent.TimeUnit;

/**
 * 같은 프로젝트에 실험 요청이 동시에 들어와도 진행 중인 실험은 하나만 생기는지 본다 (design-decision 5.2 · 5.3).
 * 두 요청 모두 잠금 없는 사전 확인을 통과한 뒤, 성공 기준을 받는 시점을 맞춰 동시에 트랜잭션에 들어가게 한다.
 * 두 트랜잭션이 실제로 동시에 돌아야 하므로 테스트 트랜잭션(롤백)을 쓰지 않고, 만든 행은 끝나고 지운다.
 */
@SpringBootTest
class RunConcurrencyTest {

  @Autowired
  private RunService runService;

  @Autowired
  private JdbcTemplate jdbcTemplate;

  @Autowired
  private ProjectRepository projectRepository;

  @Autowired
  private TransactionTemplate transactionTemplate;

  @MockitoBean
  private SuccessRuleClient successRuleClient;

  @MockitoBean
  private AgentClient agentClient;

  private Long userId;
  private Long projectId;
  private Long personaId;

  @BeforeEach
  void setUp() {
    String email = "concurrency-" + System.nanoTime() + "@uxight.com";
    jdbcTemplate.update("INSERT INTO users (email, password_hash, auth_provider, name, role, is_active) "
        + "VALUES (?, 'hash', 'local', '동시', 'researcher', TRUE)", email);
    userId = jdbcTemplate.queryForObject("SELECT user_id FROM users WHERE email = ?", Long.class, email);
    jdbcTemplate.update("INSERT INTO projects (user_id, title, target_url, allowed_domains) "
        + "VALUES (?, '동시', 'https://a.example.com', JSON_ARRAY('a.example.com'))", userId);
    projectId = jdbcTemplate.queryForObject("SELECT project_id FROM projects WHERE user_id = ?", Long.class, userId);
    jdbcTemplate.update("INSERT INTO personas (user_id, name, profile) VALUES (?, 'p', JSON_OBJECT('webSkill', 'low'))",
        userId);
    personaId = jdbcTemplate.queryForObject("SELECT persona_id FROM personas WHERE user_id = ?", Long.class, userId);
    when(agentClient.dispatch(anyLong())).thenReturn(CompletableFuture.completedFuture(Optional.empty()));
  }

  @AfterEach
  void tearDown() {
    jdbcTemplate.update("UPDATE runs SET first_run_id = NULL WHERE project_id = ?", projectId);
    jdbcTemplate.update("DELETE FROM runs WHERE project_id = ?", projectId);
    jdbcTemplate.update("DELETE FROM tasks WHERE project_id = ?", projectId);
    jdbcTemplate.update("DELETE FROM personas WHERE user_id = ?", userId);
    jdbcTemplate.update("DELETE FROM projects WHERE project_id = ?", projectId);
    jdbcTemplate.update("DELETE FROM users WHERE user_id = ?", userId);
  }

  @Test
  void cancel_waitsForProjectLock_thenRecordsOnLastRound() throws Exception {
    when(successRuleClient.createSuccessRule(anyString(), anyString(), anyString())).thenReturn("rule");
    Long firstRunId = runService.createExperiment(userId, projectId, new ExperimentCreateRequest(
        "구매", "https://a.example.com/done", List.of(personaId), "diagnose", null));

    // 다음 회차 승인 대역: 프로젝트 행을 잠근 채 잠시 붙잡는다 — 취소는 그동안 기다렸다가 잠금이 풀린 뒤 마지막 회차를 다시 읽는다
    CountDownLatch locked = new CountDownLatch(1);
    CompletableFuture<Void> holder = CompletableFuture.runAsync(() -> transactionTemplate.executeWithoutResult(tx -> {
      projectRepository.findForUpdate(projectId, userId).orElseThrow();
      locked.countDown();
      sleep(Duration.ofMillis(1500));
    }));
    assertThat(locked.await(10, TimeUnit.SECONDS)).isTrue();

    long start = System.nanoTime();
    runService.cancelExperiment(userId, firstRunId);
    Duration waited = Duration.ofNanos(System.nanoTime() - start);
    holder.get(10, TimeUnit.SECONDS);

    assertThat(waited).isGreaterThan(Duration.ofMillis(1000));   // 잠금이 풀릴 때까지 기다렸다
    assertThat(jdbcTemplate.queryForObject("SELECT cancel_requested FROM runs WHERE run_id = ?", Boolean.class,
        firstRunId)).isTrue();
  }

  @Test
  void concurrentRequests_createOnlyOneExperiment() throws Exception {
    // 두 요청이 모두 성공 기준 생성(트랜잭션 밖)까지 온 뒤에야 함께 다음 단계로 간다
    CyclicBarrier bothPassedPreCheck = new CyclicBarrier(2);
    when(successRuleClient.createSuccessRule(anyString(), anyString(), anyString())).thenAnswer(invocation -> {
      bothPassedPreCheck.await(10, TimeUnit.SECONDS);
      return "rule";
    });

    List<CompletableFuture<Object>> requests = new ArrayList<>();
    for (int i = 0; i < 2; i++) {
      requests.add(CompletableFuture.supplyAsync(() -> {
        try {
          return runService.createExperiment(userId, projectId, new ExperimentCreateRequest(
              "구매", "https://a.example.com/done", List.of(personaId), "diagnose", null));
        } catch (ApiException e) {
          return e.errorCode();
        }
      }));
    }
    List<Object> results = new ArrayList<>();
    for (CompletableFuture<Object> request : requests) {
      results.add(request.get(30, TimeUnit.SECONDS));
    }

    // 잠금 · 재확인이 없으면 둘 다 회차를 만든다
    assertThat(results).filteredOn(Long.class::isInstance).hasSize(1);
    assertThat(results).filteredOn(ErrorCode.EXPERIMENT_IN_PROGRESS::equals).hasSize(1);
    assertThat(jdbcTemplate.queryForObject("SELECT COUNT(*) FROM runs WHERE project_id = ?", Integer.class, projectId))
        .isEqualTo(1);
    assertThat(jdbcTemplate.queryForObject("SELECT COUNT(*) FROM tasks WHERE project_id = ?", Integer.class, projectId))
        .isEqualTo(1);   // 거절된 쪽의 Task 는 롤백됐다
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
