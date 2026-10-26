package com.uxight.api.web.run;

import static org.hamcrest.Matchers.hasSize;
import static org.hamcrest.Matchers.nullValue;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

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
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.ResultActions;
import org.springframework.transaction.annotation.Transactional;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;

/**
 * 회차 Persona 진행 · step 로그 · 스크린샷 — 리서처(/api/runs/...)와 운영자(/api/admin/runs/...)가 같은 읽기 코드를 쓰고 권한만 다르다.
 * 실제 MySQL(테스트마다 롤백) + 임시 폴더를 agent 로그 루트(uxight.run-log-dir)로 쓴다.
 */
@SpringBootTest
@AutoConfigureMockMvc
@Transactional
class RunLogControllerTest {

  private static final Path RUN_LOG_ROOT;

  static {
    try {
      RUN_LOG_ROOT = Files.createTempDirectory("uxight-runs-");
    } catch (IOException e) {
      throw new IllegalStateException(e);
    }
  }

  @DynamicPropertySource
  static void runLogDir(DynamicPropertyRegistry registry) {
    registry.add("uxight.run-log-dir", RUN_LOG_ROOT::toString);
  }

  // 행동 로그 명세 3절 형식의 한 줄
  private static final String SPEC_LINE = """
      {"run_id":1,"persona_id":1,"step":1,"ts":"2026-10-27T10:00:01.123+09:00","url":"https://shop.example.com/",\
      "observation":{"mode":"som","screenshot":"1/1/step-1.png","elements_hash":"h","element_count":12},\
      "reasoning":"장바구니 버튼을 찾는다","action":{"kind":"type","target":7,"text":"****","direction":null},\
      "result":{"ok":false,"url_after":"https://shop.example.com/cart","error":"요소 없음","error_code":"ELEMENT_NOT_FOUND"},\
      "blocked":{"is":true,"reason":"domain"},"latency_ms":{"llm":900,"browser":0},"tokens":{"prompt":10,"completion":3},\
      "model":"m","task":{"url_reached":true}}""";
  // 지금 agent(Walking Skeleton)의 한 줄 — 명세의 칸이 없다
  private static final String SKELETON_LINE = """
      {"run_id":1,"persona_id":1,"step":2,"started_at":"2026-10-27T10:00:02","url":"https://shop.example.com/cart",\
      "element_count":3,"action":{"kind":"click","element_id":"e1","value":null},"result":{"ok":true}}""";
  private static final byte[] PNG = {(byte) 0x89, 'P', 'N', 'G', 13, 10, 26, 10, 1, 2, 3};

  @Autowired
  private MockMvc mvc;

  @Autowired
  private JwtProvider jwtProvider;

  @Autowired
  private JdbcTemplate jdbcTemplate;

  private Long researcherId;
  private Long projectId;
  private Long personaA;
  private Long personaB;
  private Long runId;

  @BeforeEach
  void setUp() {
    researcherId = insertUser("runlog-researcher@uxight.com", "researcher");
    projectId = insertProject(researcherId);
    personaA = insertPersona(researcherId, "쇼핑 초보");
    personaB = insertPersona(researcherId, "숙련자");
    runId = insertRun(projectId, "queued", personaA, personaB);
  }

  // ───────── GET /api/runs/{runId}/personas ─────────

  @Test
  void personas_beforeAcceptance_namesInSnapshotOrder_statusNull() throws Exception {
    researcher(get("/api/runs/{runId}/personas", runId))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.*", hasSize(3)))
        .andExpect(jsonPath("$.runId").value(runId))
        .andExpect(jsonPath("$.status").value("queued"))
        .andExpect(jsonPath("$.personas", hasSize(2)))
        .andExpect(jsonPath("$.personas[0].*", hasSize(5)))
        .andExpect(jsonPath("$.personas[0].personaId").value(personaA))
        .andExpect(jsonPath("$.personas[0].name").value("쇼핑 초보"))
        .andExpect(jsonPath("$.personas[0].status").value(nullValue()))
        .andExpect(jsonPath("$.personas[0].steps").value(nullValue()))
        .andExpect(jsonPath("$.personas[0].finishedAt").value(nullValue()))
        .andExpect(jsonPath("$.personas[1].name").value("숙련자"));
  }

  @Test
  void personas_afterAcceptance_haveStatusStepsAndFinishedAt() throws Exception {
    jdbcTemplate.update("UPDATE runs SET status = 'running' WHERE run_id = ?", runId);
    insertRunPersona(runId, personaA, "done", 4, "2026-10-27 10:01:00");
    insertRunPersona(runId, personaB, "running", 2, null);

    researcher(get("/api/runs/{runId}/personas", runId))
        .andExpect(jsonPath("$.status").value("running"))
        .andExpect(jsonPath("$.personas[0].status").value("done"))
        .andExpect(jsonPath("$.personas[0].steps").value(4))
        .andExpect(jsonPath("$.personas[0].finishedAt").value("2026-10-27T10:01:00"))
        .andExpect(jsonPath("$.personas[1].status").value("running"))
        .andExpect(jsonPath("$.personas[1].steps").value(2))
        .andExpect(jsonPath("$.personas[1].finishedAt").value(nullValue()));
  }

  // ───────── 권한 ─────────

  @Test
  void othersRun_deletedProjectsRun_andMissingRun_areAllRunNotFound_onEveryResearcherEndpoint() throws Exception {
    writeSteps(runId, personaA, SPEC_LINE + "\n");
    writeScreenshot(runId, personaA, 1);
    Long other = insertUser("runlog-other@uxight.com", "researcher");
    for (String path : researcherPaths(runId, personaA)) {
      as(other, get(path)).andExpect(status().isNotFound()).andExpect(jsonPath("$.code").value("EXP-ERR-002"));
    }
    for (String path : researcherPaths(999_999_999L, personaA)) {
      researcher(get(path)).andExpect(status().isNotFound()).andExpect(jsonPath("$.code").value("EXP-ERR-002"));
    }
    jdbcTemplate.update("UPDATE projects SET deleted_at = NOW() WHERE project_id = ?", projectId);
    for (String path : researcherPaths(runId, personaA)) {
      researcher(get(path)).andExpect(status().isNotFound()).andExpect(jsonPath("$.code").value("EXP-ERR-002"));
    }
  }

  @Test
  void withoutToken_isUnauthorized() throws Exception {
    mvc.perform(get("/api/runs/{runId}/personas", runId))
        .andExpect(status().isUnauthorized())
        .andExpect(jsonPath("$.code").value("AUT-ERR-001"));
  }

  // ───────── step 로그 ─────────

  @Test
  void steps_specFormat_isConvertedToCamelCase_withOnlyNeededKeys() throws Exception {
    writeSteps(runId, personaA, SPEC_LINE + "\n");

    researcher(get("/api/runs/{runId}/personas/{personaId}/steps", runId, personaA))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.*", hasSize(1)))
        .andExpect(jsonPath("$.steps", hasSize(1)))
        .andExpect(jsonPath("$.steps[0].*", hasSize(10)))   // observation · latency · tokens · model 은 내보내지 않는다
        .andExpect(jsonPath("$.steps[0].step").value(1))
        .andExpect(jsonPath("$.steps[0].ts").value("2026-10-27T10:00:01.123+09:00"))
        .andExpect(jsonPath("$.steps[0].url").value("https://shop.example.com/"))
        .andExpect(jsonPath("$.steps[0].reasoning").value("장바구니 버튼을 찾는다"))
        .andExpect(jsonPath("$.steps[0].action.kind").value("type"))
        .andExpect(jsonPath("$.steps[0].action.target").value(7))
        .andExpect(jsonPath("$.steps[0].action.text").value("****"))
        .andExpect(jsonPath("$.steps[0].action.direction").value(nullValue()))
        .andExpect(jsonPath("$.steps[0].result.ok").value(false))
        .andExpect(jsonPath("$.steps[0].result.urlAfter").value("https://shop.example.com/cart"))
        .andExpect(jsonPath("$.steps[0].result.error").value("요소 없음"))
        .andExpect(jsonPath("$.steps[0].result.errorCode").value("ELEMENT_NOT_FOUND"))
        .andExpect(jsonPath("$.steps[0].blocked").value(true))
        .andExpect(jsonPath("$.steps[0].blockedReason").value("domain"))
        .andExpect(jsonPath("$.steps[0].urlReached").value(true))
        .andExpect(jsonPath("$.steps[0].hasScreenshot").value(true));
  }

  @Test
  void steps_skeletonFormatWithoutSpecKeys_isNullOrFalse() throws Exception {
    writeSteps(runId, personaA, SKELETON_LINE + "\n");

    researcher(get("/api/runs/{runId}/personas/{personaId}/steps", runId, personaA))
        .andExpect(jsonPath("$.steps[0].step").value(2))
        .andExpect(jsonPath("$.steps[0].ts").value(nullValue()))
        .andExpect(jsonPath("$.steps[0].reasoning").value(nullValue()))
        .andExpect(jsonPath("$.steps[0].action.kind").value("click"))
        .andExpect(jsonPath("$.steps[0].action.target").value(nullValue()))
        .andExpect(jsonPath("$.steps[0].result.ok").value(true))
        .andExpect(jsonPath("$.steps[0].result.urlAfter").value(nullValue()))
        .andExpect(jsonPath("$.steps[0].blocked").value(false))
        .andExpect(jsonPath("$.steps[0].blockedReason").value(nullValue()))
        .andExpect(jsonPath("$.steps[0].urlReached").value(nullValue()))
        .andExpect(jsonPath("$.steps[0].hasScreenshot").value(false));
  }

  @Test
  void steps_skipLineBeingWritten_andUnreadableLines() throws Exception {
    // 깨진 줄 · 빈 줄은 건너뛰고, 줄바꿈으로 끝나지 않은 마지막 줄은 agent 가 쓰는 중이라 건너뛴다
    writeSteps(runId, personaA, SPEC_LINE + "\n{not json\n\n" + SKELETON_LINE + "\n" + "{\"step\":3,\"url\":\"https://sh");

    researcher(get("/api/runs/{runId}/personas/{personaId}/steps", runId, personaA))
        .andExpect(jsonPath("$.steps", hasSize(2)))
        .andExpect(jsonPath("$.steps[0].step").value(1))
        .andExpect(jsonPath("$.steps[1].step").value(2));
  }

  @Test
  void steps_noFileYet_isEmpty_whileNotStartedOrRunning() throws Exception {
    researcher(get("/api/runs/{runId}/personas/{personaId}/steps", runId, personaA))   // 접수 전
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.steps", hasSize(0)));
    insertRunPersona(runId, personaA, "running", 0, null);
    researcher(get("/api/runs/{runId}/personas/{personaId}/steps", runId, personaA))   // 실행 중, 첫 줄 전
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.steps", hasSize(0)));
  }

  @Test
  void steps_finishedButNoFile_orPersonaNotInRun_isLogNotFound() throws Exception {
    insertRunPersona(runId, personaA, "done", 3, "2026-10-27 10:01:00");
    researcher(get("/api/runs/{runId}/personas/{personaId}/steps", runId, personaA))
        .andExpect(status().isNotFound())
        .andExpect(jsonPath("$.code").value("LOG-ERR-001"));
    Long notInRun = insertPersona(researcherId, "다른 Persona");
    researcher(get("/api/runs/{runId}/personas/{personaId}/steps", runId, notInRun))
        .andExpect(status().isNotFound())
        .andExpect(jsonPath("$.code").value("LOG-ERR-001"));
  }

  // ───────── 스크린샷 ─────────

  @Test
  void screenshot_isPngBytes_withPrivateOneDayCache() throws Exception {
    writeScreenshot(runId, personaA, 1);

    researcher(get("/api/runs/{runId}/personas/{personaId}/steps/{step}/screenshot", runId, personaA, 1))
        .andExpect(status().isOk())
        .andExpect(content().contentType(MediaType.IMAGE_PNG))
        .andExpect(header().string(HttpHeaders.CACHE_CONTROL, "max-age=86400, private"))
        .andExpect(content().bytes(PNG));
  }

  @ParameterizedTest(name = "step={0} → LOG-ERR-002")
  @ValueSource(ints = {2, 0, -1})
  void screenshot_missingStep_isScreenshotNotFound(int step) throws Exception {
    writeScreenshot(runId, personaA, 1);
    researcher(get("/api/runs/{runId}/personas/{personaId}/steps/{step}/screenshot", runId, personaA, step))
        .andExpect(status().isNotFound())
        .andExpect(jsonPath("$.code").value("LOG-ERR-002"));
  }

  @Test
  void screenshot_personaNotInRun_isScreenshotNotFound_andNonNumericStepIsBadRequest() throws Exception {
    Long notInRun = insertPersona(researcherId, "다른 Persona");
    writeScreenshot(runId, notInRun, 1);   // 파일이 있어도 그 회차의 Persona 가 아니면 보이지 않는다
    researcher(get("/api/runs/{runId}/personas/{personaId}/steps/{step}/screenshot", runId, notInRun, 1))
        .andExpect(status().isNotFound())
        .andExpect(jsonPath("$.code").value("LOG-ERR-002"));
    researcher(get("/api/runs/" + runId + "/personas/" + personaA + "/steps/abc/screenshot"))
        .andExpect(status().isBadRequest())
        .andExpect(jsonPath("$.code").value("GLB-ERR-001"));
  }

  // ───────── 운영자 ─────────

  @ParameterizedTest(name = "{0} 은 남의 · 삭제된 프로젝트의 회차도 본다")
  @ValueSource(strings = {"admin", "maintainer"})
  void adminOrMaintainer_readsAnyRun_withSameReader(String role) throws Exception {
    Long operator = insertUser("runlog-" + role + "@uxight.com", role);
    writeSteps(runId, personaA, SPEC_LINE + "\n");
    writeScreenshot(runId, personaA, 1);
    jdbcTemplate.update("UPDATE projects SET deleted_at = NOW() WHERE project_id = ?", projectId);

    as(operator, get("/api/admin/runs/{runId}/personas/{personaId}/steps", runId, personaA))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.steps[0].result.errorCode").value("ELEMENT_NOT_FOUND"));
    as(operator, get("/api/admin/runs/{runId}/personas/{personaId}/steps/{step}/screenshot", runId, personaA, 1))
        .andExpect(status().isOk())
        .andExpect(content().contentType(MediaType.IMAGE_PNG))
        .andExpect(header().string(HttpHeaders.CACHE_CONTROL, "max-age=86400, private"))
        .andExpect(content().bytes(PNG));
    as(operator, get("/api/admin/runs/{runId}/personas/{personaId}/steps", 999_999_999L, personaA))
        .andExpect(status().isNotFound())
        .andExpect(jsonPath("$.code").value("EXP-ERR-002"));
    as(operator, get("/api/admin/runs/{runId}/personas/{personaId}/steps/{step}/screenshot", runId, personaA, 5))
        .andExpect(status().isNotFound())
        .andExpect(jsonPath("$.code").value("LOG-ERR-002"));
  }

  @Test
  void researcher_onAdminPath_isForbidden_evenForOwnRun() throws Exception {
    writeSteps(runId, personaA, SPEC_LINE + "\n");
    researcher(get("/api/admin/runs/{runId}/personas/{personaId}/steps", runId, personaA))
        .andExpect(status().isForbidden())
        .andExpect(jsonPath("$.code").value("AUT-ERR-006"));
  }

  // ───────── 도우미 ─────────

  private String[] researcherPaths(Long run, Long persona) {
    return new String[] {
        "/api/runs/" + run + "/personas",
        "/api/runs/" + run + "/personas/" + persona + "/steps",
        "/api/runs/" + run + "/personas/" + persona + "/steps/1/screenshot"};
  }

  private ResultActions researcher(org.springframework.test.web.servlet.request.MockHttpServletRequestBuilder request)
      throws Exception {
    return as(researcherId, request);
  }

  private ResultActions as(Long userId, org.springframework.test.web.servlet.request.MockHttpServletRequestBuilder request)
      throws Exception {
    return mvc.perform(request.header(HttpHeaders.AUTHORIZATION, "Bearer " + jwtProvider.createAccessToken(userId)));
  }

  private void writeSteps(Long run, Long persona, String content) throws IOException {
    Path dir = Files.createDirectories(RUN_LOG_ROOT.resolve(run.toString()).resolve(persona.toString()));
    Files.writeString(dir.resolve("steps.jsonl"), content, StandardCharsets.UTF_8);
  }

  private void writeScreenshot(Long run, Long persona, int step) throws IOException {
    Path dir = Files.createDirectories(RUN_LOG_ROOT.resolve(run.toString()).resolve(persona.toString()));
    Files.write(dir.resolve("step-" + step + ".png"), PNG);
  }

  private Long insertUser(String email, String role) {
    jdbcTemplate.update("INSERT INTO users (email, password_hash, auth_provider, name, role, is_active) "
        + "VALUES (?, 'hash', 'local', '로그', ?, TRUE)", email, role);
    return jdbcTemplate.queryForObject("SELECT user_id FROM users WHERE email = ?", Long.class, email);
  }

  private Long insertProject(Long ownerId) {
    jdbcTemplate.update("INSERT INTO projects (user_id, title, target_url, allowed_domains) "
        + "VALUES (?, 'p', 'https://shop.example.com', JSON_ARRAY('shop.example.com'))", ownerId);
    return jdbcTemplate.queryForObject("SELECT LAST_INSERT_ID()", Long.class);
  }

  private Long insertPersona(Long ownerId, String name) {
    jdbcTemplate.update("INSERT INTO personas (user_id, name, profile) VALUES (?, ?, JSON_OBJECT('webSkill', 'low'))",
        ownerId, name);
    return jdbcTemplate.queryForObject("SELECT LAST_INSERT_ID()", Long.class);
  }

  private Long insertRun(Long project, String status, Long firstPersona, Long secondPersona) {
    jdbcTemplate.update("INSERT INTO tasks (project_id, goal, success_rule, success_url) "
        + "VALUES (?, 'g', 'rule', 'https://shop.example.com/done')", project);
    Long taskId = jdbcTemplate.queryForObject("SELECT LAST_INSERT_ID()", Long.class);
    jdbcTemplate.update("INSERT INTO runs (project_id, task_id, mode, target_url_snapshot, allowed_domains_snapshot, "
            + "task_snapshot, policy_snapshot, persona_snapshot, status) "
            + "VALUES (?, ?, 'diagnose', 'https://shop.example.com', JSON_ARRAY(), JSON_OBJECT(), JSON_OBJECT(), "
            + "JSON_ARRAY(JSON_OBJECT('persona_id', ?, 'name', '쇼핑 초보', 'profile', JSON_OBJECT()), "
            + "JSON_OBJECT('persona_id', ?, 'name', '숙련자', 'profile', JSON_OBJECT())), ?)",
        project, taskId, firstPersona, secondPersona, status);
    return jdbcTemplate.queryForObject("SELECT LAST_INSERT_ID()", Long.class);
  }

  private void insertRunPersona(Long run, Long persona, String status, int steps, String finishedAt) {
    jdbcTemplate.update("INSERT INTO run_personas (run_id, persona_id, status, steps, log_path, started_at, finished_at) "
        + "VALUES (?, ?, ?, ?, CONCAT(?, '/', ?, '/steps.jsonl'), NOW(), ?)", run, persona, status, steps, run, persona,
        finishedAt);
  }
}
