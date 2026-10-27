package com.uxight.api.web.finding;

import static org.hamcrest.Matchers.contains;
import static org.hamcrest.Matchers.hasSize;
import static org.hamcrest.Matchers.nullValue;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
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
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.ResultActions;
import org.springframework.test.web.servlet.request.MockHttpServletRequestBuilder;
import org.springframework.transaction.annotation.Transactional;

/**
 * 진단 목록(GET /api/runs/{runId}/findings) · 진단 상세(GET /api/findings/{findingId}) — 본인 프로젝트의 done 회차만.
 * 실제 MySQL, 테스트마다 롤백. 로컬 seed(R__seed_local_findings — 테스트도 local 프로필)로 명세의 응답 모양을 보고,
 * 404 조건은 테스트가 넣은 회차로 본다.
 */
@SpringBootTest
@AutoConfigureMockMvc
@Transactional
class FindingControllerTest {

  private static final long SEED_USER_ID = 1L;   // test@uxight.com (R__seed_local)

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
