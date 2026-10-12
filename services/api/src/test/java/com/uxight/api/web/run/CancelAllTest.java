package com.uxight.api.web.run;

import static org.assertj.core.api.Assertions.assertThat;
import static org.hamcrest.Matchers.hasSize;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.uxight.api.domain.user.JwtProvider;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.HttpHeaders;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.ResultActions;
import org.springframework.transaction.annotation.Transactional;

import java.util.Arrays;
import java.util.List;
import java.util.Map;

/**
 * 전체 실험 중단(POST /api/admin/runs/cancel-all) — 관리자만. 모든 프로젝트의 진행 중이고 취소 요청이 없는 회차에만 기록한다.
 * 실제 MySQL, 테스트마다 롤백. 회차의 status 는 Python 이 쓰는 값이라 SQL 로 넣는다.
 */
@SpringBootTest
@AutoConfigureMockMvc
@Transactional
class CancelAllTest {

  @Autowired
  private MockMvc mvc;

  @Autowired
  private JwtProvider jwtProvider;

  @Autowired
  private JdbcTemplate jdbcTemplate;

  @Autowired
  private ObjectMapper objectMapper;

  private Long adminId;

  @BeforeEach
  void setUp() {
    adminId = insertUser("cancel-all-admin@uxight.com", "admin");
    // 개발 DB 에 남은 진행 중 회차가 섞이지 않게 잠시 치운다(롤백된다)
    jdbcTemplate.update("UPDATE runs SET status = 'failed' WHERE status IN ('queued', 'accepted', 'running')");
  }

  @Test
  void cancelAll_recordsOnInProgressRunsOfAllProjects_only() throws Exception {
    Long a = insertProject(insertUser("cancel-all-a@uxight.com", "researcher"));
    Long b = insertProject(insertUser("cancel-all-b@uxight.com", "researcher"));
    Long queued = insertRun(a, "queued", false);
    Long accepted = insertRun(b, "accepted", false);
    Long running = insertRun(b, "running", false);
    Long alreadyRequested = insertRun(a, "running", true);   // 이미 취소 요청됨 — 다시 세지 않는다
    Long done = insertRun(a, "done", false);                 // 끝났거나 승인 대기 — 실행 자원을 쓰지 않는다
    Long failed = insertRun(b, "failed", false);
    Long cancelled = insertRun(b, "cancelled", false);

    cancelAll(adminId)
        .andExpect(status().isAccepted())
        .andExpect(jsonPath("$.*", hasSize(1)))
        .andExpect(jsonPath("$.cancelledCount").value(3));

    assertThat(cancelRequested(queued, accepted, running, alreadyRequested, done, failed, cancelled))
        .containsExactly(true, true, true, true, false, false, false);
    // status 는 바꾸지 않는다 — AI 모듈이 실제로 멈춘 뒤 cancelled 로 기록한다
    assertThat(jdbcTemplate.queryForList("SELECT status FROM runs WHERE run_id IN (?, ?, ?) ORDER BY run_id",
        String.class, queued, accepted, running)).containsExactly("queued", "accepted", "running");

    Map<String, Object> audit = lastAudit();
    assertThat(audit).containsEntry("action", "run.cancel_all").containsEntry("target", "runs");
    assertThat(objectMapper.readValue(audit.get("detail").toString(), new TypeReference<Map<String, Object>>() {}))
        .isEqualTo(Map.of("cancelledCount", 3,
            "runIds", List.of(queued.intValue(), accepted.intValue(), running.intValue())));
  }

  @Test
  void cancelAll_researcherSeesExperimentAsStoppedCancelling() throws Exception {
    Long researcher = insertUser("cancel-all-a@uxight.com", "researcher");
    Long run = insertRun(insertProject(researcher), "running", false);

    cancelAll(adminId).andExpect(status().isAccepted());

    mvc.perform(get("/api/runs").header(HttpHeaders.AUTHORIZATION, bearer(researcher)))
        .andExpect(jsonPath("$.content[0].firstRunId").value(run))
        .andExpect(jsonPath("$.content[0].state").value("stopped"))
        .andExpect(jsonPath("$.content[0].endType").value("cancelling"));
  }

  @Test
  void cancelAll_withNothingRunning_returnsZero_andStillRecordsAudit() throws Exception {
    cancelAll(adminId)
        .andExpect(status().isAccepted())
        .andExpect(jsonPath("$.cancelledCount").value(0));
    cancelAll(adminId).andExpect(jsonPath("$.cancelledCount").value(0));   // 두 번 눌러도 같다

    assertThat(jdbcTemplate.queryForObject("SELECT COUNT(*) FROM audit_log WHERE actor = ? AND action = 'run.cancel_all'",
        Integer.class, "user:" + adminId)).isEqualTo(2);
  }

  @Test
  void researcher_isForbidden_andNothingIsCancelled() throws Exception {
    Long researcher = insertUser("cancel-all-a@uxight.com", "researcher");
    Long run = insertRun(insertProject(researcher), "running", false);

    cancelAll(researcher)
        .andExpect(status().isForbidden())
        .andExpect(jsonPath("$.code").value("AUT-ERR-006"));
    assertThat(cancelRequested(run)).containsExactly(false);
  }

  @Test
  void withoutTokenOrByInactiveAdmin_isUnauthorized() throws Exception {
    mvc.perform(post("/api/admin/runs/cancel-all"))
        .andExpect(status().isUnauthorized())
        .andExpect(jsonPath("$.code").value("AUT-ERR-001"));

    jdbcTemplate.update("UPDATE users SET is_active = FALSE WHERE user_id = ?", adminId);
    cancelAll(adminId)
        .andExpect(status().isUnauthorized())
        .andExpect(jsonPath("$.code").value("AUT-ERR-005"));
  }

  private ResultActions cancelAll(Long userId) throws Exception {
    return mvc.perform(post("/api/admin/runs/cancel-all").header(HttpHeaders.AUTHORIZATION, bearer(userId)));
  }

  private String bearer(Long userId) {
    return "Bearer " + jwtProvider.createAccessToken(userId);
  }

  private List<Boolean> cancelRequested(Long... runIds) {
    return Arrays.stream(runIds)
        .map(id -> jdbcTemplate.queryForObject("SELECT cancel_requested FROM runs WHERE run_id = ?", Boolean.class, id))
        .toList();
  }

  private Map<String, Object> lastAudit() {
    return jdbcTemplate.queryForMap("SELECT action, target, detail FROM audit_log WHERE actor = ? "
        + "ORDER BY audit_log_id DESC LIMIT 1", "user:" + adminId);
  }

  private Long insertUser(String email, String role) {
    jdbcTemplate.update("INSERT INTO users (email, password_hash, auth_provider, name, role, is_active) "
        + "VALUES (?, 'hash', 'local', '중단', ?, TRUE)", email, role);
    return jdbcTemplate.queryForObject("SELECT user_id FROM users WHERE email = ?", Long.class, email);
  }

  private Long insertProject(Long ownerId) {
    jdbcTemplate.update("INSERT INTO projects (user_id, title, target_url, allowed_domains) "
        + "VALUES (?, 'p', 'https://a.example.com', JSON_ARRAY('a.example.com'))", ownerId);
    return jdbcTemplate.queryForObject("SELECT LAST_INSERT_ID()", Long.class);
  }

  /** 최초 회차 하나짜리 실험. */
  private Long insertRun(Long projectId, String status, boolean cancelRequested) {
    jdbcTemplate.update("INSERT INTO tasks (project_id, goal, success_rule, success_url) "
        + "VALUES (?, 'g', 'r', 'https://a.example.com/done')", projectId);
    Long taskId = jdbcTemplate.queryForObject("SELECT LAST_INSERT_ID()", Long.class);
    jdbcTemplate.update("INSERT INTO runs (project_id, task_id, mode, target_url_snapshot, allowed_domains_snapshot, "
        + "task_snapshot, policy_snapshot, persona_snapshot, status, cancel_requested) "
        + "VALUES (?, ?, 'diagnose', 'https://a.example.com', JSON_ARRAY(), JSON_OBJECT(), JSON_OBJECT(), JSON_ARRAY(), ?, ?)",
        projectId, taskId, status, cancelRequested);
    Long runId = jdbcTemplate.queryForObject("SELECT LAST_INSERT_ID()", Long.class);
    jdbcTemplate.update("UPDATE runs SET first_run_id = run_id WHERE run_id = ?", runId);
    return runId;
  }
}
