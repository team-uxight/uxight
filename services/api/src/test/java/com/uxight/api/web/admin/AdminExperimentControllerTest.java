package com.uxight.api.web.admin;

import static org.assertj.core.api.Assertions.assertThat;
import static org.hamcrest.Matchers.contains;
import static org.hamcrest.Matchers.hasSize;
import static org.hamcrest.Matchers.nullValue;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.uxight.api.domain.user.JwtProvider;
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
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.ResultActions;
import org.springframework.test.web.servlet.request.MockHttpServletRequestBuilder;
import org.springframework.transaction.annotation.Transactional;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;

/**
 * 관리자 전체 실험 목록(GET /api/admin/runs) · 회차 목록(GET /api/admin/runs/{firstRunId}/rounds) — admin · maintainer 만.
 * 실제 MySQL, 테스트마다 롤백. 다른 실험이 있을 수 있어 목록은 방금 넣은(가장 최근) 실험과 SQL 로 센 건수로 확인한다.
 * agent 로그 루트(uxight.run-log-dir)는 임시 폴더 — 목록 → 회차 → step 로그 · 스크린샷 흐름 테스트가 쓴다.
 */
@SpringBootTest
@AutoConfigureMockMvc
@Transactional
class AdminExperimentControllerTest {

  private static final Path RUN_LOG_ROOT;
  private static final byte[] PNG = {(byte) 0x89, 'P', 'N', 'G', 13, 10, 26, 10, 7, 7};

  static {
    try {
      RUN_LOG_ROOT = Files.createTempDirectory("uxight-admin-runs-");
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

  private Long adminId;
  private Long researcherA;
  private Long projectA;
  private Long personaA;
  private Long personaB;

  @BeforeEach
  void setUp() {
    adminId = insertUser("adminexp-admin@uxight.com", "admin");
    researcherA = insertUser("adminexp-a@uxight.com", "researcher");
    projectA = insertProject(researcherA, "A 쇼핑몰");
    personaA = insertPersona(researcherA, "쇼핑 초보");
    personaB = insertPersona(researcherA, "숙련자");
  }

  // ───────── GET /api/admin/runs ─────────

  @Test
  void list_allUsersExperiments_newestFirst_lastRoundValues_andDeletedProjectFlag() throws Exception {
    // A 의 loop 실험: 1회차 done → 2회차 running
    long loopFirst = insertRun(projectA, "loop", "done", null, "2026-10-01 10:00:00", "2026-10-01 10:05:00");
    insertRun(projectA, "loop", "running", loopFirst, "2026-10-01 10:10:00", null);
    // B 의 실험 — 프로젝트를 삭제했다
    Long researcherB = insertUser("adminexp-b@uxight.com", "researcher");
    Long projectB = insertProject(researcherB, "B 블로그");
    long deletedFirst = insertRun(projectB, "diagnose", "cancelled", null, "2026-10-02 09:00:00", "2026-10-02 09:01:00");
    jdbcTemplate.update("UPDATE projects SET deleted_at = NOW() WHERE project_id = ?", projectB);
    long total = jdbcTemplate.queryForObject("SELECT COUNT(*) FROM runs WHERE run_id = first_run_id", Long.class);

    admin(get("/api/admin/runs"))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.*", hasSize(5)))
        .andExpect(jsonPath("$.page").value(0))
        .andExpect(jsonPath("$.size").value(20))
        .andExpect(jsonPath("$.totalElements").value(total))
        // 최근 요청 순 — 나중에 만든 B 의 실험이 먼저
        .andExpect(jsonPath("$.content[0].*", hasSize(10)))
        .andExpect(jsonPath("$.content[0].firstRunId").value(deletedFirst))
        .andExpect(jsonPath("$.content[0].projectTitle").value("B 블로그"))
        .andExpect(jsonPath("$.content[0].projectDeleted").value(true))
        .andExpect(jsonPath("$.content[0].ownerEmail").value("adminexp-b@uxight.com"))
        .andExpect(jsonPath("$.content[0].status").value("cancelled"))
        .andExpect(jsonPath("$.content[1].firstRunId").value(loopFirst))
        .andExpect(jsonPath("$.content[1].projectDeleted").value(false))
        .andExpect(jsonPath("$.content[1].ownerEmail").value("adminexp-a@uxight.com"))
        .andExpect(jsonPath("$.content[1].taskGoal").value("장바구니에 담는다"))
        .andExpect(jsonPath("$.content[1].mode").value("loop"))
        .andExpect(jsonPath("$.content[1].round").value(2))                       // 마지막 회차 기준
        .andExpect(jsonPath("$.content[1].status").value("running"))
        .andExpect(jsonPath("$.content[1].createdAt").value("2026-10-01T10:00:00"))   // 최초 회차의 요청 시각
        .andExpect(jsonPath("$.content[1].finishedAt").value(nullValue()));       // 마지막 회차가 아직 진행 중
  }

  @Test
  void list_pagesBySize() throws Exception {
    long first = insertRun(projectA, "diagnose", "done", null, "2026-10-03 10:00:00", "2026-10-03 10:01:00");
    long second = insertRun(projectA, "diagnose", "done", null, "2026-10-03 11:00:00", "2026-10-03 11:01:00");

    admin(get("/api/admin/runs").param("page", "0").param("size", "1"))
        .andExpect(jsonPath("$.content[*].firstRunId").value(contains((int) second)));
    admin(get("/api/admin/runs").param("page", "1").param("size", "1"))
        .andExpect(jsonPath("$.page").value(1))
        .andExpect(jsonPath("$.content[*].firstRunId").value(contains((int) first)));
  }

  @ParameterizedTest(name = "{0}={1} → {2}")
  @CsvSource({
      "page, -1, GLB-ERR-002",
      "size, 0, GLB-ERR-002",
      "page, abc, GLB-ERR-001"
  })
  void list_invalidPageOrSize_isBadRequest(String name, String value, String code) throws Exception {
    admin(get("/api/admin/runs").param(name, value))
        .andExpect(status().isBadRequest())
        .andExpect(jsonPath("$.code").value(code));
  }

  // ───────── GET /api/admin/runs/{firstRunId}/rounds ─────────

  @Test
  void rounds_inOrder_withPersonaResults_andNotYetAcceptedRoundHasNamesOnly() throws Exception {
    long first = insertRun(projectA, "loop", "done", null, "2026-10-04 10:00:00", "2026-10-04 10:05:00");
    long second = insertRun(projectA, "loop", "queued", first, "2026-10-04 10:10:00", null);
    insertRunPersona(first, personaA, "done", 4);
    insertRunPersona(first, personaB, "max_steps", 10);

    admin(get("/api/admin/runs/{firstRunId}/rounds", first))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.*", hasSize(1)))
        .andExpect(jsonPath("$.rounds", hasSize(2)))
        .andExpect(jsonPath("$.rounds[0].*", hasSize(7)))
        .andExpect(jsonPath("$.rounds[0].runId").value(first))
        .andExpect(jsonPath("$.rounds[0].projectTitle").value("A 쇼핑몰"))
        .andExpect(jsonPath("$.rounds[0].taskGoal").value("장바구니에 담는다"))
        .andExpect(jsonPath("$.rounds[0].mode").value("loop"))
        .andExpect(jsonPath("$.rounds[0].round").value(1))
        .andExpect(jsonPath("$.rounds[0].status").value("done"))
        .andExpect(jsonPath("$.rounds[0].personas", hasSize(2)))
        .andExpect(jsonPath("$.rounds[0].personas[0].*", hasSize(4)))
        .andExpect(jsonPath("$.rounds[0].personas[0].personaId").value(personaA))
        .andExpect(jsonPath("$.rounds[0].personas[0].name").value("쇼핑 초보"))
        .andExpect(jsonPath("$.rounds[0].personas[0].status").value("done"))
        .andExpect(jsonPath("$.rounds[0].personas[0].steps").value(4))
        .andExpect(jsonPath("$.rounds[0].personas[1].status").value("max_steps"))
        .andExpect(jsonPath("$.rounds[1].runId").value(second))
        .andExpect(jsonPath("$.rounds[1].round").value(2))
        .andExpect(jsonPath("$.rounds[1].status").value("queued"))
        .andExpect(jsonPath("$.rounds[1].personas[0].name").value("쇼핑 초보"))   // AI 접수 전 — 이름만
        .andExpect(jsonPath("$.rounds[1].personas[0].status").value(nullValue()))
        .andExpect(jsonPath("$.rounds[1].personas[0].steps").value(nullValue()));
  }

  @Test
  void rounds_ofDeletedProject_areVisible_andLeadToAdminStepLogs() throws Exception {
    long first = insertRun(projectA, "diagnose", "running", null, "2026-10-05 10:00:00", null);
    insertRunPersona(first, personaA, "running", 0);
    jdbcTemplate.update("UPDATE projects SET deleted_at = NOW() WHERE project_id = ?", projectA);

    admin(get("/api/admin/runs/{firstRunId}/rounds", first))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.rounds[0].personas[0].personaId").value(personaA));
    // 회차 목록에서 얻은 runId · personaId 로 운영자용 step 로그를 부른다 — 실행 중, 첫 줄 전이라 빈 목록
    admin(get("/api/admin/runs/{runId}/personas/{personaId}/steps", first, personaA))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.steps", hasSize(0)));
  }

  @Test
  void rounds_ofLaterRoundIdOrMissingExperiment_isExperimentNotFound() throws Exception {
    long first = insertRun(projectA, "loop", "done", null, "2026-10-06 10:00:00", "2026-10-06 10:05:00");
    long second = insertRun(projectA, "loop", "running", first, "2026-10-06 10:10:00", null);

    admin(get("/api/admin/runs/{firstRunId}/rounds", second))   // 최초 회차가 아니다
        .andExpect(status().isNotFound())
        .andExpect(jsonPath("$.code").value("EXP-ERR-001"));
    admin(get("/api/admin/runs/{firstRunId}/rounds", 999_999_999L))
        .andExpect(status().isNotFound())
        .andExpect(jsonPath("$.code").value("EXP-ERR-001"));
  }

  // ───────── 완료 기준: 목록 → 회차 → 원하는 회차의 step 로그 · 스크린샷 ─────────

  /** 응답에서 꺼낸 값만으로 다음 API 를 부른다 — 실험 목록 → 회차 목록 → 2회차 Persona 의 step 로그 → 스크린샷. */
  @Test
  void flow_experimentList_toRounds_toChosenRoundsStepLogAndScreenshot() throws Exception {
    long first = insertRun(projectA, "loop", "done", null, "2026-10-08 10:00:00", "2026-10-08 10:05:00");
    long second = insertRun(projectA, "loop", "running", first, "2026-10-08 10:10:00", null);
    insertRunPersona(first, personaA, "done", 3);
    insertRunPersona(second, personaA, "running", 1);
    // agent 가 2회차 · 쇼핑 초보 의 1번째 step 을 기록했다 (스크린샷 먼저, 줄 나중)
    Path dir = Files.createDirectories(RUN_LOG_ROOT.resolve(Long.toString(second)).resolve(personaA.toString()));
    Files.write(dir.resolve("step-1.png"), PNG);
    Files.writeString(dir.resolve("steps.jsonl"), """
        {"step":1,"ts":"2026-10-08T10:10:05+09:00","url":"https://shop.example.com/",        "observation":{"screenshot":"x"},"reasoning":"장바구니를 찾는다","action":{"kind":"click","target":2},        "result":{"ok":true,"url_after":"https://shop.example.com/cart"},"blocked":{"is":false,"reason":null},        "task":{"url_reached":true}}
        """, StandardCharsets.UTF_8);

    // 1. 실험 목록 — 가장 최근 실험이 방금 만든 실험
    JsonNode experiments = body(admin(get("/api/admin/runs")).andExpect(status().isOk()));
    long firstRunId = experiments.at("/content/0/firstRunId").asLong();
    assertThat(firstRunId).isEqualTo(first);
    assertThat(experiments.at("/content/0/round").asInt()).isEqualTo(2);

    // 2. 회차 목록 — 2회차의 runId 와 Persona 를 고른다
    JsonNode rounds = body(admin(get("/api/admin/runs/{firstRunId}/rounds", firstRunId)).andExpect(status().isOk()));
    JsonNode chosen = rounds.at("/rounds/1");
    long runId = chosen.get("runId").asLong();
    long personaId = chosen.at("/personas/0/personaId").asLong();
    assertThat(runId).isEqualTo(second);
    assertThat(chosen.at("/personas/0/status").asText()).isEqualTo("running");

    // 3. 그 회차 · Persona 의 step 로그
    JsonNode steps = body(admin(get("/api/admin/runs/{runId}/personas/{personaId}/steps", runId, personaId))
        .andExpect(status().isOk()));
    assertThat(steps.get("steps")).hasSize(1);
    assertThat(steps.at("/steps/0/result/urlAfter").asText()).isEqualTo("https://shop.example.com/cart");
    assertThat(steps.at("/steps/0/hasScreenshot").asBoolean()).isTrue();

    // 4. hasScreenshot 인 step 의 스크린샷
    int step = steps.at("/steps/0/step").asInt();
    admin(get("/api/admin/runs/{runId}/personas/{personaId}/steps/{step}/screenshot", runId, personaId, step))
        .andExpect(status().isOk())
        .andExpect(content().contentType(MediaType.IMAGE_PNG))
        .andExpect(content().bytes(PNG));
    // 1회차의 같은 Persona 는 로그 파일이 없다 — 끝난 Persona 라 404 LOG-ERR-001
    admin(get("/api/admin/runs/{runId}/personas/{personaId}/steps", first, personaId))
        .andExpect(status().isNotFound())
        .andExpect(jsonPath("$.code").value("LOG-ERR-001"));
  }

  // ───────── 권한 ─────────

  @Test
  void maintainer_canRead_researcherIsForbidden_withoutTokenIsUnauthorized() throws Exception {
    long first = insertRun(projectA, "diagnose", "done", null, "2026-10-07 10:00:00", "2026-10-07 10:01:00");
    Long maintainer = insertUser("adminexp-m@uxight.com", "maintainer");

    as(maintainer, get("/api/admin/runs")).andExpect(status().isOk());
    as(maintainer, get("/api/admin/runs/{firstRunId}/rounds", first)).andExpect(status().isOk());
    as(researcherA, get("/api/admin/runs"))   // 자기 실험이 있어도 관리자 경로는 403
        .andExpect(status().isForbidden())
        .andExpect(jsonPath("$.code").value("AUT-ERR-006"));
    as(researcherA, get("/api/admin/runs/{firstRunId}/rounds", first))
        .andExpect(status().isForbidden())
        .andExpect(jsonPath("$.code").value("AUT-ERR-006"));
    mvc.perform(get("/api/admin/runs"))
        .andExpect(status().isUnauthorized())
        .andExpect(jsonPath("$.code").value("AUT-ERR-001"));
  }

  // ───────── 도우미 ─────────

  private JsonNode body(ResultActions result) throws Exception {
    return objectMapper.readTree(result.andReturn().getResponse().getContentAsString());
  }

  private ResultActions admin(MockHttpServletRequestBuilder request) throws Exception {
    return as(adminId, request);
  }

  private ResultActions as(Long userId, MockHttpServletRequestBuilder request) throws Exception {
    return mvc.perform(request.header(HttpHeaders.AUTHORIZATION, "Bearer " + jwtProvider.createAccessToken(userId)));
  }

  private Long insertUser(String email, String role) {
    jdbcTemplate.update("INSERT INTO users (email, password_hash, auth_provider, name, role, is_active) "
        + "VALUES (?, 'hash', 'local', '실험', ?, TRUE)", email, role);
    return jdbcTemplate.queryForObject("SELECT user_id FROM users WHERE email = ?", Long.class, email);
  }

  private Long insertProject(Long ownerId, String title) {
    jdbcTemplate.update("INSERT INTO projects (user_id, title, target_url, allowed_domains) "
        + "VALUES (?, ?, 'https://shop.example.com', JSON_ARRAY('shop.example.com'))", ownerId, title);
    return jdbcTemplate.queryForObject("SELECT LAST_INSERT_ID()", Long.class);
  }

  private Long insertPersona(Long ownerId, String name) {
    jdbcTemplate.update("INSERT INTO personas (user_id, name, profile) VALUES (?, ?, JSON_OBJECT('webSkill', 'low'))",
        ownerId, name);
    return jdbcTemplate.queryForObject("SELECT LAST_INSERT_ID()", Long.class);
  }

  /** firstRunId 가 null 이면 최초 회차(first_run_id = 자기 자신), 아니면 그 실험의 다음 회차. */
  private long insertRun(Long project, String mode, String status, Long firstRunId, String createdAt, String finishedAt) {
    jdbcTemplate.update("INSERT INTO tasks (project_id, goal, success_rule, success_url) "
        + "VALUES (?, '장바구니에 담는다', 'rule', 'https://shop.example.com/cart')", project);
    Long taskId = jdbcTemplate.queryForObject("SELECT LAST_INSERT_ID()", Long.class);
    jdbcTemplate.update("INSERT INTO runs (project_id, task_id, mode, loop_max, target_url_snapshot, allowed_domains_snapshot, "
            + "task_snapshot, policy_snapshot, persona_snapshot, status, parent_run_id, created_at, finished_at) "
            + "VALUES (?, ?, ?, ?, 'https://shop.example.com', JSON_ARRAY(), JSON_OBJECT(), JSON_OBJECT(), "
            + "JSON_ARRAY(JSON_OBJECT('persona_id', ?, 'name', '쇼핑 초보'), JSON_OBJECT('persona_id', ?, 'name', '숙련자')), "
            + "?, ?, ?, ?)",
        project, taskId, mode, mode.equals("loop") ? 3 : null, personaA, personaB, status, firstRunId, createdAt,
        finishedAt);
    long runId = jdbcTemplate.queryForObject("SELECT LAST_INSERT_ID()", Long.class);
    jdbcTemplate.update("UPDATE runs SET first_run_id = ? WHERE run_id = ?", firstRunId == null ? runId : firstRunId, runId);
    return runId;
  }

  private void insertRunPersona(long run, Long persona, String status, int steps) {
    jdbcTemplate.update("INSERT INTO run_personas (run_id, persona_id, status, steps, started_at) VALUES (?, ?, ?, ?, NOW())",
        run, persona, status, steps);
  }
}
