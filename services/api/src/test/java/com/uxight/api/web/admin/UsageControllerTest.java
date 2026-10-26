package com.uxight.api.web.admin;

import static org.assertj.core.api.Assertions.assertThat;
import static org.hamcrest.Matchers.hasSize;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.uxight.api.domain.run.AgentClient;
import com.uxight.api.domain.task.SuccessRuleClient;
import com.uxight.api.domain.user.JwtProvider;
import jakarta.persistence.EntityManager;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
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

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.YearMonth;
import java.time.ZoneId;
import java.util.Optional;
import java.util.concurrent.CompletableFuture;

/**
 * 모델 사용량(GET /api/admin/usage) — admin · maintainer 만. 한 달의 비용 · 토큰 · 회차 수 합계와 일별 값.
 * 실제 MySQL, 테스트마다 롤백. 다른 회차와 섞이지 않게 2001년 3월에 만든 회차를 2001-03 으로 조회한다.
 */
@SpringBootTest
@AutoConfigureMockMvc
@Transactional
class UsageControllerTest {

  private static final ZoneId KST = ZoneId.of("Asia/Seoul");

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
  private Long researcherId;
  private Long projectId;

  @BeforeEach
  void setUp() {
    adminId = insertUser("usage-admin@uxight.com", "admin");
    researcherId = insertUser("usage-researcher@uxight.com", "researcher");
    projectId = insertProject(researcherId);
    when(successRuleClient.createSuccessRule(anyString(), anyString(), anyString())).thenReturn("rule");
    when(agentClient.dispatch(anyLong())).thenReturn(CompletableFuture.completedFuture(Optional.empty()));
  }

  @Test
  void pastMonth_hasEveryDay_zeroFilled_andSumsAllRoundsOfThatKstDay() throws Exception {
    insertRun(projectId, "done", 1000L, "0.1200", "2001-03-05 00:00:00");      // 그날 시작
    insertRun(projectId, "failed", 500L, "0.0300", "2001-03-05 23:59:59");    // 실패해도 쓴 만큼
    insertRun(projectId, "cancelled", 200L, "0.0050", "2001-03-31 23:59:59"); // 말일 끝
    insertRun(projectId, "queued", null, null, "2001-03-20 12:00:00");        // 아직 안 씀 — 회차 수만
    insertRun(projectId, "done", 9999L, "9.9999", "2001-04-01 00:00:00");     // 다음 달 — 빠진다
    insertRun(projectId, "done", 9999L, "9.9999", "2001-02-28 23:59:59");     // 지난달 — 빠진다

    usage(adminId, "2001-03")
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.*", hasSize(3)))
        .andExpect(jsonPath("$.month").value("2001-03"))
        .andExpect(jsonPath("$.total.*", hasSize(3)))
        .andExpect(jsonPath("$.total.costUsd").value(0.155))
        .andExpect(jsonPath("$.total.tokens").value(1700))
        .andExpect(jsonPath("$.total.runCount").value(4))
        .andExpect(jsonPath("$.daily", hasSize(31)))   // 지난달은 말일까지
        .andExpect(jsonPath("$.daily[0].*", hasSize(4)))
        .andExpect(jsonPath("$.daily[0].date").value("2001-03-01"))
        .andExpect(jsonPath("$.daily[0].costUsd").value(0))
        .andExpect(jsonPath("$.daily[0].tokens").value(0))
        .andExpect(jsonPath("$.daily[0].runCount").value(0))
        .andExpect(jsonPath("$.daily[4].date").value("2001-03-05"))
        .andExpect(jsonPath("$.daily[4].costUsd").value(0.15))
        .andExpect(jsonPath("$.daily[4].tokens").value(1500))
        .andExpect(jsonPath("$.daily[4].runCount").value(2))
        .andExpect(jsonPath("$.daily[19].runCount").value(1))
        .andExpect(jsonPath("$.daily[19].tokens").value(0))
        .andExpect(jsonPath("$.daily[30].date").value("2001-03-31"))
        .andExpect(jsonPath("$.daily[30].costUsd").value(0.005));
  }

  @Test
  void includesEveryUsersRounds_andDeletedProjects() throws Exception {
    Long other = insertUser("usage-other@uxight.com", "researcher");
    Long deleted = insertProject(other);
    jdbcTemplate.update("UPDATE projects SET deleted_at = NOW() WHERE project_id = ?", deleted);
    insertRun(projectId, "done", 100L, "0.0100", "2001-03-10 10:00:00");
    insertRun(deleted, "done", 300L, "0.0300", "2001-03-10 11:00:00");   // 비용은 이미 쓴 것

    usage(adminId, "2001-03")
        .andExpect(jsonPath("$.total.tokens").value(400))
        .andExpect(jsonPath("$.total.runCount").value(2))
        .andExpect(jsonPath("$.daily[9].costUsd").value(0.04));
  }

  @Test
  void defaultIsCurrentKstMonth_untilToday() throws Exception {
    LocalDate today = LocalDate.now(KST);
    usage(adminId, null)
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.month").value(YearMonth.from(today).toString()))
        .andExpect(jsonPath("$.daily", hasSize(today.getDayOfMonth())))   // 오늘까지
        .andExpect(jsonPath("$.daily[0].date").value(today.withDayOfMonth(1).toString()))
        .andExpect(jsonPath("$.daily[-1].date").value(today.toString()));
  }

  @Test
  void futureMonth_isEmpty() throws Exception {
    usage(adminId, YearMonth.now(KST).plusMonths(1).toString())
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.daily", hasSize(0)))
        .andExpect(jsonPath("$.total.costUsd").value(0))
        .andExpect(jsonPath("$.total.tokens").value(0))
        .andExpect(jsonPath("$.total.runCount").value(0));
  }

  /** 완료 기준: 실험 1회 뒤 사용량의 비용이 는다. AI 모듈이 회차에 쓰는 누적 비용은 SQL 로 흉내 낸다. */
  @Test
  void costIncreases_afterOneExperiment() throws Exception {
    JsonNode before = usageBody();

    long runId = requestExperiment();
    jdbcTemplate.update("UPDATE runs SET status = 'done', tokens = 4321, cost_usd = 0.0789 WHERE run_id = ?", runId);
    JsonNode after = usageBody();

    assertThat(after.at("/total/costUsd").decimalValue().subtract(before.at("/total/costUsd").decimalValue()))
        .isEqualByComparingTo(new BigDecimal("0.0789"));
    assertThat(after.at("/total/tokens").asLong() - before.at("/total/tokens").asLong()).isEqualTo(4321);
    assertThat(after.at("/total/runCount").asLong() - before.at("/total/runCount").asLong()).isEqualTo(1);
    JsonNode todayBefore = before.get("daily").get(before.get("daily").size() - 1);
    JsonNode todayAfter = after.get("daily").get(after.get("daily").size() - 1);
    assertThat(todayAfter.get("date").asText()).isEqualTo(LocalDate.now(KST).toString());
    assertThat(todayAfter.get("costUsd").decimalValue().subtract(todayBefore.get("costUsd").decimalValue()))
        .isEqualByComparingTo(new BigDecimal("0.0789"));
  }

  @ParameterizedTest(name = "month={0} → GLB-ERR-001")
  @ValueSource(strings = {"2026-13", "202610", "2026-1", "2026-10-01", "abc"})
  void invalidMonth_isBadRequest(String month) throws Exception {
    usage(adminId, month)
        .andExpect(status().isBadRequest())
        .andExpect(jsonPath("$.code").value("GLB-ERR-001"));
  }

  @Test
  void maintainer_canRead_researcherIsForbidden_withoutTokenIsUnauthorized() throws Exception {
    Long maintainer = insertUser("usage-maintainer@uxight.com", "maintainer");
    usage(maintainer, "2001-03").andExpect(status().isOk());
    usage(researcherId, "2001-03")
        .andExpect(status().isForbidden())
        .andExpect(jsonPath("$.code").value("AUT-ERR-006"));
    mvc.perform(get("/api/admin/usage"))
        .andExpect(status().isUnauthorized())
        .andExpect(jsonPath("$.code").value("AUT-ERR-001"));
  }

  private ResultActions usage(Long userId, String month) throws Exception {
    var request = get("/api/admin/usage").header(HttpHeaders.AUTHORIZATION, "Bearer " + jwtProvider.createAccessToken(userId));
    if (month != null) {
      request.param("month", month);
    }
    return mvc.perform(request);
  }

  private JsonNode usageBody() throws Exception {
    return objectMapper.readTree(usage(adminId, null).andExpect(status().isOk()).andReturn().getResponse().getContentAsString());
  }

  private long requestExperiment() throws Exception {
    jdbcTemplate.update("INSERT INTO personas (user_id, name, profile) VALUES (?, 'p', JSON_OBJECT('webSkill', 'low'))",
        researcherId);
    Long personaId = jdbcTemplate.queryForObject("SELECT LAST_INSERT_ID()", Long.class);
    String body = mvc.perform(post("/api/projects/{projectId}/runs", projectId)
            .header(HttpHeaders.AUTHORIZATION, "Bearer " + jwtProvider.createAccessToken(researcherId))
            .contentType(MediaType.APPLICATION_JSON)
            .content("{\"goal\":\"g\",\"successUrl\":\"https://a.example.com/done\",\"personaIds\":[" + personaId
                + "],\"mode\":\"diagnose\"}"))
        .andExpect(status().isCreated())
        .andReturn().getResponse().getContentAsString();
    entityManager.flush();
    return objectMapper.readTree(body).get("runId").asLong();
  }

  private Long insertUser(String email, String role) {
    jdbcTemplate.update("INSERT INTO users (email, password_hash, auth_provider, name, role, is_active) "
        + "VALUES (?, 'hash', 'local', '사용량', ?, TRUE)", email, role);
    return jdbcTemplate.queryForObject("SELECT user_id FROM users WHERE email = ?", Long.class, email);
  }

  private Long insertProject(Long ownerId) {
    jdbcTemplate.update("INSERT INTO projects (user_id, title, target_url, allowed_domains) "
        + "VALUES (?, 'p', 'https://a.example.com', JSON_ARRAY('a.example.com'))", ownerId);
    return jdbcTemplate.queryForObject("SELECT LAST_INSERT_ID()", Long.class);
  }

  private void insertRun(Long project, String status, Long tokens, String costUsd, String createdAt) {
    jdbcTemplate.update("INSERT INTO tasks (project_id, goal, success_rule, success_url) "
        + "VALUES (?, 'g', 'rule', 'https://a.example.com/done')", project);
    Long taskId = jdbcTemplate.queryForObject("SELECT LAST_INSERT_ID()", Long.class);
    jdbcTemplate.update("INSERT INTO runs (project_id, task_id, mode, target_url_snapshot, allowed_domains_snapshot, "
            + "task_snapshot, policy_snapshot, persona_snapshot, status, tokens, cost_usd, created_at) "
            + "VALUES (?, ?, 'diagnose', 'https://a.example.com', JSON_ARRAY(), JSON_OBJECT(), JSON_OBJECT(), JSON_ARRAY(), "
            + "?, ?, ?, ?)",
        project, taskId, status, tokens, costUsd == null ? null : new BigDecimal(costUsd), createdAt);
  }
}
