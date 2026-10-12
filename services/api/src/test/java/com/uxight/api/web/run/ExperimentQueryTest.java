package com.uxight.api.web.run;

import static org.assertj.core.api.Assertions.assertThat;
import static org.hamcrest.Matchers.contains;
import static org.hamcrest.Matchers.hasSize;
import static org.hamcrest.Matchers.nullValue;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.uxight.api.domain.run.ExperimentFilter;
import com.uxight.api.domain.run.ExperimentSummary;
import com.uxight.api.domain.run.RunService;
import com.uxight.api.domain.user.JwtProvider;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.HttpHeaders;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.ResultActions;
import org.springframework.transaction.annotation.Transactional;

import java.time.DayOfWeek;
import java.time.LocalDateTime;
import java.time.OffsetDateTime;
import java.time.ZoneId;
import java.time.ZoneOffset;
import java.util.List;

/**
 * 실험 건수(GET /api/runs/stats)와 목록 조건(검색어 · 완료 시각). 상태 계산은 목록과 건수가 같은 SQL 을 쓴다.
 * 회차는 Python 이 쓰는 컬럼(status · tokens · finished_at)까지 SQL 로 직접 넣는다. 실제 MySQL, 테스트마다 롤백.
 */
@SpringBootTest
@AutoConfigureMockMvc
@Transactional
class ExperimentQueryTest {

  @Autowired
  private MockMvc mvc;

  @Autowired
  private JwtProvider jwtProvider;

  @Autowired
  private JdbcTemplate jdbcTemplate;

  @Autowired
  private ObjectMapper objectMapper;

  @Autowired
  private RunService runService;

  private Long userId;
  private String bearer;

  @BeforeEach
  void setUp() {
    userId = insertUser("stats@uxight.com");
    bearer = "Bearer " + jwtProvider.createAccessToken(userId);
  }

  // ───────── GET /api/runs/stats ─────────

  @Test
  void stats_withoutExperiments_returnsZeros_andThisWeekStartsMondayMidnightKst() throws Exception {
    JsonNode stats = stats();

    assertThat(stats.get("totalCount").asLong()).isZero();
    assertThat(stats.get("inProgressCount").asLong()).isZero();
    assertThat(stats.get("completedCount").asLong()).isZero();
    assertThat(stats.get("completedThisWeekCount").asLong()).isZero();
    assertThat(stats.get("awaitingApprovalCount").asLong()).isZero();
    assertThat(stats.get("totalTokens").asLong()).isZero();
    assertThat(stats.size()).isEqualTo(7);

    OffsetDateTime thisWeekFrom = OffsetDateTime.parse(stats.get("thisWeekFrom").asText());
    assertThat(thisWeekFrom.getOffset()).isEqualTo(ZoneOffset.ofHours(9));
    assertThat(thisWeekFrom.getDayOfWeek()).isEqualTo(DayOfWeek.MONDAY);
    assertThat(thisWeekFrom.toLocalTime()).hasToString("00:00");
    assertThat(thisWeekFrom).isBeforeOrEqualTo(OffsetDateTime.now());
    assertThat(thisWeekFrom).isAfter(OffsetDateTime.now().minusDays(7));
  }

  @Test
  void stats_countsEachStateOnce_andSumsTokensOfAllRounds() throws Exception {
    LocalDateTime weekStart = thisWeekStartInDb();
    Long project = insertProject(userId, "쇼핑몰");
    insertExperiment(project, "queued", false, null, null);                                   // 진행 중
    insertExperiment(project, "running", true, 100L, null);                                   // 중단(취소 진행 중)
    insertExperiment(project, "done", false, 200L, weekStart.plusHours(1));                   // 완료 — 이번 주
    insertExperiment(project, "done", false, 300L, weekStart.minusHours(1));                  // 완료 — 지난주
    insertExperiment(project, "failed", false, 50L, weekStart.plusHours(2));                  // 중단(실패)
    Long multi = insertExperiment(project, "done", false, 10L, weekStart.minusDays(1));       // 2회차 실험:
    insertNextRound(multi, project, "running", 20L);                                          //   마지막 회차 기준 진행 중
    insertExperiment(insertProject(insertUser("other@uxight.com"), "남의 것"), "done", false, 999L, null);

    JsonNode stats = stats();

    assertThat(stats.get("totalCount").asLong()).isEqualTo(6);           // 남의 실험 제외, 2회차 실험은 1건
    assertThat(stats.get("inProgressCount").asLong()).isEqualTo(2);
    assertThat(stats.get("completedCount").asLong()).isEqualTo(2);
    assertThat(stats.get("completedThisWeekCount").asLong()).isEqualTo(1);
    assertThat(stats.get("awaitingApprovalCount").asLong()).isZero();    // 승인 기능 도입 전
    assertThat(stats.get("totalTokens").asLong()).isEqualTo(100 + 200 + 300 + 50 + 10 + 20);
    // 네 분류는 겹치지 않는다 — 중단(2건)까지 더하면 총 건수
    assertThat(runService.countRuns(userId, new ExperimentFilter("stopped", null, null))).isEqualTo(2);
  }

  @Test
  void deletedProjectsExperiments_areHiddenFromListStatsAndCancel() throws Exception {
    Long kept = insertExperiment(insertProject(userId, "남은 프로젝트"), "done", false, 10L, null);
    Long deletedProject = insertProject(userId, "삭제한 프로젝트");
    Long hidden = insertExperiment(deletedProject, "done", false, 500L, null);
    jdbcTemplate.update("UPDATE projects SET deleted_at = NOW() WHERE project_id = ?", deletedProject);

    assertThat(ids(ExperimentFilter.none())).containsExactly(kept);
    assertThat(runService.countRuns(userId, ExperimentFilter.none())).isEqualTo(1);
    JsonNode stats = stats();
    assertThat(stats.get("totalCount").asLong()).isEqualTo(1);
    assertThat(stats.get("totalTokens").asLong()).isEqualTo(10);   // 삭제한 프로젝트의 토큰도 빠진다
    // 보이지 않는 실험은 없는 것과 같다
    mvc.perform(post("/api/runs/{firstRunId}/cancel", hidden).header(HttpHeaders.AUTHORIZATION, bearer))
        .andExpect(status().isNotFound())
        .andExpect(jsonPath("$.code").value("EXP-ERR-001"));
  }

  @Test
  void stats_withoutTokenOrByInactiveUser_returnsUnauthorized() throws Exception {
    mvc.perform(get("/api/runs/stats"))
        .andExpect(status().isUnauthorized())
        .andExpect(jsonPath("$.code").value("AUT-ERR-001"));

    jdbcTemplate.update("UPDATE users SET is_active = FALSE WHERE user_id = ?", userId);
    mvc.perform(get("/api/runs/stats").header(HttpHeaders.AUTHORIZATION, bearer))
        .andExpect(status().isUnauthorized())
        .andExpect(jsonPath("$.code").value("AUT-ERR-005"));
  }

  // ───────── GET /api/runs ─────────

  @Test
  void list_returnsLastRoundValuesOfEachExperiment_withPageMeta() throws Exception {
    Long project = insertProject(userId, "쇼핑몰");
    Long multi = insertExperiment(project, "done", false, 10L, null);          // 1회차 done
    Long last = insertNextRound(multi, project, "running", 20L);               // 2회차 running — 목록은 이 회차 기준
    jdbcTemplate.update("UPDATE runs SET progress = 1, heartbeat_at = NOW() - INTERVAL 10 MINUTE, "
        + "persona_snapshot = JSON_ARRAY(JSON_OBJECT('persona_id', 1), JSON_OBJECT('persona_id', 2)) WHERE run_id = ?", last);
    Long cancelling = insertExperiment(project, "running", true, null, null);

    mvc.perform(get("/api/runs").header(HttpHeaders.AUTHORIZATION, bearer))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.page").value(0))
        .andExpect(jsonPath("$.size").value(20))
        .andExpect(jsonPath("$.totalElements").value(2))
        .andExpect(jsonPath("$.totalPages").value(1))
        .andExpect(jsonPath("$.content[*].firstRunId").value(contains(cancelling.intValue(), multi.intValue())))
        // 2회차 실험 — 마지막 회차 기준 값
        .andExpect(jsonPath("$.content[1].*", hasSize(15)))
        .andExpect(jsonPath("$.content[1].runId").value(last))
        .andExpect(jsonPath("$.content[1].round").value(2))
        .andExpect(jsonPath("$.content[1].status").value("running"))
        .andExpect(jsonPath("$.content[1].state").value("in_progress"))
        .andExpect(jsonPath("$.content[1].endType").value(nullValue()))
        .andExpect(jsonPath("$.content[1].stale").value(true))       // heartbeat 가 끊긴 running — 표시만 한다
        .andExpect(jsonPath("$.content[1].hasResult").value(true))   // 최초 회차가 done
        .andExpect(jsonPath("$.content[1].projectTitle").value("쇼핑몰"))
        .andExpect(jsonPath("$.content[1].taskGoal").value("구매"))
        .andExpect(jsonPath("$.content[1].mode").value("diagnose"))
        .andExpect(jsonPath("$.content[1].progress").value(1))
        .andExpect(jsonPath("$.content[1].personaCount").value(2))
        .andExpect(jsonPath("$.content[1].elapsedSeconds").isNumber())
        .andExpect(jsonPath("$.content[1].createdAt").isString())
        // 취소 진행 중 — 중단으로 분류, 종료 유형 cancelling
        .andExpect(jsonPath("$.content[0].state").value("stopped"))
        .andExpect(jsonPath("$.content[0].endType").value("cancelling"))
        .andExpect(jsonPath("$.content[0].hasResult").value(false));
    assertThat(jdbcTemplate.queryForObject("SELECT status FROM runs WHERE run_id = ?", String.class, last))
        .isEqualTo("running");   // stale 이어도 status 를 바꾸지 않는다
  }

  @Test
  void list_pagesByNewestRequestFirst() throws Exception {
    Long project = insertProject(userId, "p");
    Long first = insertExperiment(project, "done", false, null, null);
    Long second = insertExperiment(project, "done", false, null, null);
    Long third = insertExperiment(project, "done", false, null, null);

    mvc.perform(get("/api/runs").header(HttpHeaders.AUTHORIZATION, bearer).param("page", "0").param("size", "2"))
        .andExpect(jsonPath("$.content[*].firstRunId").value(contains(third.intValue(), second.intValue())))
        .andExpect(jsonPath("$.totalElements").value(3))
        .andExpect(jsonPath("$.totalPages").value(2));
    mvc.perform(get("/api/runs").header(HttpHeaders.AUTHORIZATION, bearer).param("page", "1").param("size", "2"))
        .andExpect(jsonPath("$.content[*].firstRunId").value(contains(first.intValue())))
        .andExpect(jsonPath("$.page").value(1));
  }

  @Test
  void list_appliesQueryParameters() throws Exception {
    LocalDateTime weekStart = thisWeekStartInDb();
    Long shop = insertExperiment(insertProject(userId, "쇼핑몰"), "done", false, null, weekStart.plusHours(1));
    insertExperiment(insertProject(userId, "쇼핑몰 2"), "done", false, null, weekStart.minusDays(2));
    Long blog = insertExperiment(insertProject(userId, "블로그"), "queued", false, null, null);
    String thisWeekFrom = stats().get("thisWeekFrom").asText();   // 예: 2026-10-12T00:00:00+09:00

    mvc.perform(get("/api/runs").header(HttpHeaders.AUTHORIZATION, bearer).param("state", "in_progress"))
        .andExpect(jsonPath("$.content[*].firstRunId").value(contains(blog.intValue())));
    mvc.perform(get("/api/runs").header(HttpHeaders.AUTHORIZATION, bearer).param("keyword", "  쇼핑  "))
        .andExpect(jsonPath("$.totalElements").value(2));   // 앞뒤 공백은 지운다
    mvc.perform(get("/api/runs").header(HttpHeaders.AUTHORIZATION, bearer).param("keyword", "   "))
        .andExpect(jsonPath("$.totalElements").value(3));   // 빈 검색어는 조건 없음
    // '이번 주 완료' 이동: stats 의 thisWeekFrom 을 그대로 넘긴다
    mvc.perform(get("/api/runs").header(HttpHeaders.AUTHORIZATION, bearer)
            .param("state", "completed").param("finishedFrom", thisWeekFrom))
        .andExpect(jsonPath("$.content[*].firstRunId").value(contains(shop.intValue())))
        .andExpect(jsonPath("$.totalElements").value(1));
  }

  @ParameterizedTest(name = "[{index}] {0}={1} → {2}")
  @CsvSource({
      "state, fast, GLB-ERR-002",
      "page, -1, GLB-ERR-002",
      "size, 0, GLB-ERR-002",
      "page, abc, GLB-ERR-001",
      "finishedFrom, 2026-10-12, GLB-ERR-001",              // 날짜만 — 시각 아님
      "finishedFrom, 2026-10-12T00:00:00, GLB-ERR-001"      // 시간대 없음
  })
  void list_invalidParameter_returnsBadRequest(String name, String value, String code) throws Exception {
    ResultActions result = mvc.perform(get("/api/runs").header(HttpHeaders.AUTHORIZATION, bearer).param(name, value))
        .andExpect(status().isBadRequest())
        .andExpect(jsonPath("$.code").value(code));
    if (code.equals("GLB-ERR-002")) {
      result.andExpect(jsonPath("$.fieldErrors[0].field").value(name));
    }
  }

  @Test
  void list_withoutTokenOrByInactiveUser_returnsUnauthorized() throws Exception {
    mvc.perform(get("/api/runs"))
        .andExpect(status().isUnauthorized())
        .andExpect(jsonPath("$.code").value("AUT-ERR-001"));

    jdbcTemplate.update("UPDATE users SET is_active = FALSE WHERE user_id = ?", userId);
    mvc.perform(get("/api/runs").header(HttpHeaders.AUTHORIZATION, bearer))
        .andExpect(status().isUnauthorized())
        .andExpect(jsonPath("$.code").value("AUT-ERR-005"));
  }

  // ───────── 목록 조건 (RunService.getRuns) ─────────

  @Test
  void getRuns_keyword_matchesProjectTitleOrTaskGoal_andTreatsWildcardsAsText() {
    Long shop = insertExperiment(insertProject(userId, "쇼핑몰 진단"), "done", false, null, null);
    Long sale = insertExperiment(insertProject(userId, "100% 할인 이벤트"), "done", false, null, null);
    Long other = insertExperiment(insertProject(userId, "블로그"), "done", false, null, null);
    jdbcTemplate.update("UPDATE tasks SET goal = '쇼핑 카트에 담기' WHERE task_id = "
        + "(SELECT task_id FROM runs WHERE run_id = ?)", other);

    assertThat(ids(new ExperimentFilter(null, "쇼핑", null))).containsExactly(other, shop);   // 제목 또는 목표
    assertThat(ids(new ExperimentFilter(null, "%", null))).containsExactly(sale);            // % 는 글자로
    assertThat(ids(new ExperimentFilter(null, "없는말", null))).isEmpty();
    assertThat(runService.countRuns(userId, new ExperimentFilter(null, "쇼핑", null))).isEqualTo(2);
  }

  @Test
  void getRuns_finishedFrom_keepsExperimentsWhoseLastRoundEndedAfterIt() {
    LocalDateTime weekStart = thisWeekStartInDb();
    Long project = insertProject(userId, "p");
    Long thisWeek = insertExperiment(project, "done", false, null, weekStart.plusHours(1));
    insertExperiment(project, "done", false, null, weekStart.minusHours(1));
    insertExperiment(project, "running", false, null, null);   // 아직 끝나지 않음

    OffsetDateTime from = weekStart.atOffset(ZoneOffset.ofHours(9));
    assertThat(ids(new ExperimentFilter(null, null, from))).containsExactly(thisWeek);
    // '이번 주 완료' 이동 = state=completed + finishedFrom=thisWeekFrom
    assertThat(ids(new ExperimentFilter("completed", null, from))).containsExactly(thisWeek);
    // 같은 순간을 다른 시간대로 넘겨도 결과가 같다
    assertThat(ids(new ExperimentFilter(null, null, from.withOffsetSameInstant(ZoneOffset.UTC))))
        .containsExactly(thisWeek);
  }

  private JsonNode stats() throws Exception {
    String body = mvc.perform(get("/api/runs/stats").header(HttpHeaders.AUTHORIZATION, bearer))
        .andExpect(status().isOk())
        .andReturn().getResponse().getContentAsString();
    return objectMapper.readTree(body);
  }

  private List<Long> ids(ExperimentFilter filter) {
    return runService.getRuns(userId, filter, 0, 20).stream().map(ExperimentSummary::firstRunId).toList();
  }

  /** API 가 돌려주는 thisWeekFrom 을 DB 시각(KST)으로 — 완료 시각을 이 기준 앞뒤로 넣는다. */
  private LocalDateTime thisWeekStartInDb() {
    return runService.getStats(userId).thisWeekFrom().atZoneSameInstant(ZoneId.of("Asia/Seoul"))
        .toLocalDateTime();
  }

  private Long insertUser(String email) {
    jdbcTemplate.update("INSERT INTO users (email, password_hash, auth_provider, name, role, is_active) "
        + "VALUES (?, 'hash', 'local', '홍길동', 'researcher', TRUE)", email);
    return jdbcTemplate.queryForObject("SELECT user_id FROM users WHERE email = ?", Long.class, email);
  }

  private Long insertProject(Long ownerId, String title) {
    jdbcTemplate.update("INSERT INTO projects (user_id, title, target_url, allowed_domains) "
        + "VALUES (?, ?, 'https://a.example.com', JSON_ARRAY('a.example.com'))", ownerId, title);
    return jdbcTemplate.queryForObject("SELECT LAST_INSERT_ID()", Long.class);
  }

  /** 최초 회차 하나짜리 실험. firstRunId 를 돌려준다. */
  private Long insertExperiment(Long projectId, String status, boolean cancelRequested, Long tokens,
      LocalDateTime finishedAt) {
    jdbcTemplate.update("INSERT INTO tasks (project_id, goal, success_rule, success_url) "
        + "VALUES (?, '구매', 'rule', 'https://a.example.com/done')", projectId);
    Long taskId = jdbcTemplate.queryForObject("SELECT LAST_INSERT_ID()", Long.class);
    Long runId = insertRun(projectId, taskId, null, status, cancelRequested, tokens, finishedAt);
    jdbcTemplate.update("UPDATE runs SET first_run_id = run_id WHERE run_id = ?", runId);
    return runId;
  }

  private Long insertNextRound(Long firstRunId, Long projectId, String status, Long tokens) {
    Long taskId = jdbcTemplate.queryForObject("SELECT task_id FROM runs WHERE run_id = ?", Long.class, firstRunId);
    return insertRun(projectId, taskId, firstRunId, status, false, tokens, null);
  }

  private Long insertRun(Long projectId, Long taskId, Long firstRunId, String status, boolean cancelRequested,
      Long tokens, LocalDateTime finishedAt) {
    jdbcTemplate.update("INSERT INTO runs (project_id, task_id, mode, first_run_id, target_url_snapshot, "
        + "allowed_domains_snapshot, task_snapshot, policy_snapshot, persona_snapshot, status, cancel_requested, "
        + "tokens, finished_at) VALUES (?, ?, 'diagnose', ?, 'https://a.example.com', JSON_ARRAY(), JSON_OBJECT(), "
        + "JSON_OBJECT(), JSON_ARRAY(JSON_OBJECT('persona_id', 1)), ?, ?, ?, ?)",
        projectId, taskId, firstRunId, status, cancelRequested, tokens, finishedAt);
    return jdbcTemplate.queryForObject("SELECT LAST_INSERT_ID()", Long.class);
  }
}
