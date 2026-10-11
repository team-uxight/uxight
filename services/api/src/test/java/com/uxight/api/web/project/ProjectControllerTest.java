package com.uxight.api.web.project;

import static org.assertj.core.api.Assertions.assertThat;
import static org.hamcrest.Matchers.contains;
import static org.hamcrest.Matchers.empty;
import static org.hamcrest.Matchers.hasKey;
import static org.hamcrest.Matchers.not;
import static org.hamcrest.Matchers.nullValue;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.patch;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.uxight.api.domain.user.JwtProvider;
import jakarta.persistence.EntityManager;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.Arguments;
import org.junit.jupiter.params.provider.MethodSource;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.ResultActions;
import org.springframework.test.web.servlet.request.MockMvcRequestBuilders;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.Map;
import java.util.stream.Stream;

/** 대시보드 프로젝트 목록(GET /api/projects)과 생성 · 상세의 JPA 매핑을 본다. 실제 MySQL, 테스트마다 롤백. */
@SpringBootTest
@AutoConfigureMockMvc
@Transactional
class ProjectControllerTest {

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

  private Long userId;
  private String bearer;

  @BeforeEach
  void setUp() {
    userId = insertUser("project-owner@uxight.com");
    bearer = "Bearer " + jwtProvider.createAccessToken(userId);
  }

  @Test
  void list_returnsOnlyOwnProjects_newestFirst() throws Exception {
    Long older = insertProject(userId, "첫 프로젝트", "https://a.example.com", "설명");
    Long newer = insertProject(userId, "둘째 프로젝트", "https://b.example.com", null);
    insertProject(insertUser("other@uxight.com"), "남의 프로젝트", "https://c.example.com", null);

    mvc.perform(get("/api/projects").header(HttpHeaders.AUTHORIZATION, bearer))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.projects[*].projectId").value(contains(newer.intValue(), older.intValue())))
        .andExpect(jsonPath("$.projects[0].title").value("둘째 프로젝트"))
        .andExpect(jsonPath("$.projects[0].targetUrl").value("https://b.example.com"))
        .andExpect(jsonPath("$.projects[0].description").value(nullValue()))
        .andExpect(jsonPath("$.projects[1].description").value("설명"))
        // 목록에는 허용 도메인을 싣지 않는다 (ProjectSummary)
        .andExpect(jsonPath("$.projects[0]", not(hasKey("allowedDomains"))));
  }

  @Test
  void list_withoutProjects_returnsEmptyArray() throws Exception {
    mvc.perform(get("/api/projects").header(HttpHeaders.AUTHORIZATION, bearer))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.projects").value(empty()));
  }

  @Test
  void list_withoutToken_returnsUnauthorized() throws Exception {
    mvc.perform(get("/api/projects"))
        .andExpect(status().isUnauthorized())
        .andExpect(jsonPath("$.code").value("AUT-ERR-001"));
  }

  @Test
  void create_thenDetail_roundTripsAllowedDomainsAsArray() throws Exception {
    Map<String, Object> request = Map.of(
        "title", "새 프로젝트",
        "targetUrl", "https://shop.example.com",
        "allowedDomains", List.of("shop.example.com", "cdn.example.com"));

    String body = mvc.perform(post("/api/projects").header(HttpHeaders.AUTHORIZATION, bearer)
            .contentType(MediaType.APPLICATION_JSON)
            .content(objectMapper.writeValueAsString(request)))
        .andExpect(status().isCreated())
        .andReturn().getResponse().getContentAsString();
    long projectId = objectMapper.readTree(body).get("projectId").asLong();

    Long ownerId = jdbcTemplate.queryForObject("SELECT user_id FROM projects WHERE project_id = ?", Long.class, projectId);
    assertThat(ownerId).isEqualTo(userId);

    mvc.perform(get("/api/projects/{projectId}", projectId).header(HttpHeaders.AUTHORIZATION, bearer))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.projectId").value(projectId))
        .andExpect(jsonPath("$.allowedDomains").value(contains("shop.example.com", "cdn.example.com")));
  }

  @Test
  void create_savesFieldsWithRequesterAsOwner() throws Exception {
    Map<String, Object> request = Map.of(
        "title", "쇼핑몰 진단",
        "targetUrl", "http://shop.example.com/start",
        "description", "결제 흐름",
        "allowedDomains", List.of("shop.example.com"));

    long projectId = createAndGetId(objectMapper.writeValueAsString(request));

    Map<String, Object> row = jdbcTemplate.queryForMap(
        "SELECT user_id, title, target_url, description FROM projects WHERE project_id = ?", projectId);
    assertThat(row.get("user_id")).isEqualTo(userId);
    assertThat(row.get("title")).isEqualTo("쇼핑몰 진단");
    assertThat(row.get("target_url")).isEqualTo("http://shop.example.com/start");
    assertThat(row.get("description")).isEqualTo("결제 흐름");
    assertThat(allowedDomainsOf(projectId)).containsExactly("shop.example.com");
  }

  @Test
  void create_addsTargetHostFirst_andRemovesDuplicatesIgnoringCase() throws Exception {
    long projectId = createAndGetId("{\"title\":\"t\",\"targetUrl\":\"https://Shop.Example.com:8443/start?q=1\","
        + "\"allowedDomains\":[\"cdn.example.com\",\"shop.example.com\",\"CDN.example.com\",\"pay.example.com\"]}");

    assertThat(allowedDomainsOf(projectId)).containsExactly("shop.example.com", "cdn.example.com", "pay.example.com");
  }

  @Test
  void create_keepsOnlyHostOfAddressInAllowedDomains() throws Exception {
    long projectId = createAndGetId("{\"title\":\"t\",\"targetUrl\":\"https://shop.example.com\","
        + "\"allowedDomains\":[\"https://pay.example.com/checkout\",\"PAY.example.com\",\"cdn.example.com/assets\","
        + "\" img.example.com \",\"http://auth.example.com:8080/login?next=/\"]}");

    assertThat(allowedDomainsOf(projectId)).containsExactly(
        "shop.example.com", "pay.example.com", "cdn.example.com", "img.example.com", "auth.example.com");
  }

  @Test
  void create_withEmptyAllowedDomains_allowsOnlyTargetHost() throws Exception {
    long projectId = createAndGetId("{\"title\":\"t\",\"targetUrl\":\"https://a.example.com/x\",\"allowedDomains\":[]}");

    assertThat(allowedDomainsOf(projectId)).containsExactly("a.example.com");
  }

  @ParameterizedTest(name = "[{index}] {1}")
  @MethodSource("invalidCreateRequests")
  void create_invalidField_returnsInvalidInput(String json, String field) throws Exception {
    create(json)
        .andExpect(status().isBadRequest())
        .andExpect(jsonPath("$.code").value("GLB-ERR-002"))
        .andExpect(jsonPath("$.fieldErrors[*].field").value(contains(field)));
    assertThat(jdbcTemplate.queryForObject("SELECT COUNT(*) FROM projects WHERE user_id = ?", Integer.class, userId))
        .isZero();
  }

  static Stream<Arguments> invalidCreateRequests() {
    String domains = "\"allowedDomains\":[\"a.example.com\"]";
    String url = "\"targetUrl\":\"https://a.example.com\"";
    return Stream.of(
        Arguments.of("{" + url + "," + domains + "}", "title"),
        Arguments.of("{\"title\":\"   \"," + url + "," + domains + "}", "title"),
        Arguments.of("{\"title\":\"\"," + url + "," + domains + "}", "title"),
        Arguments.of("{\"title\":\" 앞 공백\"," + url + "," + domains + "}", "title"),
        Arguments.of("{\"title\":\"뒤 공백\\t\"," + url + "," + domains + "}", "title"),
        Arguments.of("{\"title\":\"" + "가".repeat(101) + "\"," + url + "," + domains + "}", "title"),
        Arguments.of("{\"title\":\"t\"," + domains + "}", "targetUrl"),
        Arguments.of("{\"title\":\"t\",\"targetUrl\":\"javascript:alert(1)\"," + domains + "}", "targetUrl"),
        Arguments.of("{\"title\":\"t\",\"targetUrl\":\"file:///etc/passwd\"," + domains + "}", "targetUrl"),
        Arguments.of("{\"title\":\"t\",\"targetUrl\":\"https://exa mple.com\"," + domains + "}", "targetUrl"),   // 호스트를 읽을 수 없음
        Arguments.of("{\"title\":\"t\",\"targetUrl\":\"https://a.example.com/" + "a".repeat(2048) + "\"," + domains + "}",
            "targetUrl"),
        Arguments.of("{\"title\":\"t\"," + url + ",\"description\":\"" + "가".repeat(1001) + "\"," + domains + "}",
            "description"),
        Arguments.of("{\"title\":\"t\"," + url + "}", "allowedDomains"),
        Arguments.of("{\"title\":\"t\"," + url + ",\"allowedDomains\":[\"\"]}", "allowedDomains[0]"),
        // 호스트를 읽을 수 없는 항목 — 몇 번째 항목인지 필드 이름으로 알려 준다
        Arguments.of("{\"title\":\"t\"," + url + ",\"allowedDomains\":[\"ok.example.com\",\"https://exa mple.com\"]}",
            "allowedDomains[1]"),
        Arguments.of("{\"title\":\"t\"," + url + ",\"allowedDomains\":[\"javascript:alert(1)\"]}", "allowedDomains[0]"));
  }

  @ParameterizedTest
  @ValueSource(strings = {
      "{\"title\":",                                                                         // JSON 문법 오류
      "{\"title\":\"t\",\"targetUrl\":\"https://a.example.com\",\"allowedDomains\":\"a.com\"}",  // 배열 자리에 문자열
  })
  void create_unreadableBody_returnsBadRequest(String json) throws Exception {
    create(json)
        .andExpect(status().isBadRequest())
        .andExpect(jsonPath("$.code").value("GLB-ERR-001"));
  }

  @Test
  void create_withoutToken_returnsUnauthorized() throws Exception {
    mvc.perform(post("/api/projects").contentType(MediaType.APPLICATION_JSON).content("{}"))
        .andExpect(status().isUnauthorized())
        .andExpect(jsonPath("$.code").value("AUT-ERR-001"));
  }

  @Test
  void create_byInactiveUser_returnsUnauthorized() throws Exception {
    jdbcTemplate.update("UPDATE users SET is_active = FALSE WHERE user_id = ?", userId);

    create("{\"title\":\"t\",\"targetUrl\":\"https://a.example.com\",\"allowedDomains\":[]}")
        .andExpect(status().isUnauthorized())
        .andExpect(jsonPath("$.code").value("AUT-ERR-005"));
  }

  @Test
  void detail_ofOthersProject_returnsNotFound() throws Exception {
    Long othersProject = insertProject(insertUser("other@uxight.com"), "남의 프로젝트", "https://c.example.com", null);

    mvc.perform(get("/api/projects/{projectId}", othersProject).header(HttpHeaders.AUTHORIZATION, bearer))
        .andExpect(status().isNotFound())
        .andExpect(jsonPath("$.code").value("PRJ-ERR-001"));
  }

  // ───────── PATCH /api/projects/{projectId} ─────────

  @Test
  void update_changesOnlySentFields() throws Exception {
    Long projectId = insertOriginalProject();

    update(projectId, "{\"title\":\"새 제목\"}")
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.projectId").value(projectId))
        .andExpect(jsonPath("$.title").value("새 제목"))
        .andExpect(jsonPath("$.targetUrl").value("https://a.example.com/start"))
        .andExpect(jsonPath("$.description").value("원래 설명"))
        .andExpect(jsonPath("$.allowedDomains").value(contains("a.example.com", "b.example.com")));

    Map<String, Object> row = jdbcTemplate.queryForMap(
        "SELECT title, target_url, description FROM projects WHERE project_id = ?", projectId);
    assertThat(row).containsEntry("title", "새 제목")
        .containsEntry("target_url", "https://a.example.com/start")
        .containsEntry("description", "원래 설명");
  }

  @Test
  void update_withEmptyBody_changesNothing() throws Exception {
    Long projectId = insertOriginalProject();

    update(projectId, "{}")
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.title").value("원래 제목"))
        .andExpect(jsonPath("$.description").value("원래 설명"));
  }

  @Test
  void update_descriptionNull_clearsDescription() throws Exception {
    Long projectId = insertOriginalProject();

    update(projectId, "{\"description\":null}")
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.description").value(nullValue()))
        .andExpect(jsonPath("$.title").value("원래 제목"));
    assertThat(jdbcTemplate.queryForObject("SELECT description FROM projects WHERE project_id = ?", String.class,
        projectId)).isNull();
  }

  @Test
  void update_targetUrlOnly_putsNewHostFirst_andKeepsExistingDomains() throws Exception {
    Long projectId = insertOriginalProject();

    update(projectId, "{\"targetUrl\":\"https://New.example.com/x\"}")
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.targetUrl").value("https://New.example.com/x"))
        .andExpect(jsonPath("$.allowedDomains").value(contains("new.example.com", "a.example.com", "b.example.com")));
    assertThat(allowedDomainsOf(projectId)).containsExactly("new.example.com", "a.example.com", "b.example.com");
  }

  @Test
  void update_targetUrlAndAllowedDomains_replacesListWithNewHostFirst() throws Exception {
    Long projectId = insertOriginalProject();

    update(projectId, "{\"targetUrl\":\"https://new.example.com\","
        + "\"allowedDomains\":[\"https://pay.example.com/checkout\",\"NEW.example.com\"]}")
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.allowedDomains").value(contains("new.example.com", "pay.example.com")));
  }

  @Test
  void update_allowedDomainsOnly_keepsCurrentTargetHost() throws Exception {
    Long projectId = insertOriginalProject();

    update(projectId, "{\"allowedDomains\":[]}")
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.allowedDomains").value(contains("a.example.com")));
  }

  @ParameterizedTest(name = "[{index}] {1}")
  @MethodSource("invalidUpdateRequests")
  void update_invalidField_returnsInvalidInput_andChangesNothing(String json, String field) throws Exception {
    Long projectId = insertOriginalProject();

    update(projectId, json)
        .andExpect(status().isBadRequest())
        .andExpect(jsonPath("$.code").value("GLB-ERR-002"))
        .andExpect(jsonPath("$.fieldErrors[*].field").value(contains(field)));

    Map<String, Object> row = jdbcTemplate.queryForMap(
        "SELECT title, target_url, description FROM projects WHERE project_id = ?", projectId);
    assertThat(row).containsEntry("title", "원래 제목")
        .containsEntry("target_url", "https://a.example.com/start")
        .containsEntry("description", "원래 설명");
    assertThat(allowedDomainsOf(projectId)).containsExactly("a.example.com", "b.example.com");
  }

  static Stream<Arguments> invalidUpdateRequests() {
    return Stream.of(
        // description 외에는 null 로 지울 수 없다
        Arguments.of("{\"title\":null}", "title"),
        Arguments.of("{\"title\":\"\"}", "title"),
        Arguments.of("{\"title\":\" 앞 공백\"}", "title"),
        Arguments.of("{\"title\":\"" + "가".repeat(101) + "\"}", "title"),
        Arguments.of("{\"targetUrl\":null}", "targetUrl"),
        Arguments.of("{\"targetUrl\":\"javascript:alert(1)\"}", "targetUrl"),
        // 시작 URL 은 바꾸고 제목은 그대로 두려 해도, 한 항목이 틀리면 아무것도 바꾸지 않는다
        Arguments.of("{\"title\":\"새 제목\",\"targetUrl\":\"https://exa mple.com\"}", "targetUrl"),
        Arguments.of("{\"description\":\"" + "가".repeat(1001) + "\"}", "description"),
        Arguments.of("{\"allowedDomains\":null}", "allowedDomains"),
        Arguments.of("{\"allowedDomains\":[\"\"]}", "allowedDomains[0]"),
        Arguments.of("{\"allowedDomains\":[\"ok.example.com\",\"https://exa mple.com\"]}", "allowedDomains[1]"));
  }

  @ParameterizedTest
  @ValueSource(strings = {"{\"title\":", "{\"allowedDomains\":\"a.com\"}", "[]"})
  void update_unreadableBody_returnsBadRequest(String json) throws Exception {
    update(insertOriginalProject(), json)
        .andExpect(status().isBadRequest())
        .andExpect(jsonPath("$.code").value("GLB-ERR-001"));
  }

  @Test
  void update_othersOrMissingProject_returnsNotFound() throws Exception {
    Long othersProject = insertProject(insertUser("other@uxight.com"), "남의 프로젝트", "https://c.example.com", null);

    update(othersProject, "{\"title\":\"가로채기\"}")
        .andExpect(status().isNotFound())
        .andExpect(jsonPath("$.code").value("PRJ-ERR-001"));
    update(Long.MAX_VALUE, "{\"title\":\"없음\"}")
        .andExpect(status().isNotFound())
        .andExpect(jsonPath("$.code").value("PRJ-ERR-001"));
    assertThat(jdbcTemplate.queryForObject("SELECT title FROM projects WHERE project_id = ?", String.class,
        othersProject)).isEqualTo("남의 프로젝트");
  }

  @Test
  void update_withoutToken_returnsUnauthorized() throws Exception {
    mvc.perform(patch("/api/projects/{projectId}", insertOriginalProject())
            .contentType(MediaType.APPLICATION_JSON).content("{}"))
        .andExpect(status().isUnauthorized())
        .andExpect(jsonPath("$.code").value("AUT-ERR-001"));
  }

  // 수정은 커밋 때 dirty checking 으로 UPDATE 되는데 테스트 트랜잭션은 커밋하지 않는다 — JdbcTemplate 으로 DB 를 보기 전에 flush 한다.
  // ───────── DELETE /api/projects/{projectId} ─────────

  @Test
  void delete_marksDeletedAt_keepsRow_andHidesProjectEverywhere() throws Exception {
    Long projectId = insertOriginalProject();
    Long kept = insertProject(userId, "남는 프로젝트", "https://k.example.com", null);

    delete(projectId).andExpect(status().isNoContent());

    // 행은 남고 삭제 시각만 기록된다 — 지난 실험의 Task · 회차가 참조한다
    assertThat(jdbcTemplate.queryForObject("SELECT deleted_at IS NOT NULL FROM projects WHERE project_id = ?",
        Boolean.class, projectId)).isTrue();

    mvc.perform(get("/api/projects").header(HttpHeaders.AUTHORIZATION, bearer))
        .andExpect(jsonPath("$.projects[*].projectId").value(contains(kept.intValue())));
    mvc.perform(get("/api/projects/{projectId}", projectId).header(HttpHeaders.AUTHORIZATION, bearer))
        .andExpect(status().isNotFound())
        .andExpect(jsonPath("$.code").value("PRJ-ERR-001"));
    update(projectId, "{\"title\":\"되살리기\"}")
        .andExpect(status().isNotFound())
        .andExpect(jsonPath("$.code").value("PRJ-ERR-001"));
    delete(projectId)
        .andExpect(status().isNotFound())
        .andExpect(jsonPath("$.code").value("PRJ-ERR-001"));
  }

  @Test
  void delete_thenExperimentRequest_returnsProjectNotFound() throws Exception {
    Long projectId = insertOriginalProject();
    delete(projectId).andExpect(status().isNoContent());

    mvc.perform(post("/api/projects/{projectId}/runs", projectId).header(HttpHeaders.AUTHORIZATION, bearer)
            .contentType(MediaType.APPLICATION_JSON)
            .content("{\"goal\":\"구매\",\"successUrl\":\"https://a.example.com/done\",\"personaIds\":[1],"
                + "\"mode\":\"diagnose\"}"))
        .andExpect(status().isNotFound())
        .andExpect(jsonPath("$.code").value("PRJ-ERR-001"));
  }

  @ParameterizedTest
  @ValueSource(strings = {"queued", "accepted", "running"})
  void delete_withInProgressRun_returnsConflict_andKeepsProject(String status) throws Exception {
    Long projectId = insertOriginalProject();
    insertRun(projectId, "done");      // 끝난 이전 실험
    insertRun(projectId, status);      // 진행 중인 실험

    delete(projectId)
        .andExpect(status().isConflict())
        .andExpect(jsonPath("$.code").value("EXP-ERR-004"))
        .andExpect(jsonPath("$.message").value("프로젝트에 진행 중인 실험이 있습니다."));
    assertThat(jdbcTemplate.queryForObject("SELECT deleted_at FROM projects WHERE project_id = ?", String.class,
        projectId)).isNull();
  }

  @Test
  void delete_withCancelRequestedButStillRunning_returnsConflict() throws Exception {
    Long projectId = insertOriginalProject();
    insertRun(projectId, "running");
    jdbcTemplate.update("UPDATE runs SET cancel_requested = TRUE WHERE project_id = ?", projectId);

    delete(projectId).andExpect(status().isConflict());
  }

  @Test
  void delete_withOnlyFinishedRuns_succeeds() throws Exception {
    Long projectId = insertOriginalProject();
    insertRun(projectId, "done");
    insertRun(projectId, "failed");
    insertRun(projectId, "cancelled");

    delete(projectId).andExpect(status().isNoContent());
  }

  @Test
  void delete_othersOrMissingProject_returnsNotFound() throws Exception {
    Long othersProject = insertProject(insertUser("other@uxight.com"), "남의 프로젝트", "https://c.example.com", null);

    delete(othersProject)
        .andExpect(status().isNotFound())
        .andExpect(jsonPath("$.code").value("PRJ-ERR-001"));
    delete(Long.MAX_VALUE)
        .andExpect(status().isNotFound())
        .andExpect(jsonPath("$.code").value("PRJ-ERR-001"));
    assertThat(jdbcTemplate.queryForObject("SELECT deleted_at FROM projects WHERE project_id = ?", String.class,
        othersProject)).isNull();
  }

  @Test
  void delete_withoutToken_returnsUnauthorized() throws Exception {
    mvc.perform(MockMvcRequestBuilders.delete("/api/projects/{projectId}", insertOriginalProject()))
        .andExpect(status().isUnauthorized())
        .andExpect(jsonPath("$.code").value("AUT-ERR-001"));
  }

  private ResultActions delete(Long projectId) throws Exception {
    ResultActions result = mvc.perform(MockMvcRequestBuilders.delete("/api/projects/{projectId}", projectId)
        .header(HttpHeaders.AUTHORIZATION, bearer));
    entityManager.flush();
    return result;
  }

  private void insertRun(Long projectId, String status) {
    jdbcTemplate.update("INSERT INTO tasks (project_id, goal, success_rule, success_url) "
        + "VALUES (?, '구매', 'rule', 'https://a.example.com/done')", projectId);
    Long taskId = jdbcTemplate.queryForObject("SELECT LAST_INSERT_ID()", Long.class);
    jdbcTemplate.update("INSERT INTO runs (project_id, task_id, mode, target_url_snapshot, allowed_domains_snapshot, "
        + "task_snapshot, policy_snapshot, persona_snapshot, status) "
        + "VALUES (?, ?, 'diagnose', 'https://a.example.com', JSON_ARRAY(), JSON_OBJECT(), JSON_OBJECT(), JSON_ARRAY(), ?)",
        projectId, taskId, status);
  }

  private ResultActions update(Long projectId, String json) throws Exception {
    ResultActions result = mvc.perform(patch("/api/projects/{projectId}", projectId)
        .header(HttpHeaders.AUTHORIZATION, bearer)
        .contentType(MediaType.APPLICATION_JSON)
        .content(json));
    entityManager.flush();
    return result;
  }

  private Long insertOriginalProject() {
    jdbcTemplate.update("INSERT INTO projects (user_id, title, target_url, description, allowed_domains) "
        + "VALUES (?, '원래 제목', 'https://a.example.com/start', '원래 설명', JSON_ARRAY('a.example.com', 'b.example.com'))",
        userId);
    return jdbcTemplate.queryForObject("SELECT LAST_INSERT_ID()", Long.class);
  }

  private ResultActions create(String json) throws Exception {
    return mvc.perform(post("/api/projects").header(HttpHeaders.AUTHORIZATION, bearer)
        .contentType(MediaType.APPLICATION_JSON)
        .content(json));
  }

  private long createAndGetId(String json) throws Exception {
    String body = create(json)
        .andExpect(status().isCreated())
        .andExpect(jsonPath("$.projectId").isNumber())
        .andReturn().getResponse().getContentAsString();
    return objectMapper.readTree(body).get("projectId").asLong();
  }

  private List<String> allowedDomainsOf(long projectId) throws Exception {
    String json = jdbcTemplate.queryForObject(
        "SELECT allowed_domains FROM projects WHERE project_id = ?", String.class, projectId);
    return objectMapper.readValue(json, new TypeReference<>() {});
  }

  private Long insertUser(String email) {
    jdbcTemplate.update("INSERT INTO users (email, password_hash, auth_provider, name, role, is_active) "
        + "VALUES (?, 'hash', 'local', '홍길동', 'researcher', TRUE)", email);
    return jdbcTemplate.queryForObject("SELECT user_id FROM users WHERE email = ?", Long.class, email);
  }

  private Long insertProject(Long ownerId, String title, String targetUrl, String description) {
    jdbcTemplate.update("INSERT INTO projects (user_id, title, target_url, description, allowed_domains) "
        + "VALUES (?, ?, ?, ?, JSON_ARRAY('example.com'))", ownerId, title, targetUrl, description);
    return jdbcTemplate.queryForObject("SELECT LAST_INSERT_ID()", Long.class);
  }
}
