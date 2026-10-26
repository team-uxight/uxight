package com.uxight.api.domain.user;

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
import java.util.List;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;

/**
 * 관리자 둘을 동시에 내려도 관리자가 0명이 되지 않는지 — 관리자 행 잠금으로 역할 변경이 차례로 처리되는지 본다.
 * 두 트랜잭션이 실제로 동시에 돌아야 하므로 테스트 트랜잭션(롤백)을 쓰지 않는다. seed 등 기존 관리자는 잠시 리서처로
 * 내렸다가 끝나고 되돌리고, 만든 행은 지운다.
 */
@SpringBootTest
class UserRoleLockTest {

  private static final Duration HOLD = Duration.ofMillis(1500);

  @Autowired
  private UserService userService;

  @Autowired
  private TransactionTemplate transactionTemplate;

  @Autowired
  private JdbcTemplate jdbcTemplate;

  private List<Long> existingAdmins;
  private Long adminA;
  private Long adminB;

  @BeforeEach
  void setUp() {
    existingAdmins = jdbcTemplate.queryForList("SELECT user_id FROM users WHERE role = 'admin'", Long.class);
    jdbcTemplate.update("UPDATE users SET role = 'researcher' WHERE role = 'admin'");
    adminA = insertAdmin("lock-admin-a-" + System.nanoTime() + "@uxight.com");
    adminB = insertAdmin("lock-admin-b-" + System.nanoTime() + "@uxight.com");
  }

  @AfterEach
  void tearDown() {
    jdbcTemplate.update("DELETE FROM audit_log WHERE actor IN (?, ?)", "user:" + adminA, "user:" + adminB);
    jdbcTemplate.update("DELETE FROM users WHERE user_id IN (?, ?)", adminA, adminB);
    for (Long id : existingAdmins) {
      jdbcTemplate.update("UPDATE users SET role = 'admin' WHERE user_id = ?", id);
    }
  }

  @Test
  void twoConcurrentDemotions_leaveOneAdmin_secondWaitsAndGetsLastAdminConflict() throws Exception {
    CountDownLatch changed = new CountDownLatch(1);

    // A 가 B 를 내리고, 잠금을 쥔 채 잠시 뒤 커밋한다
    CompletableFuture<Void> first = CompletableFuture.runAsync(() -> transactionTemplate.executeWithoutResult(tx -> {
      userService.changeRole(adminA, adminB, Role.researcher);
      changed.countDown();
      sleep(HOLD);
    }));
    assertThat(changed.await(10, TimeUnit.SECONDS)).isTrue();

    // 잠금이 없으면 A 자신을 내리는 요청도 "관리자 2명"을 보고 통과해 관리자가 0명이 된다
    long start = System.nanoTime();
    ApiException e = catchThrowableOfType(ApiException.class,
        () -> userService.changeRole(adminA, adminA, Role.researcher));
    Duration waited = Duration.ofNanos(System.nanoTime() - start);
    first.get(10, TimeUnit.SECONDS);

    assertThat(e).isNotNull();
    assertThat(e.errorCode()).isEqualTo(ErrorCode.LAST_ADMIN);
    assertThat(waited).isGreaterThan(HOLD.minusMillis(500));   // 앞 변경이 커밋될 때까지 기다렸다
    assertThat(jdbcTemplate.queryForList("SELECT user_id FROM users WHERE role = 'admin'", Long.class))
        .containsExactly(adminA);
  }

  private Long insertAdmin(String email) {
    jdbcTemplate.update("INSERT INTO users (email, password_hash, auth_provider, name, role, is_active) "
        + "VALUES (?, 'hash', 'local', '잠금', 'admin', TRUE)", email);
    return jdbcTemplate.queryForObject("SELECT user_id FROM users WHERE email = ?", Long.class, email);
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
