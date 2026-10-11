package com.uxight.api.web.project;

import static org.assertj.core.api.Assertions.assertThat;
import static org.hamcrest.Matchers.contains;
import static org.hamcrest.Matchers.empty;
import static org.hamcrest.Matchers.hasKey;
import static org.hamcrest.Matchers.not;
import static org.hamcrest.Matchers.nullValue;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.uxight.api.domain.user.JwtProvider;
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
