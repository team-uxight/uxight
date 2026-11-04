package com.uxight.api.web.result;

import static org.assertj.core.api.Assertions.assertThat;
import static org.hamcrest.Matchers.contains;
import static org.hamcrest.Matchers.empty;
import static org.hamcrest.Matchers.hasSize;
import static org.hamcrest.Matchers.nullValue;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.uxight.api.domain.run.AgentClient;
import com.uxight.api.domain.user.JwtProvider;
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
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.ResultActions;
import org.springframework.test.web.servlet.request.MockHttpServletRequestBuilder;
import org.springframework.transaction.annotation.Transactional;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Optional;
import java.util.concurrent.CompletableFuture;

/**
 * 결과 조회 · 결과 스크린샷 — 최초 회차(Before)와 마지막 done 회차(After) 비교 (design-decision 2.4).
 * 실제 MySQL, 테스트마다 롤백. 로컬 seed(R__seed_local_improvements · R__seed_local_comparison)로 완료 기준을 보고,
 * 조건별 동작은 테스트가 넣은 회차로 본다. step 로그 · 스크린샷 파일은 임시 폴더(uxight.run-log-dir)에 쓴다.
 */
@SpringBootTest
@AutoConfigureMockMvc
@Transactional
class ComparisonControllerTest {

  private static final long SEED_USER_ID = 1L;   // test@uxight.com (R__seed_local)
  private static final byte[] PNG = {(byte) 0x89, 'P', 'N', 'G', 13, 10, 26, 10, 7, 7};
  private static final String CART = "https://shop.example.com/cart";
  private static final String HOME = "https://shop.example.com/";
  private static final Path RUN_LOG_ROOT;

  static {
    try {
      RUN_LOG_ROOT = Files.createTempDirectory("uxight-comparison-runs-");
    } catch (IOException e) {
      throw new IllegalStateException(e);
    }
  }

  @DynamicPropertySource
  static void runLogDir(DynamicPropertyRegistry registry) {
    registry.add("uxight.run-log-dir", RUN_LOG_ROOT::toString);
  }

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

  private Long researcherId;
  private Long projectId;
  private Long persona1;
  private Long persona2;

  @BeforeEach
  void setUp() {
    when(agentClient.dispatch(anyLong())).thenReturn(CompletableFuture.completedFuture(Optional.empty()));
    researcherId = insertUser("comparison-researcher@uxight.com");
    projectId = insertProject(researcherId);
    persona1 = insertPersona("초보");
    persona2 = insertPersona("숙련");
  }

  // ───────── 완료 기준 ─────────

  /** 시드 개선안 하나를 승인하면 다음 회차가 queued 로 생기고, 그 회차가 끝나면 비교 API 가 두 회차 지표를 나란히 낸다. */
  @Test
  void seedImprovement_approve_nextRoundQueued_thenDone_comparisonHasBothRoundsMetrics() throws Exception {
    long seedRun = seedRunId("[seed] 개선안 예시 쇼핑몰");
    long option1 = jdbcTemplate.queryForObject(
        "SELECT improvement_id FROM improvements WHERE run_id = ? AND option_no = 1", Long.class, seedRun);

    String response = as(SEED_USER_ID, post("/api/runs/{runId}/approvals", seedRun)
            .contentType(MediaType.APPLICATION_JSON)
            .content("{\"improvementId\": " + option1 + ", \"decision\": \"approve\"}"))
        .andExpect(status().isCreated())
        .andReturn().getResponse().getContentAsString();
    long nextRun = objectMapper.readTree(response).get("runId").asLong();
    assertThat(
        jdbcTemplate.queryForObject("SELECT status FROM runs WHERE run_id = ?", String.class, nextRun)).isEqualTo("queued");

    // 2회차가 아직 끝나지 않았으면 After 는 없다
    as(SEED_USER_ID, get("/api/runs/{firstRunId}/comparison", seedRun))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.experiment.state").value("in_progress"))
        .andExpect(jsonPath("$.after").value(nullValue()));

    // AI 모듈 대신 — 2회차 종료 · 지표 확정 · 1안 패치 주입 기록
    jdbcTemplate.update("UPDATE runs SET status = 'done', finished_at = NOW() WHERE run_id = ?", nextRun);
    jdbcTemplate.update("INSERT INTO run_metrics (run_id, success_rate, avg_steps, avg_backtracks, avg_seconds, tokens, cost_usd) "
        + "VALUES (?, 100.00, 6.00, 0.00, 150.00, 2600, 0.0260)", nextRun);
    jdbcTemplate.update("INSERT INTO patch_versions (run_id, improvement_id, patch_kind, patch, applied) "
        + "VALUES (?, ?, 'relabel', JSON_OBJECT('target', '#coupon-apply'), TRUE)", nextRun, option1);

    as(SEED_USER_ID, get("/api/runs/{firstRunId}/comparison", seedRun))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.before.runId").value(seedRun))
        .andExpect(jsonPath("$.before.metrics.successRate").value(0.0))
        .andExpect(jsonPath("$.before.metrics.avgSteps").value(10.0))
        .andExpect(jsonPath("$.before.metrics.tokens").value(3800))
        .andExpect(jsonPath("$.after.runId").value(nextRun))
        .andExpect(jsonPath("$.after.round").value(2))
        .andExpect(jsonPath("$.after.metrics.successRate").value(100.0))
        .andExpect(jsonPath("$.after.metrics.avgSteps").value(6.0))
        .andExpect(jsonPath("$.after.metrics.tokens").value(2600))
        .andExpect(jsonPath("$.patches", hasSize(1)))
        .andExpect(jsonPath("$.patches[0].round").value(2))
        .andExpect(jsonPath("$.patches[0].patchKind").value("relabel"))
        .andExpect(jsonPath("$.patches[0].applied").value(true));
  }

  /** 결과 비교 seed — 명세의 응답 모양. 로그 파일이 없어 스크린샷 목록은 비어 있다. */
  @Test
  void seedComparison_inSpecShape() throws Exception {
    long seedRun = seedRunId("[seed] 결과 비교 예시 쇼핑몰");
    long secondRun = jdbcTemplate.queryForObject("SELECT MAX(run_id) FROM runs WHERE first_run_id = ?", Long.class, seedRun);

    as(SEED_USER_ID, get("/api/runs/{firstRunId}/comparison", seedRun))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.*", hasSize(4)))
        .andExpect(jsonPath("$.experiment.*", hasSize(4)))
        .andExpect(jsonPath("$.experiment.projectTitle").value("[seed] 결과 비교 예시 쇼핑몰"))
        .andExpect(jsonPath("$.experiment.taskGoal").value("쿠폰을 적용해 결제 페이지까지 간다"))
        .andExpect(jsonPath("$.experiment.mode").value("loop"))
        .andExpect(jsonPath("$.experiment.state").value("completed"))
        .andExpect(jsonPath("$.before.*", hasSize(3)))
        .andExpect(jsonPath("$.before.runId").value(seedRun))
        .andExpect(jsonPath("$.before.metrics.*", hasSize(6)))
        .andExpect(jsonPath("$.before.metrics.successRate").value(0.0))
        .andExpect(jsonPath("$.before.metrics.avgBacktracks").value(2.0))
        .andExpect(jsonPath("$.before.metrics.avgSeconds").value(240.0))
        .andExpect(jsonPath("$.before.metrics.costUsd").value(0.038))
        .andExpect(jsonPath("$.before.screenshots", empty()))
        .andExpect(jsonPath("$.after.*", hasSize(4)))
        .andExpect(jsonPath("$.after.runId").value(secondRun))
        .andExpect(jsonPath("$.after.round").value(2))
        .andExpect(jsonPath("$.after.metrics.successRate").value(100.0))
        .andExpect(jsonPath("$.after.metrics.avgBacktracks").value(0.0))
        .andExpect(jsonPath("$.after.screenshots", empty()))
        .andExpect(jsonPath("$.patches", hasSize(1)))
        .andExpect(jsonPath("$.patches[0].*", hasSize(3)))
        .andExpect(jsonPath("$.patches[0].round").value(2))
        .andExpect(jsonPath("$.patches[0].patchKind").value("relabel"))
        .andExpect(jsonPath("$.patches[0].applied").value(true));
  }

  // ───────── Before · After 고르기 ─────────

  @Test
  void onlyFirstRoundDone_afterIsNull_metricsWithoutRowAreAllNull() throws Exception {
    long first = insertRun("done", null, null);

    as(researcherId, get("/api/runs/{firstRunId}/comparison", first))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.*", hasSize(4)))   // after 칸은 null 로 있다
        .andExpect(jsonPath("$.after").value(nullValue()))
        .andExpect(jsonPath("$.experiment.state").value("completed"))
        .andExpect(jsonPath("$.before.runId").value(first))
        .andExpect(jsonPath("$.before.metrics.*", hasSize(6)))
        .andExpect(jsonPath("$.before.metrics.successRate").value(nullValue()))
        .andExpect(jsonPath("$.before.metrics.tokens").value(nullValue()))
        .andExpect(jsonPath("$.before.screenshots", empty()))
        .andExpect(jsonPath("$.patches", empty()));
  }

  @Test
  void runningExperiment_afterIsLatestDoneRound_andPatchesOfEveryRoundInOrder() throws Exception {
    long first = insertRun("done", null, null);
    long improvement1 = insertImprovement(first, "[]");
    long second = insertRun("done", first, improvement1);
    long improvement2 = insertImprovement(second, "[]");
    long third = insertRun("running", first, improvement2);
    insertPatchVersion(second, improvement1, "relabel", true);
    insertPatchVersion(third, improvement1, "relabel", true);    // 이전 회차 패치까지 누적 주입
    insertPatchVersion(third, improvement2, "highlight", false);

    as(researcherId, get("/api/runs/{firstRunId}/comparison", first))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.experiment.state").value("in_progress"))
        .andExpect(jsonPath("$.after.runId").value(second))
        .andExpect(jsonPath("$.after.round").value(2))
        .andExpect(jsonPath("$.patches[*].round").value(contains(2, 3, 3)))
        .andExpect(jsonPath("$.patches[*].patchKind").value(contains("relabel", "relabel", "highlight")))
        .andExpect(jsonPath("$.patches[*].applied").value(contains(true, true, false)));
  }

  @Test
  void failedSecondRound_afterIsNull() throws Exception {
    long first = insertRun("done", null, null);
    insertRun("failed", first, insertImprovement(first, "[]"));

    as(researcherId, get("/api/runs/{firstRunId}/comparison", first))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.experiment.state").value("stopped"))
        .andExpect(jsonPath("$.after").value(nullValue()));
  }

  // ───────── 스크린샷 — 패치가 들어간 페이지 ─────────

  @Test
  void screenshots_areFirstStepOnPatchedPage_perPersona_inBothRounds() throws Exception {
    long first = insertRun("done", null, null);
    long finding = insertFinding(first, CART);
    long second = insertRun("done", first, insertImprovement(first, "[" + finding + "]"));
    // Before: 초보는 3번째 step(2번째는 스크린샷 없음), 숙련은 로그가 없어 빠진다
    writeSteps(first, persona1, step(1, HOME, true), step(2, CART, false), step(3, CART, true), step(4, CART, true));
    // After: 초보는 2번째 step, 숙련은 1번째 step
    writeSteps(second, persona1, step(1, HOME, true), step(2, CART, true));
    writeSteps(second, persona2, step(1, CART, true));

    as(researcherId, get("/api/runs/{firstRunId}/comparison", first))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.before.screenshots", hasSize(1)))
        .andExpect(jsonPath("$.before.screenshots[0].*", hasSize(2)))
        .andExpect(jsonPath("$.before.screenshots[0].personaId").value(persona1))
        .andExpect(jsonPath("$.before.screenshots[0].step").value(3))
        .andExpect(jsonPath("$.after.screenshots[*].personaId").value(contains(persona1.intValue(), persona2.intValue())))
        .andExpect(jsonPath("$.after.screenshots[*].step").value(contains(2, 1)));
  }

  @Test
  void screenshots_patchOnPageNeverVisited_areEmpty() throws Exception {
    long first = insertRun("done", null, null);
    long finding = insertFinding(first, "https://shop.example.com/checkout");
    long second = insertRun("done", first, insertImprovement(first, "[" + finding + "]"));
    writeSteps(first, persona1, step(1, HOME, true), step(2, CART, true));
    writeSteps(second, persona1, step(1, HOME, true));

    as(researcherId, get("/api/runs/{firstRunId}/comparison", first))
        .andExpect(jsonPath("$.before.screenshots", empty()))
        .andExpect(jsonPath("$.after.screenshots", empty()));
  }

  @Test
  void screenshot_onlyWithinBeforeOrAfter() throws Exception {
    long first = insertRun("done", null, null);
    long finding = insertFinding(first, CART);
    long second = insertRun("done", first, insertImprovement(first, "[" + finding + "]"));
    writeSteps(first, persona1, step(1, HOME, true), step(2, CART, true), step(3, CART, true));
    writeSteps(second, persona1, step(1, CART, true));
    writeScreenshot(first, persona1, 2);
    writeScreenshot(first, persona1, 3);
    writeScreenshot(second, persona1, 1);

    shot(researcherId, first, first, persona1, 2)
        .andExpect(status().isOk())
        .andExpect(content().contentType(MediaType.IMAGE_PNG))
        .andExpect(header().string(HttpHeaders.CACHE_CONTROL, "max-age=86400, private"))
        .andExpect(content().bytes(PNG));
    shot(researcherId, first, second, persona1, 1)
        .andExpect(status().isOk())
        .andExpect(content().bytes(PNG));

    // 범위 밖은 파일이 있어도 404 — 고르지 않은 step, Before 의 step 을 After 회차로, 목록에 없는 Persona
    shot(researcherId, first, first, persona1, 3).andExpect(status().isNotFound())
        .andExpect(jsonPath("$.code").value("LOG-ERR-002"));
    shot(researcherId, first, second, persona1, 2).andExpect(status().isNotFound())
        .andExpect(jsonPath("$.code").value("LOG-ERR-002"));
    shot(researcherId, first, first, persona2, 2).andExpect(status().isNotFound())
        .andExpect(jsonPath("$.code").value("LOG-ERR-002"));
    // 범위 안이어도 파일이 없으면 404
    Files.delete(RUN_LOG_ROOT.resolve(Long.toString(second)).resolve(Long.toString(persona1)).resolve("step-1.png"));
    shot(researcherId, first, second, persona1, 1).andExpect(status().isNotFound())
        .andExpect(jsonPath("$.code").value("LOG-ERR-002"));
    // 파라미터 누락 · 숫자 아님
    as(researcherId, get("/api/runs/{firstRunId}/comparison/screenshots", first)
            .param("personaId", String.valueOf(persona1)).param("step", "2"))   // runId 없음
        .andExpect(status().isBadRequest())
        .andExpect(jsonPath("$.code").value("GLB-ERR-001"));
    as(researcherId, get("/api/runs/{firstRunId}/comparison/screenshots", first)
            .param("runId", String.valueOf(first)).param("personaId", String.valueOf(persona1)).param("step", "abc"))
        .andExpect(status().isBadRequest())
        .andExpect(jsonPath("$.code").value("GLB-ERR-001"));
  }

  // ───────── 409 · 404 ─────────

  @ParameterizedTest(name = "최초 회차 status {0} → 409 CMP-ERR-001, 스크린샷은 404 LOG-ERR-002")
  @ValueSource(strings = {"queued", "running", "failed", "cancelled"})
  void firstRoundNotDone_isConflict(String status) throws Exception {
    long first = insertRun(status, null, null);
    writeScreenshot(first, persona1, 1);

    as(researcherId, get("/api/runs/{firstRunId}/comparison", first))
        .andExpect(status().isConflict())
        .andExpect(jsonPath("$.code").value("CMP-ERR-001"));
    shot(researcherId, first, first, persona1, 1)
        .andExpect(status().isNotFound())
        .andExpect(jsonPath("$.code").value("LOG-ERR-002"));
  }

  @Test
  void othersExperiment_deletedProject_notFirstRound_andMissing_areExperimentNotFound() throws Exception {
    long first = insertRun("done", null, null);
    long second = insertRun("done", first, insertImprovement(first, "[]"));
    Long other = insertUser("comparison-other@uxight.com");

    for (ResultActions result : new ResultActions[] {
        as(other, get("/api/runs/{firstRunId}/comparison", first)),
        shot(other, first, first, persona1, 1),
        as(researcherId, get("/api/runs/{firstRunId}/comparison", second)),   // 최초 회차가 아닌 runId
        as(researcherId, get("/api/runs/{firstRunId}/comparison", 999_999_999L))}) {
      result.andExpect(status().isNotFound()).andExpect(jsonPath("$.code").value("EXP-ERR-001"));
    }

    jdbcTemplate.update("UPDATE projects SET deleted_at = NOW() WHERE project_id = ?", projectId);
    as(researcherId, get("/api/runs/{firstRunId}/comparison", first))
        .andExpect(status().isNotFound()).andExpect(jsonPath("$.code").value("EXP-ERR-001"));
  }

  @Test
  void withoutToken_isUnauthorized_andNonNumericId_isBadRequest() throws Exception {
    mvc.perform(get("/api/runs/1/comparison"))
        .andExpect(status().isUnauthorized())
        .andExpect(jsonPath("$.code").value("AUT-ERR-001"));
    as(researcherId, get("/api/runs/abc/comparison"))
        .andExpect(status().isBadRequest())
        .andExpect(jsonPath("$.code").value("GLB-ERR-001"));
  }

  // ───────── 도우미 ─────────

  private long seedRunId(String title) {
    return jdbcTemplate.queryForObject("SELECT MIN(r.run_id) FROM runs r JOIN projects p ON p.project_id = r.project_id "
        + "WHERE p.user_id = ? AND p.title = ?", Long.class, SEED_USER_ID, title);
  }

  private ResultActions shot(Long userId, long firstRunId, long runId, long persona, int step) throws Exception {
    return as(userId, get("/api/runs/{firstRunId}/comparison/screenshots", firstRunId)
        .param("runId", String.valueOf(runId)).param("personaId", String.valueOf(persona))
        .param("step", String.valueOf(step)));
  }

  private ResultActions as(Long userId, MockHttpServletRequestBuilder request) throws Exception {
    return mvc.perform(request.header(HttpHeaders.AUTHORIZATION, "Bearer " + jwtProvider.createAccessToken(userId)));
  }

  /** steps.jsonl 한 줄 — 행동 로그 명세의 snake_case 중 고르기에 쓰는 키만. */
  private static String step(int step, String url, boolean screenshot) {
    return "{\"step\":" + step + ",\"url\":\"" + url + "\""
        + (screenshot ? ",\"observation\":{\"screenshot\":\"step-" + step + ".png\"}" : "") + "}";
  }

  private void writeSteps(long runId, long persona, String... lines) throws IOException {
    Path dir = Files.createDirectories(RUN_LOG_ROOT.resolve(Long.toString(runId)).resolve(Long.toString(persona)));
    Files.writeString(dir.resolve("steps.jsonl"), String.join("\n", lines) + "\n", StandardCharsets.UTF_8);
  }

  private void writeScreenshot(long runId, long persona, int step) throws IOException {
    Path dir = Files.createDirectories(RUN_LOG_ROOT.resolve(Long.toString(runId)).resolve(Long.toString(persona)));
    Files.write(dir.resolve("step-" + step + ".png"), PNG);
  }

  private Long insertUser(String email) {
    jdbcTemplate.update("INSERT INTO users (email, password_hash, auth_provider, name, role, is_active) "
        + "VALUES (?, 'hash', 'local', '결과', 'researcher', TRUE)", email);
    return jdbcTemplate.queryForObject("SELECT user_id FROM users WHERE email = ?", Long.class, email);
  }

  private Long insertProject(Long ownerId) {
    jdbcTemplate.update("INSERT INTO projects (user_id, title, target_url, allowed_domains) "
        + "VALUES (?, '결과 몰', 'https://shop.example.com', JSON_ARRAY('shop.example.com'))", ownerId);
    return jdbcTemplate.queryForObject("SELECT LAST_INSERT_ID()", Long.class);
  }

  private Long insertPersona(String name) {
    jdbcTemplate.update("INSERT INTO personas (user_id, name, profile) VALUES (?, ?, JSON_OBJECT('webSkill', 'low'))",
        researcherId, name);
    return jdbcTemplate.queryForObject("SELECT LAST_INSERT_ID()", Long.class);
  }

  /**
   * firstRunId 가 null 이면 최초 회차, 아니면 그 실험의 다음 회차(직전 회차 = 그 실험의 가장 최근 회차, 적용 개선안 improvementId).
   * Persona 스냅샷은 초보 · 숙련 순.
   */
  private long insertRun(String status, Long firstRunId, Long improvementId) {
    jdbcTemplate.update("INSERT INTO tasks (project_id, goal, success_rule, success_url) "
        + "VALUES (?, '결제한다', 'rule', 'https://shop.example.com/done')", projectId);
    Long taskId = jdbcTemplate.queryForObject("SELECT LAST_INSERT_ID()", Long.class);
    Long parent = firstRunId == null ? null
        : jdbcTemplate.queryForObject("SELECT MAX(run_id) FROM runs WHERE first_run_id = ?", Long.class, firstRunId);
    jdbcTemplate.update("INSERT INTO runs (project_id, task_id, mode, loop_max, target_url_snapshot, allowed_domains_snapshot, "
            + "task_snapshot, policy_snapshot, persona_snapshot, status, parent_run_id, improvement_id) "
            + "VALUES (?, ?, 'loop', 3, 'https://shop.example.com', JSON_ARRAY(), JSON_OBJECT(), JSON_OBJECT(), "
            + "JSON_ARRAY(JSON_OBJECT('persona_id', ?, 'name', '초보'), JSON_OBJECT('persona_id', ?, 'name', '숙련')), ?, ?, ?)",
        projectId, taskId, persona1, persona2, status, parent, improvementId);
    long runId = jdbcTemplate.queryForObject("SELECT LAST_INSERT_ID()", Long.class);
    jdbcTemplate.update("UPDATE runs SET first_run_id = ? WHERE run_id = ?", firstRunId == null ? runId : firstRunId, runId);
    return runId;
  }

  private long insertFinding(long runId, String url) {
    jdbcTemplate.update("INSERT INTO findings (run_id, taxonomy, severity, evidence) VALUES (?, 'task_failure', 'high', "
        + "JSON_ARRAY(JSON_OBJECT('persona_id', ?, 'step_from', 1, 'step_to', 2, 'url', ?)))", runId, persona1, url);
    return jdbcTemplate.queryForObject("SELECT LAST_INSERT_ID()", Long.class);
  }

  private long insertImprovement(long runId, String findingIdsJson) {
    jdbcTemplate.update("INSERT INTO improvements (run_id, finding_ids, option_no, patch_kind, patch) "
        + "VALUES (?, ?, 1, 'relabel', JSON_OBJECT('target', '#btn'))", runId, findingIdsJson);
    return jdbcTemplate.queryForObject("SELECT LAST_INSERT_ID()", Long.class);
  }

  private void insertPatchVersion(long runId, long improvementId, String patchKind, boolean applied) {
    jdbcTemplate.update("INSERT INTO patch_versions (run_id, improvement_id, patch_kind, patch, applied) "
        + "VALUES (?, ?, ?, JSON_OBJECT(), ?)", runId, improvementId, patchKind, applied);
  }
}
