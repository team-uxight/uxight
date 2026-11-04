package com.uxight.api.web.improvement;

import static org.assertj.core.api.Assertions.assertThat;
import static org.hamcrest.Matchers.contains;
import static org.hamcrest.Matchers.hasSize;
import static org.hamcrest.Matchers.nullValue;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.uxight.api.domain.run.AgentClient;
import com.uxight.api.domain.user.JwtProvider;
import jakarta.persistence.EntityManager;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.ResultActions;
import org.springframework.test.web.servlet.request.MockHttpServletRequestBuilder;
import org.springframework.transaction.annotation.Transactional;

import java.util.Map;
import java.util.Optional;
import java.util.concurrent.CompletableFuture;

/**
 * 개선안 목록 · 상세 · 다음 회차 승인/반려 — 본인 프로젝트의 done 회차만. 승인 가능 조건은 design-decision 2.2.
 * 실제 MySQL, 테스트마다 롤백. 로컬 seed(R__seed_local_improvements — loop 실험, 개선안 3안)로 완료 기준을 보고,
 * 조건별 동작은 테스트가 넣은 회차로 본다. AI 모듈 호출(POST /runs)은 대역으로 바꾸고 불렸는지만 본다.
 */
@SpringBootTest
@AutoConfigureMockMvc
@Transactional
class ImprovementControllerTest {

  private static final long SEED_USER_ID = 1L;   // test@uxight.com (R__seed_local)

  @Autowired
  private MockMvc mvc;

  @Autowired
  private JwtProvider jwtProvider;

  @Autowired
  private JdbcTemplate jdbcTemplate;

  @Autowired
  private ObjectMapper objectMapper;

  @Autowired
  private EntityManager entityManager;

  @MockitoBean
  private AgentClient agentClient;

  private Long researcherId;
  private Long projectId;
  private Long personaId;

  @BeforeEach
  void setUp() {
    when(agentClient.dispatch(anyLong())).thenReturn(CompletableFuture.completedFuture(Optional.empty()));
    researcherId = insertUser("improvement-researcher@uxight.com");
    projectId = insertProject(researcherId);
    jdbcTemplate.update("INSERT INTO personas (user_id, name, profile) VALUES (?, '초보', JSON_OBJECT('webSkill', 'low'))",
        researcherId);
    personaId = jdbcTemplate.queryForObject("SELECT LAST_INSERT_ID()", Long.class);
  }

  // ───────── 완료 기준: seed 개선안으로 응답 모양 · 승인 → 다음 회차 queued ─────────

  @Test
  void seedRun_listAndDetail_inSpecShape_andAwaitingApproval() throws Exception {
    long seedRun = seedRunId();
    long option2 = improvementId(seedRun, 2);

    as(SEED_USER_ID, get("/api/runs/{runId}/improvements", seedRun))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.*", hasSize(2)))
        .andExpect(jsonPath("$.run.*", hasSize(5)))
        .andExpect(jsonPath("$.run.firstRunId").value(seedRun))
        .andExpect(jsonPath("$.run.round").value(1))
        .andExpect(jsonPath("$.run.projectTitle").value("[seed] 개선안 예시 쇼핑몰"))
        .andExpect(jsonPath("$.run.taskGoal").value("쿠폰을 적용해 결제 페이지까지 간다"))
        .andExpect(jsonPath("$.run.awaitingApproval").value(true))
        .andExpect(jsonPath("$.improvements", hasSize(3)))
        .andExpect(jsonPath("$.improvements[0].*", hasSize(5)))
        .andExpect(jsonPath("$.improvements[*].optionNo").value(contains(1, 2, 3)))
        .andExpect(jsonPath("$.improvements[*].patchKind").value(contains("relabel", "highlight", "help_text")))
        .andExpect(jsonPath("$.improvements[0].fixCost").value("low"))
        .andExpect(jsonPath("$.improvements[0].decision").value(nullValue()));

    as(SEED_USER_ID, get("/api/improvements/{improvementId}", option2))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.*", hasSize(11)))
        .andExpect(jsonPath("$.improvementId").value(option2))
        .andExpect(jsonPath("$.runId").value(seedRun))
        .andExpect(jsonPath("$.optionNo").value(2))
        .andExpect(jsonPath("$.patchKind").value("highlight"))
        .andExpect(jsonPath("$.patch.target").value("#coupon-input"))
        .andExpect(jsonPath("$.patch.style").value("primary"))
        .andExpect(jsonPath("$.rationale").isNotEmpty())
        .andExpect(jsonPath("$.expectedEffect").isNotEmpty())
        .andExpect(jsonPath("$.fixCost").value("low"))
        .andExpect(jsonPath("$.findings", hasSize(2)))
        .andExpect(jsonPath("$.findings[0].*", hasSize(4)))
        .andExpect(jsonPath("$.findings[*].taxonomy").value(contains("interaction_failure", "task_failure")))
        .andExpect(jsonPath("$.approval").value(nullValue()))
        .andExpect(jsonPath("$.awaitingApproval").value(true));
    // 진단 목록의 개선안 수도 실제 개수
    as(SEED_USER_ID, get("/api/runs/{runId}/findings", seedRun))
        .andExpect(jsonPath("$.run.improvementCount").value(3));
  }

  @Test
  void seedRun_approve_createsQueuedNextRound_copiesSnapshots_dispatches_andIsAudited() throws Exception {
    long seedRun = seedRunId();
    long option1 = improvementId(seedRun, 1);

    JsonNode body = body(decide(SEED_USER_ID, seedRun, option1, "approve", "  문구가 가장 확실해 보인다  ")
        .andExpect(status().isCreated())
        .andExpect(jsonPath("$.*", hasSize(2))));
    long approvalId = body.get("approvalId").asLong();
    long nextRun = body.get("runId").asLong();

    // 다음 회차 — queued, 직전 회차 · 실험 · 적용한 개선안, 스냅샷은 직전 회차 그대로
    Map<String, Object> next = jdbcTemplate.queryForMap("SELECT status, mode, loop_max, parent_run_id, first_run_id, "
        + "improvement_id, project_id, task_id, dispatch_state, cancel_requested FROM runs WHERE run_id = ?", nextRun);
    assertThat(next).containsEntry("status", "queued").containsEntry("mode", "loop").containsEntry("loop_max", 3)
        .containsEntry("parent_run_id", seedRun).containsEntry("first_run_id", seedRun)
        .containsEntry("improvement_id", option1).containsEntry("cancel_requested", false);
    assertThat(jdbcTemplate.queryForObject("SELECT COUNT(*) FROM runs n JOIN runs p ON p.run_id = n.parent_run_id "
        + "WHERE n.run_id = ? AND n.project_id = p.project_id AND n.task_id = p.task_id "
        + "AND n.target_url_snapshot = p.target_url_snapshot AND n.allowed_domains_snapshot = p.allowed_domains_snapshot "
        + "AND n.task_snapshot = p.task_snapshot AND n.policy_snapshot = p.policy_snapshot "
        + "AND n.persona_snapshot = p.persona_snapshot", Integer.class, nextRun)).isEqualTo(1);
    verify(agentClient).dispatch(nextRun);   // 실험 요청과 같은 경로로 AI 모듈을 부른다

    // 감사 로그 run.approve
    assertThat(jdbcTemplate.queryForMap("SELECT actor, action, target, JSON_EXTRACT(detail, '$.nextRunId') AS next_run, "
            + "JSON_UNQUOTE(JSON_EXTRACT(detail, '$.note')) AS note FROM audit_log ORDER BY audit_log_id DESC LIMIT 1"))
        .containsEntry("actor", "user:" + SEED_USER_ID).containsEntry("action", "run.approve")
        .containsEntry("target", "improvement:" + option1).containsEntry("note", "문구가 가장 확실해 보인다");

    entityManager.flush();
    entityManager.clear();   // 결정 시각(decided_at)은 DB 기본값 — 다시 읽게 한다
    // 실험은 2회차가 진행 중, 1회차는 더 이상 승인 대기가 아니다
    as(SEED_USER_ID, get("/api/runs").param("state", "in_progress"))
        .andExpect(jsonPath("$.content[?(@.firstRunId == " + seedRun + ")].round").value(contains(2)));
    as(SEED_USER_ID, get("/api/runs/{runId}/improvements", seedRun))
        .andExpect(jsonPath("$.run.awaitingApproval").value(false))
        .andExpect(jsonPath("$.improvements[*].decision").value(contains("approve", null, null)));
    as(SEED_USER_ID, get("/api/improvements/{improvementId}", option1))
        .andExpect(jsonPath("$.approval.*", hasSize(3)))
        .andExpect(jsonPath("$.approval.decision").value("approve"))
        .andExpect(jsonPath("$.approval.note").value("문구가 가장 확실해 보인다"))
        .andExpect(jsonPath("$.approval.decidedAt").isNotEmpty())
        .andExpect(jsonPath("$.awaitingApproval").value(false));
    // 한 회차에서 승인할 수 있는 개선안은 하나 — 나머지는 승인도 반려도 409
    decide(SEED_USER_ID, seedRun, improvementId(seedRun, 2), "reject", null)
        .andExpect(status().isConflict())
        .andExpect(jsonPath("$.code").value("IMP-ERR-002"));
    assertThat(approvalId).isPositive();
  }

  // ───────── 반려 ─────────

  @Test
  void reject_excludesOnlyThatOption_andAllRejectedCompletesExperimentAtLastRejectTime() throws Exception {
    long run = insertRun("loop", 3, "done", null);
    long option1 = insertImprovement(run, 1, "[]");
    long option2 = insertImprovement(run, 2, "[]");

    decide(researcherId, run, option1, "reject", "효과가 작다")
        .andExpect(status().isCreated())
        .andExpect(jsonPath("$.runId").value(nullValue()));
    verify(agentClient, never()).dispatch(anyLong());
    assertThat(lastAuditAction()).isEqualTo("run.reject");
    as(researcherId, get("/api/runs/{runId}/improvements", run))
        .andExpect(jsonPath("$.run.awaitingApproval").value(true))   // 남은 개선안이 있다
        .andExpect(jsonPath("$.improvements[*].decision").value(contains("reject", null)));
    decide(researcherId, run, option1, "approve", null)   // 반려한 개선안은 다시 결정할 수 없다
        .andExpect(status().isConflict())
        .andExpect(jsonPath("$.code").value("IMP-ERR-002"));

    decide(researcherId, run, option2, "reject", null).andExpect(status().isCreated());
    jdbcTemplate.update("UPDATE approvals SET decided_at = '2026-10-20 14:00:00' WHERE improvement_id = ?", option1);
    jdbcTemplate.update("UPDATE approvals SET decided_at = '2026-10-20 15:00:00' WHERE improvement_id = ?", option2);
    as(researcherId, get("/api/runs"))   // 전부 반려 — 다음 회차 없이 완료, 완료 시각은 마지막 반려 시각
        .andExpect(jsonPath("$.content[?(@.firstRunId == " + run + ")].state").value(contains("completed")));
    assertThat(jdbcTemplate.queryForObject("SELECT COUNT(*) FROM runs WHERE first_run_id = ?", Integer.class, run))
        .isEqualTo(1);
    as(researcherId, get("/api/runs").param("finishedFrom", "2026-10-20T15:00:00+09:00"))
        .andExpect(jsonPath("$.content[?(@.firstRunId == " + run + ")]", hasSize(1)));
    as(researcherId, get("/api/runs").param("finishedFrom", "2026-10-20T15:00:01+09:00"))
        .andExpect(jsonPath("$.content[?(@.firstRunId == " + run + ")]", hasSize(0)));
  }

  // ───────── 승인 가능 조건 (409) ─────────

  @ParameterizedTest(name = "{0} → 409 IMP-ERR-002, 승인 대기 아님")
  @CsvSource({
      "diagnose 실험, diagnose, , done, false, 1",
      "improve 실험, improve, , done, false, 1",
      "회차가 아직 실행 중, loop, 3, running, false, 1",
      "취소 요청됨, loop, 3, done, true, 1",
      "최대 회차 도달(2회차 · loop_max 2), loop, 2, done, false, 2"
  })
  void notDecidable_isConflict(String label, String mode, Integer loopMax, String status, boolean cancelRequested,
      int round) throws Exception {
    long first = insertRun(mode, loopMax, round == 1 ? status : "done", null);
    long run = round == 1 ? first : insertRun(mode, loopMax, status, first);
    jdbcTemplate.update("UPDATE runs SET cancel_requested = ? WHERE run_id = ?", cancelRequested, run);
    long improvement = insertImprovement(run, 1, "[]");

    decide(researcherId, run, improvement, "approve", null)
        .andExpect(status().isConflict())
        .andExpect(jsonPath("$.code").value("IMP-ERR-002"));
    decide(researcherId, run, improvement, "reject", null)
        .andExpect(status().isConflict())
        .andExpect(jsonPath("$.code").value("IMP-ERR-002"));
    if (!"running".equals(status)) {
      as(researcherId, get("/api/runs/{runId}/improvements", run))
          .andExpect(jsonPath("$.run.awaitingApproval").value(false));
    }
    verify(agentClient, never()).dispatch(anyLong());
  }

  @Test
  void approve_whileAnotherExperimentInProgress_isConflict_butRejectIsAllowed() throws Exception {
    long run = insertRun("loop", 3, "done", null);
    long option1 = insertImprovement(run, 1, "[]");
    long option2 = insertImprovement(run, 2, "[]");
    insertRun("diagnose", null, "running", null);   // 승인 대기 중에 같은 프로젝트에 요청된 다른 실험

    decide(researcherId, run, option1, "approve", null)
        .andExpect(status().isConflict())
        .andExpect(jsonPath("$.code").value("EXP-ERR-004"));
    decide(researcherId, run, option2, "reject", null)
        .andExpect(status().isCreated());
  }

  // ───────── 404 · 400 ─────────

  @Test
  void othersRun_deletedProject_otherRunsImprovement_andMissing_areNotFound() throws Exception {
    long run = insertRun("loop", 3, "done", null);
    long improvement = insertImprovement(run, 1, "[]");
    long otherRun = insertRun("loop", 3, "done", null);
    long otherRunsImprovement = insertImprovement(otherRun, 1, "[]");
    Long other = insertUser("improvement-other@uxight.com");

    as(other, get("/api/runs/{runId}/improvements", run))
        .andExpect(status().isNotFound()).andExpect(jsonPath("$.code").value("EXP-ERR-002"));
    as(other, get("/api/improvements/{improvementId}", improvement))
        .andExpect(status().isNotFound()).andExpect(jsonPath("$.code").value("IMP-ERR-001"));
    decide(other, run, improvement, "approve", null)
        .andExpect(status().isNotFound()).andExpect(jsonPath("$.code").value("EXP-ERR-002"));
    decide(researcherId, run, otherRunsImprovement, "approve", null)   // 경로의 회차에서 산출한 개선안이 아니다
        .andExpect(status().isNotFound()).andExpect(jsonPath("$.code").value("IMP-ERR-001"));
    decide(researcherId, run, 999_999_999L, "approve", null)
        .andExpect(status().isNotFound()).andExpect(jsonPath("$.code").value("IMP-ERR-001"));

    jdbcTemplate.update("UPDATE projects SET deleted_at = NOW() WHERE project_id = ?", projectId);
    as(researcherId, get("/api/runs/{runId}/improvements", run))
        .andExpect(status().isNotFound()).andExpect(jsonPath("$.code").value("EXP-ERR-002"));
    as(researcherId, get("/api/improvements/{improvementId}", improvement))
        .andExpect(status().isNotFound()).andExpect(jsonPath("$.code").value("IMP-ERR-001"));
    decide(researcherId, run, improvement, "approve", null)
        .andExpect(status().isNotFound()).andExpect(jsonPath("$.code").value("EXP-ERR-002"));
  }

  @Test
  void notDoneRun_isNotFound_forListAndDetail() throws Exception {
    long run = insertRun("loop", 3, "running", null);   // 개선안은 done 기록 전에 저장된다 — 작성 중이면 보이지 않는다
    long improvement = insertImprovement(run, 1, "[]");

    as(researcherId, get("/api/runs/{runId}/improvements", run))
        .andExpect(status().isNotFound()).andExpect(jsonPath("$.code").value("EXP-ERR-002"));
    as(researcherId, get("/api/improvements/{improvementId}", improvement))
        .andExpect(status().isNotFound()).andExpect(jsonPath("$.code").value("IMP-ERR-001"));
  }

  @Test
  void detail_findingsAreOnlyFromSameRun() throws Exception {
    long run = insertRun("loop", 3, "done", null);
    long otherRun = insertRun("loop", 3, "done", null);
    long mine = insertFinding(run);
    long notMine = insertFinding(otherRun);
    long improvement = insertImprovement(run, 1, "[" + mine + ", " + notMine + "]");

    as(researcherId, get("/api/improvements/{improvementId}", improvement))
        .andExpect(jsonPath("$.findings[*].findingId").value(contains((int) mine)));
  }

  @ParameterizedTest(name = "[{index}] {0} → {1}")
  @CsvSource(delimiter = '|', value = {
      "{\"decision\":\"approve\"}|GLB-ERR-002",
      "{\"improvementId\":1}|GLB-ERR-002",
      "{\"improvementId\":1,\"decision\":\"maybe\"}|GLB-ERR-002",
      "{\"improvementId\":|GLB-ERR-001"
  })
  void invalidBody_isBadRequest(String json, String code) throws Exception {
    long run = insertRun("loop", 3, "done", null);
    as(researcherId, post("/api/runs/{runId}/approvals", run).contentType(MediaType.APPLICATION_JSON).content(json))
        .andExpect(status().isBadRequest())
        .andExpect(jsonPath("$.code").value(code));
  }

  @Test
  void withoutToken_isUnauthorized() throws Exception {
    mvc.perform(get("/api/improvements/1"))
        .andExpect(status().isUnauthorized())
        .andExpect(jsonPath("$.code").value("AUT-ERR-001"));
  }

  // ───────── 도우미 ─────────

  private ResultActions decide(Long userId, long runId, long improvementId, String decision, String note) throws Exception {
    String json = objectMapper.writeValueAsString(note == null
        ? Map.of("improvementId", improvementId, "decision", decision)
        : Map.of("improvementId", improvementId, "decision", decision, "note", note));
    return as(userId, post("/api/runs/{runId}/approvals", runId).contentType(MediaType.APPLICATION_JSON).content(json));
  }

  private JsonNode body(ResultActions result) throws Exception {
    return objectMapper.readTree(result.andReturn().getResponse().getContentAsString());
  }

  private ResultActions as(Long userId, MockHttpServletRequestBuilder request) throws Exception {
    return mvc.perform(request.header(HttpHeaders.AUTHORIZATION, "Bearer " + jwtProvider.createAccessToken(userId)));
  }

  private long seedRunId() {
    return jdbcTemplate.queryForObject("SELECT MIN(r.run_id) FROM runs r JOIN projects p ON p.project_id = r.project_id "
        + "WHERE p.user_id = ? AND p.title = '[seed] 개선안 예시 쇼핑몰'", Long.class, SEED_USER_ID);
  }

  private long improvementId(long runId, int optionNo) {
    return jdbcTemplate.queryForObject("SELECT improvement_id FROM improvements WHERE run_id = ? AND option_no = ?",
        Long.class, runId, optionNo);
  }

  private String lastAuditAction() {
    return jdbcTemplate.queryForObject("SELECT action FROM audit_log ORDER BY audit_log_id DESC LIMIT 1", String.class);
  }

  private Long insertUser(String email) {
    jdbcTemplate.update("INSERT INTO users (email, password_hash, auth_provider, name, role, is_active) "
        + "VALUES (?, 'hash', 'local', '개선', 'researcher', TRUE)", email);
    return jdbcTemplate.queryForObject("SELECT user_id FROM users WHERE email = ?", Long.class, email);
  }

  private Long insertProject(Long ownerId) {
    jdbcTemplate.update("INSERT INTO projects (user_id, title, target_url, allowed_domains) "
        + "VALUES (?, '개선 몰', 'https://shop.example.com', JSON_ARRAY('shop.example.com'))", ownerId);
    return jdbcTemplate.queryForObject("SELECT LAST_INSERT_ID()", Long.class);
  }

  /** firstRunId 가 null 이면 최초 회차, 아니면 그 실험의 다음 회차(직전 회차 = 그 실험의 가장 최근 회차). */
  private long insertRun(String mode, Integer loopMax, String status, Long firstRunId) {
    jdbcTemplate.update("INSERT INTO tasks (project_id, goal, success_rule, success_url) "
        + "VALUES (?, '결제한다', 'rule', 'https://shop.example.com/done')", projectId);
    Long taskId = jdbcTemplate.queryForObject("SELECT LAST_INSERT_ID()", Long.class);
    Long parent = firstRunId == null ? null
        : jdbcTemplate.queryForObject("SELECT MAX(run_id) FROM runs WHERE first_run_id = ?", Long.class, firstRunId);
    jdbcTemplate.update("INSERT INTO runs (project_id, task_id, mode, loop_max, target_url_snapshot, allowed_domains_snapshot, "
            + "task_snapshot, policy_snapshot, persona_snapshot, status, parent_run_id) "
            + "VALUES (?, ?, ?, ?, 'https://shop.example.com', JSON_ARRAY(), JSON_OBJECT(), JSON_OBJECT(), "
            + "JSON_ARRAY(JSON_OBJECT('persona_id', ?, 'name', '초보')), ?, ?)",
        projectId, taskId, mode, loopMax, personaId, status, parent);
    long runId = jdbcTemplate.queryForObject("SELECT LAST_INSERT_ID()", Long.class);
    jdbcTemplate.update("UPDATE runs SET first_run_id = ? WHERE run_id = ?", firstRunId == null ? runId : firstRunId, runId);
    return runId;
  }

  private long insertImprovement(long runId, int optionNo, String findingIdsJson) {
    jdbcTemplate.update("INSERT INTO improvements (run_id, finding_ids, option_no, patch_kind, patch, fix_cost) "
        + "VALUES (?, ?, ?, 'relabel', JSON_OBJECT('target', '#btn', 'new_text', '구매'), 'low')", runId, findingIdsJson, optionNo);
    return jdbcTemplate.queryForObject("SELECT LAST_INSERT_ID()", Long.class);
  }

  private long insertFinding(long runId) {
    jdbcTemplate.update("INSERT INTO findings (run_id, taxonomy, severity, evidence) VALUES (?, 'task_failure', 'high', '[]')",
        runId);
    return jdbcTemplate.queryForObject("SELECT LAST_INSERT_ID()", Long.class);
  }
}
