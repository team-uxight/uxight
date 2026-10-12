package com.uxight.api.domain.run;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.transaction.annotation.Transactional;

import java.time.Duration;
import java.util.Optional;
import java.util.concurrent.CompletableFuture;

/**
 * queued 로 갇힌 회차 재전송 (design-decision 4.6). 주기 작업은 테스트에서 꺼 두고 RunService 를 직접 부른다.
 * AI 모듈 호출은 대역 — 즉시 완료되므로 dispatch_state 기록까지 테스트 스레드에서 끝난다. 실제 MySQL, 테스트마다 롤백.
 */
@SpringBootTest
@Transactional
class RunRedispatchTest {

  private static final Duration STALE_AFTER = Duration.ofSeconds(30);

  @Autowired
  private RunService runService;

  @Autowired
  private JdbcTemplate jdbcTemplate;

  @MockitoBean
  private AgentClient agentClient;

  private Long projectId;
  private Long taskId;

  @BeforeEach
  void setUp() {
    jdbcTemplate.update("INSERT INTO users (email, password_hash, auth_provider, name, role, is_active) "
        + "VALUES ('redispatch@uxight.com', 'hash', 'local', '재전송', 'researcher', TRUE)");
    Long userId = jdbcTemplate.queryForObject("SELECT LAST_INSERT_ID()", Long.class);
    jdbcTemplate.update("INSERT INTO projects (user_id, title, target_url, allowed_domains) "
        + "VALUES (?, 'p', 'https://a.example.com', JSON_ARRAY('a.example.com'))", userId);
    projectId = jdbcTemplate.queryForObject("SELECT LAST_INSERT_ID()", Long.class);
    jdbcTemplate.update("INSERT INTO tasks (project_id, goal, success_rule, success_url) "
        + "VALUES (?, 'g', 'r', 'https://a.example.com/done')", projectId);
    taskId = jdbcTemplate.queryForObject("SELECT LAST_INSERT_ID()", Long.class);
    // 다른 테스트 · 개발 DB 에 남은 queued 회차가 섞이지 않게 이 테스트가 만든 회차만 보도록 기존 것을 잠시 치운다(롤백된다)
    jdbcTemplate.update("UPDATE runs SET status = 'failed' WHERE status = 'queued'");
    when(agentClient.dispatch(anyLong())).thenReturn(CompletableFuture.completedFuture(Optional.of(DispatchState.sent)));
  }

  @Test
  void redispatch_sendsOnlyQueuedRunsOlderThanThreshold_includingCancelRequested() {
    Long staleQueued = insertRun("queued", 60, false);
    Long staleCancelRequested = insertRun("queued", 60, true);
    Long freshQueued = insertRun("queued", 5, false);        // 방금 만든 회차 — 첫 POST /runs 가 아직 진행 중일 수 있다
    Long staleAccepted = insertRun("accepted", 60, false);   // 이미 접수됨
    Long staleDone = insertRun("done", 60, false);

    int sent = runService.redispatchStaleQueuedRuns(STALE_AFTER);

    assertThat(sent).isEqualTo(2);
    verify(agentClient).dispatch(staleQueued);
    verify(agentClient).dispatch(staleCancelRequested);
    verify(agentClient, never()).dispatch(freshQueued);
    verify(agentClient, never()).dispatch(staleAccepted);
    verify(agentClient, never()).dispatch(staleDone);
    // 결과는 dispatch_state 에만 기록하고 status 는 그대로 둔다
    assertThat(jdbcTemplate.queryForMap("SELECT status, dispatch_state FROM runs WHERE run_id = ?", staleQueued))
        .containsEntry("status", "queued")
        .containsEntry("dispatch_state", "sent");
  }

  @Test
  void redispatch_whenAgentAlreadyAccepted_leavesDispatchStateUntouched() {
    // 200(이미 받은 회차) — 첫 전송 때 기록한 값을 그대로 둔다
    when(agentClient.dispatch(anyLong())).thenReturn(CompletableFuture.completedFuture(Optional.empty()));
    Long run = insertRun("queued", 60, false);
    jdbcTemplate.update("UPDATE runs SET dispatch_state = 'timeout' WHERE run_id = ?", run);

    runService.redispatchStaleQueuedRuns(STALE_AFTER);

    assertThat(jdbcTemplate.queryForObject("SELECT dispatch_state FROM runs WHERE run_id = ?", String.class, run))
        .isEqualTo("timeout");
  }

  @Test
  void redispatch_withNothingStale_sendsNothing() {
    insertRun("queued", 5, false);

    assertThat(runService.redispatchStaleQueuedRuns(STALE_AFTER)).isZero();
    verify(agentClient, never()).dispatch(anyLong());
  }

  /** created_at 을 DB 시계 기준 secondsAgo 초 전으로 둔 회차. */
  private Long insertRun(String status, int secondsAgo, boolean cancelRequested) {
    jdbcTemplate.update("INSERT INTO runs (project_id, task_id, mode, target_url_snapshot, allowed_domains_snapshot, "
        + "task_snapshot, policy_snapshot, persona_snapshot, status, cancel_requested, created_at) "
        + "VALUES (?, ?, 'diagnose', 'https://a.example.com', JSON_ARRAY(), JSON_OBJECT(), JSON_OBJECT(), JSON_ARRAY(), "
        + "?, ?, NOW() - INTERVAL ? SECOND)", projectId, taskId, status, cancelRequested, secondsAgo);
    return jdbcTemplate.queryForObject("SELECT LAST_INSERT_ID()", Long.class);
  }
}
