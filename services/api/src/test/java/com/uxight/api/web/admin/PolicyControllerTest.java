package com.uxight.api.web.admin;

import static org.assertj.core.api.Assertions.assertThat;
import static org.hamcrest.Matchers.hasSize;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.patch;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.uxight.api.domain.run.AgentClient;
import com.uxight.api.domain.task.SuccessRuleClient;
import com.uxight.api.domain.user.JwtProvider;
import jakarta.persistence.EntityManager;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;
import org.junit.jupiter.params.provider.ValueSource;
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
 * 전역 정책 조회 · 수정(GET · PATCH /api/admin/policy) — 관리자만. 수정은 감사 로그에 남고, 이후 요청되는 실험의 정책 스냅샷부터 적용된다.
 * 실제 MySQL, 테스트마다 롤백.
 */
@SpringBootTest
@AutoConfigureMockMvc
@Transactional
class PolicyControllerTest {

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

  private Long adminId;

  @BeforeEach
  void setUp() {
    adminId = insertUser("policy-admin@uxight.com", "admin");
    when(successRuleClient.createSuccessRule(anyString(), anyString(), anyString())).thenReturn("rule");
    when(agentClient.dispatch(anyLong())).thenReturn(CompletableFuture.completedFuture(Optional.empty()));
  }

  // ───────── GET ─────────

  @Test
  void admin_getsGlobalPolicy_withSevenFields() throws Exception {
    policy(adminId)
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.*", hasSize(7)))   // modelMap 은 싣지 않는다
        .andExpect(jsonPath("$.maxSteps").value(10))
        .andExpect(jsonPath("$.maxSeconds").value(120))
        .andExpect(jsonPath("$.maxTokens").value(20000))
        .andExpect(jsonPath("$.runConcurrency").value(1))
        .andExpect(jsonPath("$.personaConcurrency").value(2))
        .andExpect(jsonPath("$.rateLimitPerDomain").value(30))
        .andExpect(jsonPath("$.dailyTokenBudget").value(200000));
  }

  // ───────── PATCH ─────────

  @Test
  void update_changesOnlySentFields_returnsWholePolicy_andRecordsChangesInAuditLog() throws Exception {
    // maxSeconds 는 지금과 같은 값 — 바뀐 것이 아니므로 감사 로그에 없다
    update(adminId, "{\"maxSteps\":7,\"maxSeconds\":120,\"dailyTokenBudget\":999}")
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.*", hasSize(7)))
        .andExpect(jsonPath("$.maxSteps").value(7))
        .andExpect(jsonPath("$.maxSeconds").value(120))
        .andExpect(jsonPath("$.maxTokens").value(20000))          // 보내지 않은 항목은 그대로
        .andExpect(jsonPath("$.personaConcurrency").value(2))
        .andExpect(jsonPath("$.dailyTokenBudget").value(999));

    assertThat(jdbcTemplate.queryForMap("SELECT max_steps, max_tokens, daily_token_budget FROM policies WHERE policy_id = 1"))
        .containsEntry("max_steps", 7)
        .containsEntry("max_tokens", 20000)
        .containsEntry("daily_token_budget", 999L);
    Map<String, Object> audit = jdbcTemplate.queryForMap(
        "SELECT actor, action, target, detail, ts FROM audit_log WHERE actor = ? ORDER BY audit_log_id DESC LIMIT 1",
        "user:" + adminId);
    assertThat(audit).containsEntry("action", "policy.update").containsEntry("target", "policy:1");
    assertThat(audit.get("ts")).isNotNull();
    assertThat(objectMapper.readValue(audit.get("detail").toString(), new TypeReference<Map<String, Object>>() {}))
        .isEqualTo(Map.of("changes", Map.of(
            "maxSteps", Map.of("before", 10, "after", 7),
            "dailyTokenBudget", Map.of("before", 200000, "after", 999))));
  }

  @ParameterizedTest
  @ValueSource(strings = {"{}", "{\"maxSteps\":10,\"rateLimitPerDomain\":30}", "{\"maxSteps\":null}"})
  void update_withNothingChanged_returnsPolicy_andRecordsNoAuditLog(String json) throws Exception {
    update(adminId, json)
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.maxSteps").value(10));

    assertThat(auditCount()).isZero();
  }

  @ParameterizedTest(name = "{0}={1}")
  @CsvSource({
      "maxSteps, 0", "maxSeconds, -1", "maxTokens, 0", "runConcurrency, 0", "personaConcurrency, -5",
      "rateLimitPerDomain, 0", "dailyTokenBudget, 0"
  })
  void update_nonPositiveValue_returnsInvalidInput_andChangesNothing(String field, int value) throws Exception {
    update(adminId, "{\"maxSteps\":7,\"" + field + "\":" + value + "}")
        .andExpect(status().isBadRequest())
        .andExpect(jsonPath("$.code").value("GLB-ERR-002"))
        .andExpect(jsonPath("$.fieldErrors[0].field").value(field));

    assertThat(jdbcTemplate.queryForObject("SELECT max_steps FROM policies WHERE policy_id = 1", Integer.class))
        .isEqualTo(10);
    assertThat(auditCount()).isZero();
  }

  @ParameterizedTest
  @ValueSource(strings = {"{\"maxSteps\":", "{\"maxSteps\":\"many\"}", "{\"maxSteps\":1.5}", "[]"})
  void update_unreadableBody_returnsBadRequest(String json) throws Exception {
    update(adminId, json)
        .andExpect(status().isBadRequest())
        .andExpect(jsonPath("$.code").value("GLB-ERR-001"));
  }

  @Test
  void update_appliesFromNextExperiment_inProgressExperimentKeepsItsSnapshot() throws Exception {
    Long researcher = insertUser("policy-researcher@uxight.com", "researcher");
    Long personaId = insertPersona(researcher);
    long before = requestExperiment(researcher, insertProject(researcher), personaId);   // 수정 전에 요청한 실험

    update(adminId, "{\"maxSteps\":7,\"personaConcurrency\":3,\"dailyTokenBudget\":999}").andExpect(status().isOk());
    policy(adminId).andExpect(jsonPath("$.maxSteps").value(7));
    long after = requestExperiment(researcher, insertProject(researcher), personaId);    // 수정 뒤에 요청한 실험

    // 진행 중인 실험은 시작 시점의 정책으로 계속 실행된다 — 멈추지도 않는다
    assertThat(snapshot(before)).containsEntry("max_steps", 10).containsEntry("persona_concurrency", 2);
    assertThat(jdbcTemplate.queryForMap("SELECT status, cancel_requested FROM runs WHERE run_id = ?", before))
        .containsEntry("status", "queued").containsEntry("cancel_requested", false);
    // 이후 요청한 실험부터 새 정책 — POST /runs 는 run_id 만 보내고 AI 모듈이 이 스냅샷을 읽는다
    verify(agentClient).dispatch(after);
    assertThat(snapshot(after))
        .containsEntry("max_steps", 7)
        .containsEntry("persona_concurrency", 3)
        .containsEntry("max_tokens", 20000)
        .doesNotContainKey("daily_token_budget");   // 모든 회차가 나눠 쓰는 한도 — AI 모듈이 매번 policies 에서 읽는다
  }

  // ───────── 권한 ─────────

  @Test
  void researcher_isForbidden_forGetAndPatch() throws Exception {
    Long researcher = insertUser("policy-researcher@uxight.com", "researcher");
    policy(researcher)
        .andExpect(status().isForbidden())
        .andExpect(jsonPath("$.code").value("AUT-ERR-006"));
    update(researcher, "{\"maxSteps\":1}")
        .andExpect(status().isForbidden())
        .andExpect(jsonPath("$.code").value("AUT-ERR-006"));
    assertThat(jdbcTemplate.queryForObject("SELECT max_steps FROM policies WHERE policy_id = 1", Integer.class))
        .isEqualTo(10);
  }

  @Test
  void withoutTokenOrByInactiveAdmin_isUnauthorized() throws Exception {
    mvc.perform(get("/api/admin/policy"))
        .andExpect(status().isUnauthorized())
        .andExpect(jsonPath("$.code").value("AUT-ERR-001"));
    mvc.perform(patch("/api/admin/policy").contentType(MediaType.APPLICATION_JSON).content("{\"maxSteps\":1}"))
        .andExpect(status().isUnauthorized())
        .andExpect(jsonPath("$.code").value("AUT-ERR-001"));

    jdbcTemplate.update("UPDATE users SET is_active = FALSE WHERE user_id = ?", adminId);
    policy(adminId)
        .andExpect(status().isUnauthorized())
        .andExpect(jsonPath("$.code").value("AUT-ERR-005"));
  }

  private ResultActions policy(Long userId) throws Exception {
    return mvc.perform(get("/api/admin/policy")
        .header(HttpHeaders.AUTHORIZATION, "Bearer " + jwtProvider.createAccessToken(userId)));
  }

  // 정책 변경은 커밋 때 dirty checking 으로 UPDATE 되는데 테스트 트랜잭션은 커밋하지 않는다 — JdbcTemplate 으로 보기 전에 flush 한다.
  private ResultActions update(Long userId, String json) throws Exception {
    ResultActions result = mvc.perform(patch("/api/admin/policy")
        .header(HttpHeaders.AUTHORIZATION, "Bearer " + jwtProvider.createAccessToken(userId))
        .contentType(MediaType.APPLICATION_JSON)
        .content(json));
    entityManager.flush();
    return result;
  }

  private long requestExperiment(Long researcher, Long projectId, Long personaId) throws Exception {
    String body = mvc.perform(post("/api/projects/{projectId}/runs", projectId)
            .header(HttpHeaders.AUTHORIZATION, "Bearer " + jwtProvider.createAccessToken(researcher))
            .contentType(MediaType.APPLICATION_JSON)
            .content("{\"goal\":\"g\",\"successUrl\":\"https://a.example.com/done\",\"personaIds\":[" + personaId
                + "],\"mode\":\"diagnose\"}"))
        .andExpect(status().isCreated())
        .andReturn().getResponse().getContentAsString();
    entityManager.flush();
    return objectMapper.readTree(body).get("runId").asLong();
  }

  private Map<String, Object> snapshot(long runId) throws Exception {
    return objectMapper.readValue(
        jdbcTemplate.queryForObject("SELECT policy_snapshot FROM runs WHERE run_id = ?", String.class, runId),
        new TypeReference<>() {});
  }

  private int auditCount() {
    return jdbcTemplate.queryForObject("SELECT COUNT(*) FROM audit_log WHERE actor = ?", Integer.class, "user:" + adminId);
  }

  private Long insertUser(String email, String role) {
    jdbcTemplate.update("INSERT INTO users (email, password_hash, auth_provider, name, role, is_active) "
        + "VALUES (?, 'hash', 'local', '정책', ?, TRUE)", email, role);
    return jdbcTemplate.queryForObject("SELECT user_id FROM users WHERE email = ?", Long.class, email);
  }

  private Long insertProject(Long ownerId) {
    jdbcTemplate.update("INSERT INTO projects (user_id, title, target_url, allowed_domains) "
        + "VALUES (?, 'p', 'https://a.example.com', JSON_ARRAY('a.example.com'))", ownerId);
    return jdbcTemplate.queryForObject("SELECT LAST_INSERT_ID()", Long.class);
  }

  private Long insertPersona(Long ownerId) {
    jdbcTemplate.update("INSERT INTO personas (user_id, name, profile) VALUES (?, 'p', JSON_OBJECT('webSkill', 'low'))",
        ownerId);
    return jdbcTemplate.queryForObject("SELECT LAST_INSERT_ID()", Long.class);
  }
}
