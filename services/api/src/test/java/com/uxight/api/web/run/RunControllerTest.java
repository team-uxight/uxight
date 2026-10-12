package com.uxight.api.web.run;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.uxight.api.domain.run.AgentClient;
import com.uxight.api.common.ApiException;
import com.uxight.api.common.ErrorCode;
import com.uxight.api.domain.project.ProjectService;
import com.uxight.api.domain.run.DispatchState;
import com.uxight.api.domain.task.SuccessRuleClient;
import com.uxight.api.domain.user.JwtProvider;
import jakarta.persistence.EntityManager;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.ResultActions;
import org.springframework.transaction.annotation.Transactional;

import java.util.Map;
import java.util.Optional;
import java.util.concurrent.CompletableFuture;

/**
 * 실험 요청 · 목록 · 취소(Run 엔티티 전환 회귀). 실제 MySQL, 테스트마다 롤백.
 * AI 모듈 호출(POST /runs)은 대역으로 바꾼다 — 즉시 완료된 결과를 돌려주므로 dispatch_state 기록까지 테스트 스레드에서 끝난다.
 */
@SpringBootTest
@AutoConfigureMockMvc
@Transactional
class RunControllerTest {

  private static final String PROFILE =
      "{\"webSkill\":\"low\",\"device\":\"mobile\",\"domainKnowledge\":\"low\",\"background\":\"b\"}";

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

  @MockitoBean
  private SuccessRuleClient successRuleClient;

  @Autowired
  private ProjectService projectService;

  private Long userId;
  private String bearer;
  private Long projectId;
  private Long personaId;

  @BeforeEach
  void setUp() {
    jdbcTemplate.update("INSERT INTO users (email, password_hash, auth_provider, name, role, is_active) "
        + "VALUES ('run-api@uxight.com', 'hash', 'local', '실험', 'researcher', TRUE)");
    userId = jdbcTemplate.queryForObject("SELECT LAST_INSERT_ID()", Long.class);
    bearer = "Bearer " + jwtProvider.createAccessToken(userId);
    jdbcTemplate.update("INSERT INTO projects (user_id, title, target_url, allowed_domains) "
        + "VALUES (?, '쇼핑몰', 'https://shop.example.com/start', JSON_ARRAY('shop.example.com', 'pay.example.com'))", userId);
    projectId = jdbcTemplate.queryForObject("SELECT LAST_INSERT_ID()", Long.class);
    jdbcTemplate.update("INSERT INTO personas (user_id, name, profile) VALUES (?, '초보', ?)", userId, PROFILE);
    personaId = jdbcTemplate.queryForObject("SELECT LAST_INSERT_ID()", Long.class);
    when(agentClient.dispatch(anyLong())).thenReturn(CompletableFuture.completedFuture(Optional.of(DispatchState.sent)));
    when(successRuleClient.createSuccessRule(anyString(), anyString(), anyString())).thenReturn("결제 완료 화면에 도달");
  }

  @Test
  void create_savesTaskAndQueuedFirstRound_withSnapshots_andDispatches() throws Exception {
    long runId = createAndGetRunId("diagnose", null);

    Map<String, Object> run = jdbcTemplate.queryForMap(
        "SELECT project_id, task_id, mode, loop_max, first_run_id, status, dispatch_state, cancel_requested, "
            + "target_url_snapshot, JSON_LENGTH(allowed_domains_snapshot) ad, "
            + "JSON_UNQUOTE(JSON_EXTRACT(task_snapshot, '$.goal')) goal, "
            + "JSON_UNQUOTE(JSON_EXTRACT(task_snapshot, '$.success_rule')) rule, "
            + "JSON_EXTRACT(task_snapshot, '$.task_id') snap_task_id, "
            + "JSON_EXTRACT(persona_snapshot, '$[0].persona_id') pid, "
            + "JSON_UNQUOTE(JSON_EXTRACT(persona_snapshot, '$[0].profile.webSkill')) skill "
            + "FROM runs WHERE run_id = ?", runId);
    assertThat(run).containsEntry("project_id", projectId)
        .containsEntry("mode", "diagnose")
        .containsEntry("first_run_id", runId)   // 최초 회차는 자기 자신이 실험 식별자
        .containsEntry("status", "queued")
        .containsEntry("dispatch_state", "sent")
        .containsEntry("cancel_requested", false)
        .containsEntry("target_url_snapshot", "https://shop.example.com/start")
        .containsEntry("ad", 2L)
        .containsEntry("goal", "구매")
        .containsEntry("rule", "결제 완료 화면에 도달")
        .containsEntry("skill", "low");
    assertThat(run.get("loop_max")).isNull();
    assertThat(run.get("snap_task_id")).hasToString(run.get("task_id").toString());
    assertThat(run.get("pid")).hasToString(personaId.toString());

    assertThat(jdbcTemplate.queryForMap("SELECT project_id, goal, success_rule, success_url, is_one_shot FROM tasks "
        + "WHERE task_id = ?", run.get("task_id")))
        .containsEntry("project_id", projectId)
        .containsEntry("success_url", "https://shop.example.com/done")
        .containsEntry("is_one_shot", false);
    verify(agentClient).dispatch(runId);
  }

  @Test
  void create_passesTaskToSuccessRuleAgent_andSnapshotsGlobalPolicyWithoutDailyBudget() throws Exception {
    long runId = createAndGetRunId("diagnose", null);

    verify(successRuleClient).createSuccessRule("https://shop.example.com/start", "구매", "https://shop.example.com/done");
    String policy = jdbcTemplate.queryForObject("SELECT policy_snapshot FROM runs WHERE run_id = ?", String.class, runId);
    Map<String, Object> snapshot = objectMapper.readValue(policy, new TypeReference<>() {});
    // V4 전역 정책 값 — daily_token_budget 은 스냅샷에 넣지 않고, 비어 있는 model_map 도 뺀다
    assertThat(snapshot).containsOnlyKeys("max_steps", "max_seconds", "max_tokens", "run_concurrency",
            "persona_concurrency", "rate_limit_per_domain")
        .containsEntry("max_steps", 10)
        .containsEntry("persona_concurrency", 2);
  }

  @Test
  void create_withExperimentInProgress_returnsConflict_withoutCallingLlm() throws Exception {
    createAndGetRunId("diagnose", null);   // queued 회차 = 진행 중

    request("diagnose", null)
        .andExpect(status().isConflict())
        .andExpect(jsonPath("$.code").value("EXP-ERR-004"));
    // 잠금 없는 사전 확인에서 거절 — 성공 기준 생성 Agent 는 첫 요청 때 한 번만 불렸다
    verify(successRuleClient).createSuccessRule(anyString(), anyString(), anyString());
    assertThat(jdbcTemplate.queryForObject("SELECT COUNT(*) FROM runs WHERE project_id = ?", Integer.class, projectId))
        .isEqualTo(1);
  }

  @Test
  void create_afterPreviousExperimentFinished_isAllowed() throws Exception {
    long first = createAndGetRunId("diagnose", null);
    jdbcTemplate.update("UPDATE runs SET status = 'done' WHERE run_id = ?", first);

    createAndGetRunId("diagnose", null);
  }

  @Test
  void create_withUnknownPersona_returnsNotFound_withoutCallingLlm() throws Exception {
    mvc.perform(post("/api/projects/{projectId}/runs", projectId).header(HttpHeaders.AUTHORIZATION, bearer)
            .contentType(MediaType.APPLICATION_JSON)
            .content("{\"goal\":\"구매\",\"successUrl\":\"https://shop.example.com/done\",\"personaIds\":["
                + Long.MAX_VALUE + "],\"mode\":\"diagnose\"}"))
        .andExpect(status().isNotFound())
        .andExpect(jsonPath("$.code").value("EXP-ERR-003"));
    verify(successRuleClient, never()).createSuccessRule(anyString(), anyString(), anyString());
  }

  @Test
  void create_whenSuccessRuleAgentFails_returnsBadGateway_andSavesNothing() throws Exception {
    when(successRuleClient.createSuccessRule(anyString(), anyString(), anyString()))
        .thenThrow(new ApiException(ErrorCode.SUCCESS_RULE_FAILED));

    request("diagnose", null)
        .andExpect(status().isBadGateway())
        .andExpect(jsonPath("$.code").value("EXP-ERR-007"))
        .andExpect(jsonPath("$.message").value("성공 기준 생성에 실패했습니다."));
    assertNothingSaved();
  }

  @Test
  void create_whenSuccessRuleAgentTimesOut_returnsGatewayTimeout_andSavesNothing() throws Exception {
    when(successRuleClient.createSuccessRule(anyString(), anyString(), anyString()))
        .thenThrow(new ApiException(ErrorCode.SUCCESS_RULE_TIMEOUT));

    request("diagnose", null)
        .andExpect(status().isGatewayTimeout())
        .andExpect(jsonPath("$.code").value("EXP-ERR-008"));
    assertNothingSaved();
  }

  @Test
  void create_whenProjectDeletedDuringLlmCall_returnsNotFound_andSavesNothing() throws Exception {
    // 성공 기준을 기다리는 동안 리서처가 프로젝트를 지웠다 — 잠근 뒤 다시 읽어 알아챈다
    when(successRuleClient.createSuccessRule(anyString(), anyString(), anyString())).thenAnswer(invocation -> {
      projectService.deleteProject(userId, projectId);
      return "rule";
    });

    request("diagnose", null)
        .andExpect(status().isNotFound())
        .andExpect(jsonPath("$.code").value("PRJ-ERR-001"));
    assertNothingSaved();
  }

  @Test
  void create_loop_requiresAndStoresLoopMax() throws Exception {
    request("loop", null)
        .andExpect(status().isBadRequest())
        .andExpect(jsonPath("$.code").value("GLB-ERR-002"))
        .andExpect(jsonPath("$.fieldErrors[0].field").value("loopMax"));

    long runId = createAndGetRunId("loop", 3);
    assertThat(jdbcTemplate.queryForObject("SELECT loop_max FROM runs WHERE run_id = ?", Integer.class, runId))
        .isEqualTo(3);
  }

  @Test
  void create_whenDispatchGetsNoNewAcceptance_leavesDispatchStateEmpty() throws Exception {
    // 200(이미 받은 회차) — dispatch_state 를 건드리지 않는다
    when(agentClient.dispatch(anyLong())).thenReturn(CompletableFuture.completedFuture(Optional.empty()));

    long runId = createAndGetRunId("improve", null);

    assertThat(jdbcTemplate.queryForObject("SELECT dispatch_state FROM runs WHERE run_id = ?", String.class, runId))
        .isNull();
  }

  @Test
  void experiments_listsCreatedExperiment() throws Exception {
    long runId = createAndGetRunId("diagnose", null);

    mvc.perform(get("/api/runs").header(HttpHeaders.AUTHORIZATION, bearer))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.totalElements").value(1))
        .andExpect(jsonPath("$.content[0].firstRunId").value(runId))
        .andExpect(jsonPath("$.content[0].state").value("in_progress"))
        .andExpect(jsonPath("$.content[0].projectTitle").value("쇼핑몰"))
        .andExpect(jsonPath("$.content[0].taskGoal").value("구매"))
        .andExpect(jsonPath("$.content[0].personaCount").value(1));
  }

  @Test
  void cancel_inProgress_recordsRequest_andIsIdempotent() throws Exception {
    long runId = createAndGetRunId("diagnose", null);

    cancel(runId).andExpect(status().isAccepted());
    cancel(runId).andExpect(status().isAccepted());   // 이미 취소 요청됨 — 멱등

    assertThat(jdbcTemplate.queryForMap("SELECT cancel_requested, status FROM runs WHERE run_id = ?", runId))
        .containsEntry("cancel_requested", true)
        .containsEntry("status", "queued");   // status 는 Python 이 바꾼다
  }

  @Test
  void cancel_finishedOrOthersExperiment_isRejected() throws Exception {
    long runId = createAndGetRunId("diagnose", null);
    jdbcTemplate.update("UPDATE runs SET status = 'done' WHERE run_id = ?", runId);
    entityManager.clear();

    cancel(runId)
        .andExpect(status().isConflict())
        .andExpect(jsonPath("$.code").value("EXP-ERR-006"));
    mvc.perform(post("/api/runs/{firstRunId}/cancel", runId)
            .header(HttpHeaders.AUTHORIZATION, "Bearer " + jwtProvider.createAccessToken(otherUser())))
        .andExpect(status().isNotFound())
        .andExpect(jsonPath("$.code").value("EXP-ERR-001"));
  }

  private long createAndGetRunId(String mode, Integer loopMax) throws Exception {
    String body = request(mode, loopMax)
        .andExpect(status().isCreated())
        .andExpect(jsonPath("$.runId").isNumber())
        .andReturn().getResponse().getContentAsString();
    entityManager.flush();   // first_run_id UPDATE 는 커밋(여기서는 flush) 때 나간다
    return objectMapper.readTree(body).get("runId").asLong();
  }

  private ResultActions request(String mode, Integer loopMax) throws Exception {
    String json = "{\"goal\":\"구매\",\"successUrl\":\"https://shop.example.com/done\",\"personaIds\":[" + personaId
        + "],\"mode\":\"" + mode + "\"" + (loopMax != null ? ",\"loopMax\":" + loopMax : "") + "}";
    return mvc.perform(post("/api/projects/{projectId}/runs", projectId).header(HttpHeaders.AUTHORIZATION, bearer)
        .contentType(MediaType.APPLICATION_JSON)
        .content(json));
  }

  private void assertNothingSaved() {
    assertThat(jdbcTemplate.queryForObject("SELECT COUNT(*) FROM tasks WHERE project_id = ?", Integer.class, projectId))
        .isZero();
    assertThat(jdbcTemplate.queryForObject("SELECT COUNT(*) FROM runs WHERE project_id = ?", Integer.class, projectId))
        .isZero();
    verify(agentClient, never()).dispatch(anyLong());
  }

  private ResultActions cancel(long firstRunId) throws Exception {
    return mvc.perform(post("/api/runs/{firstRunId}/cancel", firstRunId).header(HttpHeaders.AUTHORIZATION, bearer));
  }

  private Long otherUser() {
    jdbcTemplate.update("INSERT INTO users (email, password_hash, auth_provider, name, role, is_active) "
        + "VALUES ('run-other@uxight.com', 'hash', 'local', '남', 'researcher', TRUE)");
    return jdbcTemplate.queryForObject("SELECT LAST_INSERT_ID()", Long.class);
  }
}
