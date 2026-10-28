package com.uxight.api.web.finding;

import static org.hamcrest.Matchers.contains;
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
import org.springframework.test.web.servlet.request.MockHttpServletRequestBuilder;
import org.springframework.transaction.annotation.Transactional;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;

/**
 * 진단 목록 · 상세 · Taxonomy 분포 · 근거 스크린샷 — 본인 프로젝트의 done 회차만.
 * 실제 MySQL, 테스트마다 롤백. 로컬 seed(R__seed_local_findings — 테스트도 local 프로필)로 명세의 응답 모양을 보고,
 * 404 · 집계 조건은 테스트가 넣은 회차로 본다. 스크린샷 파일은 임시 폴더(uxight.run-log-dir)에 쓴다.
 */
@SpringBootTest
@AutoConfigureMockMvc
@Transactional
class FindingControllerTest {

  private static final long SEED_USER_ID = 1L;   // test@uxight.com (R__seed_local)
  private static final byte[] PNG = {(byte) 0x89, 'P', 'N', 'G', 13, 10, 26, 10, 4, 2};
  private static final Path RUN_LOG_ROOT;

  static {
    try {
      RUN_LOG_ROOT = Files.createTempDirectory("uxight-finding-runs-");
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

  private Long researcherId;
  private Long projectId;
  private Long personaId;

  @BeforeEach
  void setUp() {
    researcherId = insertUser("finding-researcher@uxight.com");
    projectId = insertProject(researcherId);
    jdbcTemplate.update("INSERT INTO personas (user_id, name, profile) VALUES (?, '초보', JSON_OBJECT('webSkill', 'low'))",
        researcherId);
    personaId = jdbcTemplate.queryForObject("SELECT LAST_INSERT_ID()", Long.class);
  }

  // ───────── 완료 기준: 시드한 회차로 명세의 응답 모양 ─────────

  @Test
  void seedRun_list_hasRoundInfoAndFindings_inSpecShape() throws Exception {
    long seedRun = seedRunId();

    as(SEED_USER_ID, get("/api/runs/{runId}/findings", seedRun))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.*", hasSize(2)))
        .andExpect(jsonPath("$.run.*", hasSize(5)))
        .andExpect(jsonPath("$.run.firstRunId").value(seedRun))
        .andExpect(jsonPath("$.run.round").value(1))
        .andExpect(jsonPath("$.run.projectTitle").value("[seed] 진단 예시 쇼핑몰"))
        .andExpect(jsonPath("$.run.taskGoal").value("상품을 장바구니에 담는다"))
        .andExpect(jsonPath("$.run.improvementCount").value(0))   // improvements 테이블 전
        .andExpect(jsonPath("$.findings", hasSize(3)))
        .andExpect(jsonPath("$.findings[0].*", hasSize(4)))
        .andExpect(jsonPath("$.findings[*].taxonomy").value(contains(
            "navigation_confusion", "interaction_failure", "task_failure")))   // 검출 순
        .andExpect(jsonPath("$.findings[0].severity").value("high"))
        .andExpect(jsonPath("$.findings[0].summary").isNotEmpty())
        .andExpect(jsonPath("$.findings[2].summary").value(nullValue()));   // 요약 단계 전
  }

  @Test
  void seedRun_detail_hasEvidenceInCamelCase_inSpecShape() throws Exception {
    long seedRun = seedRunId();
    long findingId = jdbcTemplate.queryForObject(
        "SELECT MIN(finding_id) FROM findings WHERE run_id = ?", Long.class, seedRun);
    long seedPersona = jdbcTemplate.queryForObject(
        "SELECT persona_id FROM run_personas WHERE run_id = ?", Long.class, seedRun);

    as(SEED_USER_ID, get("/api/findings/{findingId}", findingId))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.*", hasSize(6)))
        .andExpect(jsonPath("$.findingId").value(findingId))
        .andExpect(jsonPath("$.runId").value(seedRun))
        .andExpect(jsonPath("$.taxonomy").value("navigation_confusion"))
        .andExpect(jsonPath("$.severity").value("high"))
        .andExpect(jsonPath("$.summary").isNotEmpty())
        .andExpect(jsonPath("$.evidence", hasSize(1)))
        .andExpect(jsonPath("$.evidence[0].*", hasSize(4)))
        .andExpect(jsonPath("$.evidence[0].personaId").value(seedPersona))
        .andExpect(jsonPath("$.evidence[0].stepFrom").value(2))
        .andExpect(jsonPath("$.evidence[0].stepTo").value(5))
        .andExpect(jsonPath("$.evidence[0].url").value("https://shop.example.com/category"));
  }

  /** 완료 기준의 나머지 2개 — 같은 seed 회차로 Taxonomy 분포와 근거 스크린샷. */
  @Test
  void seedRun_stats_andEvidenceScreenshot_inSpecShape() throws Exception {
    long seedRun = seedRunId();
    long seedPersona = jdbcTemplate.queryForObject("SELECT persona_id FROM run_personas WHERE run_id = ?", Long.class, seedRun);
    long interaction = jdbcTemplate.queryForObject(
        "SELECT finding_id FROM findings WHERE run_id = ? AND taxonomy = 'interaction_failure'", Long.class, seedRun);
    writeScreenshot(seedRun, seedPersona, 6);   // interaction_failure 근거 step 6~7

    as(SEED_USER_ID, get("/api/findings/stats"))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.*", hasSize(1)))
        .andExpect(jsonPath("$.stats", hasSize(4)))
        .andExpect(jsonPath("$.stats[0].*", hasSize(2)))
        .andExpect(jsonPath("$.stats[*].taxonomy").value(contains(
            "navigation_confusion", "interaction_failure", "task_failure", "excessive_steps")))
        // 진단 seed(navigation · interaction · task 1건씩) + 개선안 seed(interaction · task 1건씩, R__seed_local_improvements)
        .andExpect(jsonPath("$.stats[*].count").value(contains(1, 2, 2, 0)));
    as(SEED_USER_ID, get("/api/findings/{findingId}/screenshots", interaction)
            .param("personaId", String.valueOf(seedPersona)).param("step", "6"))
        .andExpect(status().isOk())
        .andExpect(content().contentType(MediaType.IMAGE_PNG))
        .andExpect(header().string(HttpHeaders.CACHE_CONTROL, "max-age=86400, private"))
        .andExpect(content().bytes(PNG));
  }

  // ───────── Taxonomy 분포 ─────────

  @Test
  void stats_countsOnlyFirstRoundsThatAreDone_ofOwnExistingProjects_allFourInOrder() throws Exception {
    long first = insertRun("done", null);
    insertFinding(first, "navigation_confusion", "[]");
    insertFinding(first, "navigation_confusion", "[]");
    insertFinding(first, "excessive_steps", "[]");
    long second = insertRun("done", first);
    insertFinding(second, "task_failure", "[]");          // 다음 회차 — 세지 않는다
    long running = insertRun("running", null);
    insertFinding(running, "interaction_failure", "[]");  // 최초 회차가 done 아님 — 세지 않는다
    Long otherProject = insertProject(researcherId);
    long deleted = insertRunIn(otherProject, "done");
    insertFinding(deleted, "task_failure", "[]");         // 삭제한 프로젝트 — 세지 않는다
    jdbcTemplate.update("UPDATE projects SET deleted_at = NOW() WHERE project_id = ?", otherProject);

    as(researcherId, get("/api/findings/stats"))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.stats[*].taxonomy").value(contains(
            "navigation_confusion", "interaction_failure", "task_failure", "excessive_steps")))
        .andExpect(jsonPath("$.stats[*].count").value(contains(2, 0, 0, 1)));
    // 다른 리서처에게는 보이지 않는다 — 진단이 없으면 4종 모두 0
    as(insertUser("finding-stats-other@uxight.com"), get("/api/findings/stats"))
        .andExpect(jsonPath("$.stats", hasSize(4)))
        .andExpect(jsonPath("$.stats[*].count").value(contains(0, 0, 0, 0)));
  }

  // ───────── 근거 스크린샷 ─────────

  @Test
  void screenshot_onlyWithinEvidenceRange_inclusive() throws Exception {
    long run = insertRun("done", null);
    long finding = insertFinding(run, "interaction_failure", evidence(personaId, 2, 4));
    for (int step : new int[] {1, 2, 4, 5}) {
      writeScreenshot(run, personaId, step);
    }

    for (int step : new int[] {2, 4}) {   // 구간 양 끝 포함
      shot(researcherId, finding, personaId, step)
          .andExpect(status().isOk())
          .andExpect(content().bytes(PNG));
    }
    for (int step : new int[] {1, 5, 3}) {   // 범위 밖은 파일이 있어도 404, 범위 안이어도 파일이 없으면 404
      shot(researcherId, finding, personaId, step)
          .andExpect(status().isNotFound())
          .andExpect(jsonPath("$.code").value("LOG-ERR-002"));
    }
    shot(researcherId, finding, 999_999_999L, 2)   // 근거에 없는 Persona
        .andExpect(status().isNotFound())
        .andExpect(jsonPath("$.code").value("LOG-ERR-002"));
  }

  @Test
  void screenshot_ofOthersOrNotDoneFinding_isFindingNotFound_andMissingParamIsBadRequest() throws Exception {
    long run = insertRun("done", null);
    long finding = insertFinding(run, "task_failure", evidence(personaId, 1, 1));
    writeScreenshot(run, personaId, 1);
    long notDone = insertRun("running", null);
    long notDoneFinding = insertFinding(notDone, "task_failure", evidence(personaId, 1, 1));
    writeScreenshot(notDone, personaId, 1);

    shot(insertUser("finding-shot-other@uxight.com"), finding, personaId, 1)
        .andExpect(status().isNotFound())
        .andExpect(jsonPath("$.code").value("FND-ERR-001"));
    shot(researcherId, notDoneFinding, personaId, 1)
        .andExpect(status().isNotFound())
        .andExpect(jsonPath("$.code").value("FND-ERR-001"));
    as(researcherId, get("/api/findings/{findingId}/screenshots", finding).param("step", "1"))   // personaId 없음
        .andExpect(status().isBadRequest())
        .andExpect(jsonPath("$.code").value("GLB-ERR-001"));
    as(researcherId, get("/api/findings/{findingId}/screenshots", finding)
            .param("personaId", String.valueOf(personaId)).param("step", "abc"))
        .andExpect(status().isBadRequest())
        .andExpect(jsonPath("$.code").value("GLB-ERR-001"));
  }

  // ───────── 목록 ─────────

  @Test
  void list_secondRound_hasRoundTwo_andNoFindingsIsEmptyList() throws Exception {
    long first = insertRun("done", null);
    long second = insertRun("done", first);
    insertFinding(first, "excessive_steps", "[{\"persona_id\":" + personaId + ",\"step_from\":1,\"step_to\":10,\"url\":\"u\"}]");

    as(researcherId, get("/api/runs/{runId}/findings", second))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.run.firstRunId").value(first))
        .andExpect(jsonPath("$.run.round").value(2))
        .andExpect(jsonPath("$.findings", hasSize(0)));   // 검출된 Friction 이 없는 회차
    as(researcherId, get("/api/runs/{runId}/findings", first))
        .andExpect(jsonPath("$.run.round").value(1))
        .andExpect(jsonPath("$.findings[0].taxonomy").value("excessive_steps"));
  }

  @ParameterizedTest(name = "회차 status {0} → 404 (작성 중인 결과는 보이지 않는다)")
  @ValueSource(strings = {"queued", "running", "failed", "cancelled"})
  void notDoneRun_isNotFound_forListAndDetail(String status) throws Exception {
    long run = insertRun(status, null);
    long finding = insertFinding(run, "task_failure", "[]");

    as(researcherId, get("/api/runs/{runId}/findings", run))
        .andExpect(status().isNotFound())
        .andExpect(jsonPath("$.code").value("EXP-ERR-002"));
    as(researcherId, get("/api/findings/{findingId}", finding))
        .andExpect(status().isNotFound())
        .andExpect(jsonPath("$.code").value("FND-ERR-001"));
  }

  // ───────── 권한 ─────────

  @Test
  void othersRun_deletedProject_andMissing_areNotFound() throws Exception {
    long run = insertRun("done", null);
    long finding = insertFinding(run, "interaction_failure", "[]");
    Long other = insertUser("finding-other@uxight.com");

    as(other, get("/api/runs/{runId}/findings", run))
        .andExpect(status().isNotFound()).andExpect(jsonPath("$.code").value("EXP-ERR-002"));
    as(other, get("/api/findings/{findingId}", finding))
        .andExpect(status().isNotFound()).andExpect(jsonPath("$.code").value("FND-ERR-001"));
    as(researcherId, get("/api/runs/{runId}/findings", 999_999_999L))
        .andExpect(status().isNotFound()).andExpect(jsonPath("$.code").value("EXP-ERR-002"));
    as(researcherId, get("/api/findings/{findingId}", 999_999_999L))
        .andExpect(status().isNotFound()).andExpect(jsonPath("$.code").value("FND-ERR-001"));

    jdbcTemplate.update("UPDATE projects SET deleted_at = NOW() WHERE project_id = ?", projectId);
    as(researcherId, get("/api/runs/{runId}/findings", run))
        .andExpect(status().isNotFound()).andExpect(jsonPath("$.code").value("EXP-ERR-002"));
    as(researcherId, get("/api/findings/{findingId}", finding))
        .andExpect(status().isNotFound()).andExpect(jsonPath("$.code").value("FND-ERR-001"));
  }

  @Test
  void withoutToken_isUnauthorized_andNonNumericId_isBadRequest() throws Exception {
    mvc.perform(get("/api/runs/1/findings"))
        .andExpect(status().isUnauthorized())
        .andExpect(jsonPath("$.code").value("AUT-ERR-001"));
    as(researcherId, get("/api/findings/abc"))
        .andExpect(status().isBadRequest())
        .andExpect(jsonPath("$.code").value("GLB-ERR-001"));
  }

  // ───────── 도우미 ─────────

  private long seedRunId() {
    return jdbcTemplate.queryForObject("SELECT MIN(r.run_id) FROM runs r JOIN projects p ON p.project_id = r.project_id "
        + "WHERE p.user_id = ? AND p.title = '[seed] 진단 예시 쇼핑몰'", Long.class, SEED_USER_ID);
  }

  private ResultActions shot(Long userId, long findingId, long persona, int step) throws Exception {
    return as(userId, get("/api/findings/{findingId}/screenshots", findingId)
        .param("personaId", String.valueOf(persona)).param("step", String.valueOf(step)));
  }

  private static String evidence(long persona, int stepFrom, int stepTo) {
    return "[{\"persona_id\":" + persona + ",\"step_from\":" + stepFrom + ",\"step_to\":" + stepTo + ",\"url\":\"u\"}]";
  }

  private void writeScreenshot(long runId, long persona, int step) throws IOException {
    Path dir = Files.createDirectories(RUN_LOG_ROOT.resolve(Long.toString(runId)).resolve(Long.toString(persona)));
    Files.write(dir.resolve("step-" + step + ".png"), PNG);
  }

  private ResultActions as(Long userId, MockHttpServletRequestBuilder request) throws Exception {
    return mvc.perform(request.header(HttpHeaders.AUTHORIZATION, "Bearer " + jwtProvider.createAccessToken(userId)));
  }

  private Long insertUser(String email) {
    jdbcTemplate.update("INSERT INTO users (email, password_hash, auth_provider, name, role, is_active) "
        + "VALUES (?, 'hash', 'local', '진단', 'researcher', TRUE)", email);
    return jdbcTemplate.queryForObject("SELECT user_id FROM users WHERE email = ?", Long.class, email);
  }

  private Long insertProject(Long ownerId) {
    jdbcTemplate.update("INSERT INTO projects (user_id, title, target_url, allowed_domains) "
        + "VALUES (?, '진단 몰', 'https://shop.example.com', JSON_ARRAY('shop.example.com'))", ownerId);
    return jdbcTemplate.queryForObject("SELECT LAST_INSERT_ID()", Long.class);
  }

  /** 다른 프로젝트의 최초 회차. */
  private long insertRunIn(Long project, String status) {
    Long saved = projectId;
    projectId = project;
    try {
      return insertRun(status, null);
    } finally {
      projectId = saved;
    }
  }

  /** firstRunId 가 null 이면 최초 회차, 아니면 그 실험의 다음 회차. */
  private long insertRun(String status, Long firstRunId) {
    jdbcTemplate.update("INSERT INTO tasks (project_id, goal, success_rule, success_url) "
        + "VALUES (?, '결제한다', 'rule', 'https://shop.example.com/done')", projectId);
    Long taskId = jdbcTemplate.queryForObject("SELECT LAST_INSERT_ID()", Long.class);
    jdbcTemplate.update("INSERT INTO runs (project_id, task_id, mode, loop_max, target_url_snapshot, allowed_domains_snapshot, "
            + "task_snapshot, policy_snapshot, persona_snapshot, status, parent_run_id) "
            + "VALUES (?, ?, 'loop', 3, 'https://shop.example.com', JSON_ARRAY(), JSON_OBJECT(), JSON_OBJECT(), "
            + "JSON_ARRAY(JSON_OBJECT('persona_id', ?, 'name', '초보')), ?, ?)",
        projectId, taskId, personaId, status, firstRunId);
    long runId = jdbcTemplate.queryForObject("SELECT LAST_INSERT_ID()", Long.class);
    jdbcTemplate.update("UPDATE runs SET first_run_id = ? WHERE run_id = ?", firstRunId == null ? runId : firstRunId, runId);
    return runId;
  }

  private long insertFinding(long runId, String taxonomy, String evidenceJson) {
    jdbcTemplate.update("INSERT INTO findings (run_id, taxonomy, severity, evidence) VALUES (?, ?, 'low', ?)",
        runId, taxonomy, evidenceJson);
    return jdbcTemplate.queryForObject("SELECT LAST_INSERT_ID()", Long.class);
  }
}
