package com.uxight.api.web.admin;

import static org.assertj.core.api.Assertions.assertThat;
import static org.hamcrest.Matchers.hasSize;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.uxight.api.domain.run.AgentClient;
import com.uxight.api.domain.task.SuccessRuleClient;
import com.uxight.api.domain.user.JwtProvider;
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

/** 전역 정책 조회(GET /api/admin/policy) — 관리자만. 조회 값이 실험 요청의 정책 스냅샷에 그대로 실리는지도 본다. 실제 MySQL, 롤백. */
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

  @MockitoBean
  private AgentClient agentClient;

  @MockitoBean
  private SuccessRuleClient successRuleClient;

  @Test
  void admin_getsGlobalPolicy_withSevenFields() throws Exception {
    policy(insertUser("policy-admin@uxight.com", "admin"))
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

  @Test
  void globalPolicyShown_isWhatTheNextExperimentCarriesInPolicySnapshot() throws Exception {
    // 관리자가 값을 바꿨다고 친다(수정 API 전이라 SQL 로)
    jdbcTemplate.update("UPDATE policies SET max_steps = 7, max_seconds = 90, persona_concurrency = 3, "
        + "daily_token_budget = 999 WHERE policy_id = 1");
    policy(insertUser("policy-admin@uxight.com", "admin"))
        .andExpect(jsonPath("$.maxSteps").value(7))
        .andExpect(jsonPath("$.maxSeconds").value(90))
        .andExpect(jsonPath("$.personaConcurrency").value(3))
        .andExpect(jsonPath("$.dailyTokenBudget").value(999));

    // 리서처가 실험을 요청한다 — POST /runs 는 run_id 만 보내고, AI 모듈은 그 회차의 policy_snapshot 을 읽는다
    Long researcher = insertUser("policy-researcher@uxight.com", "researcher");
    jdbcTemplate.update("INSERT INTO projects (user_id, title, target_url, allowed_domains) "
        + "VALUES (?, 'p', 'https://a.example.com', JSON_ARRAY('a.example.com'))", researcher);
    Long projectId = jdbcTemplate.queryForObject("SELECT LAST_INSERT_ID()", Long.class);
    jdbcTemplate.update("INSERT INTO personas (user_id, name, profile) VALUES (?, 'p', JSON_OBJECT('webSkill', 'low'))",
        researcher);
    Long personaId = jdbcTemplate.queryForObject("SELECT LAST_INSERT_ID()", Long.class);
    when(successRuleClient.createSuccessRule(anyString(), anyString(), anyString())).thenReturn("rule");
    when(agentClient.dispatch(anyLong())).thenReturn(CompletableFuture.completedFuture(Optional.empty()));

    String body = mvc.perform(post("/api/projects/{projectId}/runs", projectId)
            .header(HttpHeaders.AUTHORIZATION, "Bearer " + jwtProvider.createAccessToken(researcher))
            .contentType(MediaType.APPLICATION_JSON)
            .content("{\"goal\":\"g\",\"successUrl\":\"https://a.example.com/done\",\"personaIds\":[" + personaId
                + "],\"mode\":\"diagnose\"}"))
        .andExpect(status().isCreated())
        .andReturn().getResponse().getContentAsString();
    long runId = objectMapper.readTree(body).get("runId").asLong();

    verify(agentClient).dispatch(runId);
    Map<String, Object> snapshot = objectMapper.readValue(
        jdbcTemplate.queryForObject("SELECT policy_snapshot FROM runs WHERE run_id = ?", String.class, runId),
        new TypeReference<>() {});
    assertThat(snapshot)
        .containsEntry("max_steps", 7)
        .containsEntry("max_seconds", 90)
        .containsEntry("max_tokens", 20000)
        .containsEntry("run_concurrency", 1)
        .containsEntry("persona_concurrency", 3)
        .containsEntry("rate_limit_per_domain", 30)
        .doesNotContainKey("daily_token_budget");   // 모든 회차가 나눠 쓰는 한도 — AI 모듈이 매번 policies 에서 읽는다
  }

  @Test
  void researcher_isForbidden() throws Exception {
    policy(insertUser("policy-researcher@uxight.com", "researcher"))
        .andExpect(status().isForbidden())
        .andExpect(jsonPath("$.code").value("AUT-ERR-006"));
  }

  @Test
  void withoutTokenOrByInactiveAdmin_isUnauthorized() throws Exception {
    mvc.perform(get("/api/admin/policy"))
        .andExpect(status().isUnauthorized())
        .andExpect(jsonPath("$.code").value("AUT-ERR-001"));

    Long admin = insertUser("policy-admin@uxight.com", "admin");
    jdbcTemplate.update("UPDATE users SET is_active = FALSE WHERE user_id = ?", admin);
    policy(admin)
        .andExpect(status().isUnauthorized())
        .andExpect(jsonPath("$.code").value("AUT-ERR-005"));
  }

  private ResultActions policy(Long userId) throws Exception {
    return mvc.perform(get("/api/admin/policy")
        .header(HttpHeaders.AUTHORIZATION, "Bearer " + jwtProvider.createAccessToken(userId)));
  }

  private Long insertUser(String email, String role) {
    jdbcTemplate.update("INSERT INTO users (email, password_hash, auth_provider, name, role, is_active) "
        + "VALUES (?, 'hash', 'local', '정책', ?, TRUE)", email, role);
    return jdbcTemplate.queryForObject("SELECT user_id FROM users WHERE email = ?", Long.class, email);
  }
}
