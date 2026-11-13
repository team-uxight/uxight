package com.uxight.api.web.admin;

import static org.assertj.core.api.Assertions.assertThat;
import static org.hamcrest.Matchers.hasSize;
import static org.hamcrest.Matchers.nullValue;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.patch;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.uxight.api.domain.user.JwtProvider;
import jakarta.servlet.http.Cookie;
import jakarta.persistence.EntityManager;
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
import org.springframework.mock.web.MockHttpServletResponse;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.ResultActions;
import org.springframework.test.web.servlet.request.MockHttpServletRequestBuilder;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.Map;

/**
 * 계정 목록(GET /api/admin/users) · 역할 변경(PATCH .../role) · 활성 상태 변경(PATCH .../active) — admin · maintainer 만.
 * 실제 MySQL, 테스트마다 롤백. seed 계정이 있을 수 있어 건수는 테스트 안에서 센 값과 비교하고,
 * 마지막 관리자를 보는 테스트는 다른 관리자를 리서처로 내려 둔다(롤백된다).
 */
@SpringBootTest
@AutoConfigureMockMvc
@Transactional
class AdminControllerTest {

  @Autowired
  private MockMvc mvc;

  @Autowired
  private JwtProvider jwtProvider;

  @Autowired
  private JdbcTemplate jdbcTemplate;

  @Autowired
  private EntityManager entityManager;

  @Autowired
  private ObjectMapper objectMapper;

  @Autowired
  private PasswordEncoder passwordEncoder;

  private Long adminId;

  @BeforeEach
  void setUp() {
    adminId = insertUser("users-admin@uxight.com", "local", null, "관리자", "admin", true);
  }

  @Test
  void admin_getsAllAccounts_newestFirst_withoutSecrets() throws Exception {
    Long inactive = insertUser("users-inactive@uxight.com", "local", null, "비활성", "researcher", false);
    Long google = insertUser("users-google@uxight.com", "google", "google-sub-123", null, "maintainer", true);
    long total = jdbcTemplate.queryForObject("SELECT COUNT(*) FROM users", Long.class);

    users(adminId, get("/api/admin/users"))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.*", hasSize(5)))
        .andExpect(jsonPath("$.page").value(0))
        .andExpect(jsonPath("$.size").value(20))   // 기본값
        .andExpect(jsonPath("$.totalElements").value(total))
        // 최근 가입 순 — 방금 넣은 Google 계정이 맨 앞
        .andExpect(jsonPath("$.content[0].*", hasSize(9)))
        .andExpect(jsonPath("$.content[0].userId").value(google))
        .andExpect(jsonPath("$.content[0].email").value("users-google@uxight.com"))
        .andExpect(jsonPath("$.content[0].name").value(nullValue()))   // 이름 없이 가입한 계정
        .andExpect(jsonPath("$.content[0].role").value("maintainer"))
        .andExpect(jsonPath("$.content[0].authProvider").value("google"))
        .andExpect(jsonPath("$.content[0].isActive").value(true))
        .andExpect(jsonPath("$.content[0].createdAt").isNotEmpty())
        .andExpect(jsonPath("$.content[0].lastLoginAt").value(nullValue()))   // 로그인한 적 없음
        .andExpect(jsonPath("$.content[0].totalCostUsd").value(0.0))          // 회차 없음
        .andExpect(jsonPath("$.content[0].googleSub").doesNotExist())
        .andExpect(jsonPath("$.content[0].passwordHash").doesNotExist())
        // 비활성 계정도 목록에 있다
        .andExpect(jsonPath("$.content[1].userId").value(inactive))
        .andExpect(jsonPath("$.content[1].authProvider").value("local"))
        .andExpect(jsonPath("$.content[1].isActive").value(false))
        .andExpect(jsonPath("$.content[2].userId").value(adminId))
        .andExpect(jsonPath("$.content[2].role").value("admin"));
  }

  @Test
  void pagesBySize_andPageBeyondTheEndIsEmpty() throws Exception {
    Long first = insertUser("users-1@uxight.com", "local", null, "1", "researcher", true);
    Long second = insertUser("users-2@uxight.com", "local", null, "2", "researcher", true);
    Long third = insertUser("users-3@uxight.com", "local", null, "3", "researcher", true);
    long total = jdbcTemplate.queryForObject("SELECT COUNT(*) FROM users", Long.class);

    users(adminId, get("/api/admin/users").param("page", "0").param("size", "2"))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.content", hasSize(2)))
        .andExpect(jsonPath("$.content[0].userId").value(third))
        .andExpect(jsonPath("$.content[1].userId").value(second))
        .andExpect(jsonPath("$.totalElements").value(total))
        .andExpect(jsonPath("$.totalPages").value((total + 1) / 2));
    users(adminId, get("/api/admin/users").param("page", "1").param("size", "2"))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.page").value(1))
        .andExpect(jsonPath("$.content[0].userId").value(first))
        .andExpect(jsonPath("$.content[1].userId").value(adminId));
    users(adminId, get("/api/admin/users").param("page", "1000").param("size", "2"))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.content", hasSize(0)))
        .andExpect(jsonPath("$.totalElements").value(total));
  }

  @Test
  void maintainer_canListAccounts() throws Exception {
    Long maintainer = insertUser("users-maintainer@uxight.com", "local", null, "메인테이너", "maintainer", true);
    users(maintainer, get("/api/admin/users"))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.content[0].userId").value(maintainer));
  }

  @ParameterizedTest(name = "page={0} size={1} → GLB-ERR-002 {2}")
  @CsvSource({
      "-1, 20, page",
      "0, 0, size",
      "0, -5, size"
  })
  void outOfRangePageOrSize_isBadRequest(String page, String size, String field) throws Exception {
    users(adminId, get("/api/admin/users").param("page", page).param("size", size))
        .andExpect(status().isBadRequest())
        .andExpect(jsonPath("$.code").value("GLB-ERR-002"))
        .andExpect(jsonPath("$.fieldErrors[0].field").value(field));
  }

  @ParameterizedTest(name = "page={0} size={1} → GLB-ERR-001")
  @CsvSource({
      "abc, 20",
      "0, 1.5"
  })
  void nonNumericPageOrSize_isBadRequest(String page, String size) throws Exception {
    users(adminId, get("/api/admin/users").param("page", page).param("size", size))
        .andExpect(status().isBadRequest())
        .andExpect(jsonPath("$.code").value("GLB-ERR-001"));
  }

  @Test
  void researcher_isForbidden() throws Exception {
    Long researcher = insertUser("users-researcher@uxight.com", "local", null, "리서처", "researcher", true);
    users(researcher, get("/api/admin/users"))
        .andExpect(status().isForbidden())
        .andExpect(jsonPath("$.code").value("AUT-ERR-006"));
  }

  @Test
  void withoutTokenOrByInactiveAdmin_isUnauthorized() throws Exception {
    mvc.perform(get("/api/admin/users"))
        .andExpect(status().isUnauthorized())
        .andExpect(jsonPath("$.code").value("AUT-ERR-001"));

    jdbcTemplate.update("UPDATE users SET is_active = FALSE WHERE user_id = ?", adminId);
    users(adminId, get("/api/admin/users"))
        .andExpect(status().isUnauthorized())
        .andExpect(jsonPath("$.code").value("AUT-ERR-005"));
  }

  /** 누적 비용은 그 계정 프로젝트의 모든 회차 비용 합 — 진행 중 · 취소 회차와 삭제된 프로젝트의 회차도 센다. 다른 계정 회차는 섞이지 않는다. */
  @Test
  void totalCost_sumsAllRunsOfTheAccountsProjects_includingDeletedProjectsAndRunningRuns() throws Exception {
    Long researcher = insertUser("users-cost@uxight.com", "local", null, "비용", "researcher", true);
    Long other = insertUser("users-cost-other@uxight.com", "local", null, "다른", "researcher", true);
    Long project = insertProject(researcher);
    Long deletedProject = insertProject(researcher);
    jdbcTemplate.update("UPDATE projects SET deleted_at = NOW() WHERE project_id = ?", deletedProject);
    insertRun(project, "done", "1.2500");
    insertRun(project, "running", "0.5000");
    insertRun(project, "cancelled", null);        // 비용 기록 전에 취소 — 합에서 빠진다
    insertRun(deletedProject, "failed", "0.2500");
    insertRun(insertProject(other), "done", "9.0000");

    users(adminId, get("/api/admin/users"))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.content[0].userId").value(other))
        .andExpect(jsonPath("$.content[0].totalCostUsd").value(9.0))
        .andExpect(jsonPath("$.content[1].userId").value(researcher))
        .andExpect(jsonPath("$.content[1].totalCostUsd").value(2.0));
  }

  /** 마지막 로그인은 이메일 로그인 성공 때 기록된다. 비밀번호가 틀린 로그인과 토큰 재발급은 바꾸지 않는다. */
  @Test
  void lastLoginAt_isSetOnSuccessfulLogin_notOnFailedLoginOrRefresh() throws Exception {
    String body = createUser(adminId, "{\"email\":\"users-login@uxight.com\",\"name\":\"로그인\"}")
        .andExpect(status().isCreated()).andReturn().getResponse().getContentAsString();
    String password = objectMapper.readTree(body).get("initialPassword").asText();
    Long target = jdbcTemplate.queryForObject("SELECT user_id FROM users WHERE email = 'users-login@uxight.com'", Long.class);

    login("users-login@uxight.com", "wrong1234").andExpect(status().isUnauthorized());
    entityManager.flush();
    assertThat(lastLoginAtOf(target)).isNull();

    Cookie refreshCookie = login("users-login@uxight.com", password)
        .andExpect(status().isOk()).andReturn().getResponse().getCookie("refreshToken");
    entityManager.flush();
    assertThat(lastLoginAtOf(target)).isNotNull();
    users(adminId, get("/api/admin/users"))
        .andExpect(jsonPath("$.content[0].userId").value(target))
        .andExpect(jsonPath("$.content[0].lastLoginAt").isNotEmpty());

    jdbcTemplate.update("UPDATE users SET last_login_at = '2026-01-01 00:00:00' WHERE user_id = ?", target);
    mvc.perform(post("/api/auth/refresh").cookie(refreshCookie)).andExpect(status().isOk());
    entityManager.flush();
    assertThat(lastLoginAtOf(target)).hasToString("2026-01-01T00:00");
  }

  // ───────── 계정 생성 ─────────

  /** 완료 기준: 리서처 계정을 만들고, 초기 비밀번호는 응답에만 있고 DB 에는 해시만, 그 비밀번호로 로그인된다, 감사 로그가 남는다. */
  @ParameterizedTest(name = "{0} 가 만든다")
  @CsvSource({"admin", "maintainer"})
  void adminOrMaintainer_createsResearcher_withOneTimePassword_andAuditLog(String actorRole) throws Exception {
    Long actor = "admin".equals(actorRole) ? adminId
        : insertUser("users-create-actor@uxight.com", "local", null, "메인테이너", "maintainer", true);
    long auditBefore = auditLogCount();

    String body = createUser(actor, "{\"email\":\"users-created@uxight.com\",\"name\":\"새 리서처\"}")
        .andExpect(status().isCreated())
        .andExpect(jsonPath("$.*", hasSize(2)))
        .andExpect(jsonPath("$.userId").isNumber())
        .andExpect(jsonPath("$.initialPassword").isString())
        .andReturn().getResponse().getContentAsString();
    Long userId = objectMapper.readTree(body).get("userId").asLong();
    String initialPassword = objectMapper.readTree(body).get("initialPassword").asText();

    entityManager.flush();
    Map<String, Object> row = jdbcTemplate.queryForMap(
        "SELECT email, name, role, auth_provider, is_active, password_hash, google_sub, last_login_at FROM users WHERE user_id = ?",
        userId);
    assertThat(row.get("email")).isEqualTo("users-created@uxight.com");
    assertThat(row.get("name")).isEqualTo("새 리서처");
    assertThat(row.get("role")).isEqualTo("researcher");
    assertThat(row.get("auth_provider")).isEqualTo("local");
    assertThat(row.get("is_active")).isEqualTo(true);
    assertThat(row.get("google_sub")).isNull();
    assertThat(row.get("last_login_at")).isNull();
    String hash = (String) row.get("password_hash");
    assertThat(hash).isNotEqualTo(initialPassword);
    assertThat(passwordEncoder.matches(initialPassword, hash)).isTrue();

    assertThat(auditLogCount()).isEqualTo(auditBefore + 1);
    Map<String, Object> audit = jdbcTemplate.queryForMap("SELECT actor, action, target, "
        + "JSON_UNQUOTE(JSON_EXTRACT(detail, '$.email')) AS email, JSON_UNQUOTE(JSON_EXTRACT(detail, '$.name')) AS name, "
        + "JSON_UNQUOTE(JSON_EXTRACT(detail, '$.role')) AS role, JSON_LENGTH(detail) AS keys_count, "
        + "CAST(detail AS CHAR) AS detail_text FROM audit_log ORDER BY audit_log_id DESC LIMIT 1");
    assertThat(audit.get("actor")).isEqualTo("user:" + actor);
    assertThat(audit.get("action")).isEqualTo("user.create");
    assertThat(audit.get("target")).isEqualTo("user:" + userId);
    assertThat(audit.get("email")).isEqualTo("users-created@uxight.com");
    assertThat(audit.get("name")).isEqualTo("새 리서처");
    assertThat(audit.get("role")).isEqualTo("researcher");
    assertThat(((Number) audit.get("keys_count")).intValue()).isEqualTo(3);
    assertThat((String) audit.get("detail_text")).doesNotContain(initialPassword);

    login("users-created@uxight.com", initialPassword)
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.accessToken").isNotEmpty());
  }

  /** 같은 이메일이 있으면 이메일 가입이든 Google 가입이든 409 AUT-ERR-007 — 계정 · 감사 로그가 늘지 않는다. */
  @ParameterizedTest(name = "{0} 가입 계정과 같은 이메일")
  @CsvSource({"local, ", "google, google-sub-dup"})
  void duplicateEmail_isConflict(String authProvider, String googleSub) throws Exception {
    insertUser("users-dup@uxight.com", authProvider, googleSub, "기존", "researcher", true);
    long usersBefore = jdbcTemplate.queryForObject("SELECT COUNT(*) FROM users", Long.class);
    long auditBefore = auditLogCount();

    createUser(adminId, "{\"email\":\"users-dup@uxight.com\",\"name\":\"중복\"}")
        .andExpect(status().isConflict())
        .andExpect(jsonPath("$.code").value("AUT-ERR-007"));
    assertThat(jdbcTemplate.queryForObject("SELECT COUNT(*) FROM users", Long.class)).isEqualTo(usersBefore);
    assertThat(auditLogCount()).isEqualTo(auditBefore);
  }

  @ParameterizedTest(name = "{0} → GLB-ERR-002 {1}")
  @CsvSource(delimiter = '|', value = {
      "{\"name\":\"이름\"}|email",
      "{\"email\":\"not-an-email\",\"name\":\"이름\"}|email",
      "{\"email\":\"users-noname@uxight.com\"}|name",
      "{\"email\":\"users-noname@uxight.com\",\"name\":\" \"}|name"
  })
  void invalidCreateBody_isBadRequest(String body, String field) throws Exception {
    createUser(adminId, body)
        .andExpect(status().isBadRequest())
        .andExpect(jsonPath("$.code").value("GLB-ERR-002"))
        .andExpect(jsonPath("$.fieldErrors[0].field").value(field));
  }

  @Test
  void create_byResearcher_isForbidden_andWithoutToken_isUnauthorized() throws Exception {
    Long researcher = insertUser("users-create-researcher@uxight.com", "local", null, "리서처", "researcher", true);
    createUser(researcher, "{\"email\":\"users-by-researcher@uxight.com\",\"name\":\"x\"}")
        .andExpect(status().isForbidden())
        .andExpect(jsonPath("$.code").value("AUT-ERR-006"));
    mvc.perform(post("/api/admin/users").contentType(MediaType.APPLICATION_JSON)
            .content("{\"email\":\"users-no-token@uxight.com\",\"name\":\"x\"}"))
        .andExpect(status().isUnauthorized())
        .andExpect(jsonPath("$.code").value("AUT-ERR-001"));
  }

  // ───────── PATCH /api/admin/users/{userId}/role ─────────

  @ParameterizedTest(name = "admin: researcher → {0}")
  @CsvSource({"maintainer", "admin"})
  void admin_changesRole_andAuditLogHasBeforeAndAfter(String role) throws Exception {
    Long target = insertUser("role-target@uxight.com", "local", null, "대상", "researcher", true);

    changeRole(adminId, target, "{\"role\":\"" + role + "\"}")
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.*", hasSize(2)))
        .andExpect(jsonPath("$.userId").value(target))
        .andExpect(jsonPath("$.role").value(role));

    entityManager.flush();
    assertThat(roleOf(target)).isEqualTo(role);
    assertThat(jdbcTemplate.queryForMap("SELECT actor, action, target, JSON_UNQUOTE(JSON_EXTRACT(detail, '$.before')) AS before_role, "
            + "JSON_UNQUOTE(JSON_EXTRACT(detail, '$.after')) AS after_role FROM audit_log ORDER BY audit_log_id DESC LIMIT 1"))
        .containsEntry("actor", "user:" + adminId)
        .containsEntry("action", "user.role_update")
        .containsEntry("target", "user:" + target)
        .containsEntry("before_role", "researcher")
        .containsEntry("after_role", role);
  }

  @Test
  void admin_canDemoteAnotherAdmin_whileAnotherActiveAdminRemains() throws Exception {
    Long other = insertUser("role-other-admin@uxight.com", "local", null, "다른 관리자", "admin", true);

    changeRole(adminId, other, "{\"role\":\"maintainer\"}")
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.role").value("maintainer"));
  }

  @Test
  void sameRole_isOk_withoutAuditLog() throws Exception {
    Long target = insertUser("role-same@uxight.com", "local", null, "대상", "maintainer", true);
    long before = auditLogCount();

    changeRole(adminId, target, "{\"role\":\"maintainer\"}")
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.role").value("maintainer"));
    assertThat(auditLogCount()).isEqualTo(before);
  }

  @ParameterizedTest(name = "마지막 관리자 → {0}: 409")
  @CsvSource({"maintainer", "researcher"})
  void demotingLastActiveAdmin_isConflict_evenSelf(String role) throws Exception {
    leaveOnlyAdmin(adminId);
    insertUser("role-maintainer@uxight.com", "local", null, "메인테이너", "maintainer", true);   // 메인테이너가 있어도
    insertUser("role-inactive-admin@uxight.com", "local", null, "비활성 관리자", "admin", false);   // 로그인 못 하는 관리자는 세지 않는다
    long before = auditLogCount();

    changeRole(adminId, adminId, "{\"role\":\"" + role + "\"}")
        .andExpect(status().isConflict())
        .andExpect(jsonPath("$.code").value("ACC-ERR-002"));

    entityManager.flush();
    assertThat(roleOf(adminId)).isEqualTo("admin");
    assertThat(auditLogCount()).isEqualTo(before);
  }

  @Test
  void demotingInactiveAdmin_isOk_evenIfOnlyOneActiveAdmin() throws Exception {
    leaveOnlyAdmin(adminId);
    Long inactive = insertUser("role-inactive-admin@uxight.com", "local", null, "비활성 관리자", "admin", false);

    changeRole(adminId, inactive, "{\"role\":\"researcher\"}")
        .andExpect(status().isOk());
  }

  @Test
  void changedRole_appliesFromTheTargetsNextRequest() throws Exception {
    Long target = insertUser("role-next@uxight.com", "local", null, "대상", "researcher", true);
    users(target, get("/api/admin/users")).andExpect(status().isForbidden());

    changeRole(adminId, target, "{\"role\":\"maintainer\"}").andExpect(status().isOk());
    users(target, get("/api/admin/users")).andExpect(status().isOk());   // 같은 access 토큰으로 바로

    changeRole(adminId, target, "{\"role\":\"researcher\"}").andExpect(status().isOk());
    users(target, get("/api/admin/users")).andExpect(status().isForbidden());
  }

  @Test
  void maintainer_canOnlyKeepResearcherAsResearcher() throws Exception {
    Long maintainer = insertUser("role-maintainer@uxight.com", "local", null, "메인테이너", "maintainer", true);
    Long researcher = insertUser("role-researcher@uxight.com", "local", null, "리서처", "researcher", true);
    Long otherMaintainer = insertUser("role-maintainer2@uxight.com", "local", null, "메인테이너2", "maintainer", true);

    changeRole(maintainer, researcher, "{\"role\":\"researcher\"}")
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.role").value("researcher"));
    // 리서처에게 메인테이너 · 관리자를 부여하면 403 — 권한 부족
    for (String role : new String[] {"maintainer", "admin"}) {
      changeRole(maintainer, researcher, "{\"role\":\"" + role + "\"}")
          .andExpect(status().isForbidden())
          .andExpect(jsonPath("$.code").value("AUT-ERR-006"));
    }
    // 메인테이너 · 관리자 계정(자기 포함)이 대상이면 409 — 대상 계정이 변경 대상이 아니다. 관리자를 부여하려 해도 대상 확인이 먼저
    for (String[] c : new String[][] {
        {String.valueOf(otherMaintainer), "researcher"}, {String.valueOf(adminId), "researcher"},
        {String.valueOf(maintainer), "researcher"}, {String.valueOf(otherMaintainer), "admin"}}) {
      changeRole(maintainer, Long.valueOf(c[0]), "{\"role\":\"" + c[1] + "\"}")
          .andExpect(status().isConflict())
          .andExpect(jsonPath("$.code").value("ACC-ERR-003"));
    }
    entityManager.flush();
    assertThat(roleOf(researcher)).isEqualTo("researcher");
    assertThat(roleOf(otherMaintainer)).isEqualTo("maintainer");
    assertThat(roleOf(adminId)).isEqualTo("admin");
  }

  @Test
  void researcher_isForbidden_forRoleChange() throws Exception {
    Long researcher = insertUser("role-researcher@uxight.com", "local", null, "리서처", "researcher", true);
    changeRole(researcher, researcher, "{\"role\":\"admin\"}")
        .andExpect(status().isForbidden())
        .andExpect(jsonPath("$.code").value("AUT-ERR-006"));
    entityManager.flush();
    assertThat(roleOf(researcher)).isEqualTo("researcher");
  }

  @Test
  void unknownAccount_isNotFound() throws Exception {
    changeRole(adminId, 999_999_999L, "{\"role\":\"researcher\"}")
        .andExpect(status().isNotFound())
        .andExpect(jsonPath("$.code").value("ACC-ERR-001"));
  }

  @ParameterizedTest(name = "[{index}] {0} → GLB-ERR-002 role")
  @CsvSource(delimiter = '|', value = {
      "{\"role\":\"owner\"}",
      "{\"role\":\"Admin\"}",   // 대소문자도 정확히
      "{}",
      "{\"role\":null}"
  })
  void invalidRole_isBadRequest(String body) throws Exception {
    Long target = insertUser("role-target@uxight.com", "local", null, "대상", "researcher", true);
    changeRole(adminId, target, body)
        .andExpect(status().isBadRequest())
        .andExpect(jsonPath("$.code").value("GLB-ERR-002"))
        .andExpect(jsonPath("$.fieldErrors[0].field").value("role"));
  }

  @Test
  void malformedBodyOrUserId_isBadRequest() throws Exception {
    Long target = insertUser("role-target@uxight.com", "local", null, "대상", "researcher", true);
    changeRole(adminId, target, "{\"role\":")
        .andExpect(status().isBadRequest())
        .andExpect(jsonPath("$.code").value("GLB-ERR-001"));
    mvc.perform(patch("/api/admin/users/abc/role")
            .header(HttpHeaders.AUTHORIZATION, "Bearer " + jwtProvider.createAccessToken(adminId))
            .contentType(MediaType.APPLICATION_JSON).content("{\"role\":\"admin\"}"))
        .andExpect(status().isBadRequest())
        .andExpect(jsonPath("$.code").value("GLB-ERR-001"));
  }

  @Test
  void roleChange_withoutToken_isUnauthorized() throws Exception {
    mvc.perform(patch("/api/admin/users/{userId}/role", adminId)
            .contentType(MediaType.APPLICATION_JSON).content("{\"role\":\"researcher\"}"))
        .andExpect(status().isUnauthorized())
        .andExpect(jsonPath("$.code").value("AUT-ERR-001"));
  }

  // ───────── PATCH /api/admin/users/{userId}/active ─────────

  @ParameterizedTest(name = "{0} 이 리서처를 비활성화 · 다시 활성화")
  @CsvSource({"admin", "maintainer"})
  void adminOrMaintainer_togglesResearcher_andAuditLogsEachChange(String actorRole) throws Exception {
    Long actor = actorRole.equals("admin") ? adminId
        : insertUser("active-maintainer@uxight.com", "local", null, "메인테이너", "maintainer", true);
    Long target = insertUser("active-target@uxight.com", "local", null, "대상", "researcher", true);

    changeActive(actor, target, "{\"isActive\":false}")
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.*", hasSize(2)))
        .andExpect(jsonPath("$.userId").value(target))
        .andExpect(jsonPath("$.isActive").value(false));
    entityManager.flush();
    assertThat(activeOf(target)).isFalse();
    assertThat(lastAuditLog())
        .containsEntry("actor", "user:" + actor)
        .containsEntry("action", "user.active_update")
        .containsEntry("target", "user:" + target)
        .containsEntry("before_value", "true")
        .containsEntry("after_value", "false");

    changeActive(actor, target, "{\"isActive\":true}")
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.isActive").value(true));
    entityManager.flush();
    assertThat(activeOf(target)).isTrue();
    assertThat(lastAuditLog()).containsEntry("before_value", "false").containsEntry("after_value", "true");
  }

  @ParameterizedTest(name = "이미 isActive={0} → 200 · 감사 로그 없음")
  @CsvSource({"true", "false"})
  void sameActiveState_isOk_withoutAuditLog(boolean active) throws Exception {
    Long target = insertUser("active-same@uxight.com", "local", null, "대상", "researcher", active);
    long before = auditLogCount();

    for (int i = 0; i < 2; i++) {   // 여러 번 보내도 결과가 같다
      changeActive(adminId, target, "{\"isActive\":" + active + "}")
          .andExpect(status().isOk())
          .andExpect(jsonPath("$.isActive").value(active));
    }
    assertThat(auditLogCount()).isEqualTo(before);
  }

  @ParameterizedTest(name = "{0} 이 {1} 계정 → 409 ACC-ERR-003")
  @CsvSource({
      "admin, admin",
      "admin, maintainer",
      "maintainer, admin",
      "maintainer, maintainer"
  })
  void adminOrMaintainerAccount_isNotChangeTarget_evenForAdmin(String actorRole, String targetRole) throws Exception {
    Long actor = actorRole.equals("admin") ? adminId
        : insertUser("active-actor@uxight.com", "local", null, "요청자", "maintainer", true);
    Long target = insertUser("active-" + targetRole + "@uxight.com", "local", null, "대상", targetRole, true);
    long before = auditLogCount();

    changeActive(actor, target, "{\"isActive\":false}")
        .andExpect(status().isConflict())
        .andExpect(jsonPath("$.code").value("ACC-ERR-003"))
        .andExpect(jsonPath("$.message").value("해당 계정은 변경 대상이 아닙니다."));
    entityManager.flush();
    assertThat(activeOf(target)).isTrue();
    assertThat(auditLogCount()).isEqualTo(before);
  }

  @Test
  void selfDeactivation_isNotChangeTarget_becauseActorIsNeverResearcher() throws Exception {
    changeActive(adminId, adminId, "{\"isActive\":false}")
        .andExpect(status().isConflict())
        .andExpect(jsonPath("$.code").value("ACC-ERR-003"));
  }

  @Test
  void activeChange_byResearcher_isForbidden_andUnknownAccount_isNotFound() throws Exception {
    Long researcher = insertUser("active-researcher@uxight.com", "local", null, "리서처", "researcher", true);
    changeActive(researcher, researcher, "{\"isActive\":false}")
        .andExpect(status().isForbidden())
        .andExpect(jsonPath("$.code").value("AUT-ERR-006"));
    changeActive(adminId, 999_999_999L, "{\"isActive\":false}")
        .andExpect(status().isNotFound())
        .andExpect(jsonPath("$.code").value("ACC-ERR-001"));
  }

  @ParameterizedTest(name = "[{index}] {0} → {1}")
  @CsvSource(delimiter = '|', value = {
      "{}|GLB-ERR-002",
      "{\"isActive\":null}|GLB-ERR-002",
      "{\"isActive\":\"yes\"}|GLB-ERR-001",
      "{\"isActive\":|GLB-ERR-001"
  })
  void invalidBody_isBadRequest(String body, String errorCode) throws Exception {
    Long target = insertUser("active-target@uxight.com", "local", null, "대상", "researcher", true);
    ResultActions result = changeActive(adminId, target, body)
        .andExpect(status().isBadRequest())
        .andExpect(jsonPath("$.code").value(errorCode));
    if (errorCode.equals("GLB-ERR-002")) {
      result.andExpect(jsonPath("$.fieldErrors[0].field").value("isActive"));
    }
  }

  /** 완료 기준: 비활성화한 계정은 다음 요청 · 로그인 · 토큰 갱신에서 거절되고, 다시 활성화하면 같은 refresh 토큰을 이어서 쓴다. */
  @Test
  void deactivatedAccount_isRejectedOnNextRequestLoginAndRefresh_andRefreshTokenWorksAgainAfterReactivation()
      throws Exception {
    mvc.perform(post("/api/auth/signup").contentType(MediaType.APPLICATION_JSON)
            .content("{\"email\":\"active-flow@uxight.com\",\"password\":\"password12\",\"name\":\"흐름\"}"))
        .andExpect(status().isCreated());
    Long target = jdbcTemplate.queryForObject("SELECT user_id FROM users WHERE email = 'active-flow@uxight.com'", Long.class);
    MockHttpServletResponse loginResponse = login("active-flow@uxight.com", "password12")
        .andExpect(status().isOk()).andReturn().getResponse();
    String accessToken = objectMapper.readTree(loginResponse.getContentAsString()).get("accessToken").asText();
    Cookie refreshCookie = loginResponse.getCookie("refreshToken");

    changeActive(adminId, target, "{\"isActive\":false}").andExpect(status().isOk());

    mvc.perform(get("/api/users/me").header(HttpHeaders.AUTHORIZATION, "Bearer " + accessToken))
        .andExpect(status().isUnauthorized())
        .andExpect(jsonPath("$.code").value("AUT-ERR-005"));
    login("active-flow@uxight.com", "password12")
        .andExpect(status().isUnauthorized())
        .andExpect(jsonPath("$.code").value("AUT-ERR-005"));
    mvc.perform(post("/api/auth/refresh").cookie(refreshCookie))
        .andExpect(status().isUnauthorized())
        .andExpect(jsonPath("$.code").value("AUT-ERR-005"));
    entityManager.flush();
    assertThat(jdbcTemplate.queryForObject("SELECT COUNT(*) FROM refresh_tokens WHERE user_id = ? AND revoked_at IS NULL",
        Long.class, target)).isEqualTo(1);   // 비활성화해도 refresh 토큰 행은 지우지 않는다

    changeActive(adminId, target, "{\"isActive\":true}").andExpect(status().isOk());

    mvc.perform(post("/api/auth/refresh").cookie(refreshCookie))   // 다시 로그인하지 않고 이어서
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.accessToken").isNotEmpty());
    mvc.perform(get("/api/users/me").header(HttpHeaders.AUTHORIZATION, "Bearer " + accessToken))
        .andExpect(status().isOk());
  }

  private ResultActions changeActive(Long actorId, Long targetId, String json) throws Exception {
    return mvc.perform(patch("/api/admin/users/{userId}/active", targetId)
        .header(HttpHeaders.AUTHORIZATION, "Bearer " + jwtProvider.createAccessToken(actorId))
        .contentType(MediaType.APPLICATION_JSON)
        .content(json));
  }

  private ResultActions login(String email, String password) throws Exception {
    return mvc.perform(post("/api/auth/login").contentType(MediaType.APPLICATION_JSON)
        .content("{\"email\":\"" + email + "\",\"password\":\"" + password + "\"}"));
  }

  private boolean activeOf(Long userId) {
    return jdbcTemplate.queryForObject("SELECT is_active FROM users WHERE user_id = ?", Boolean.class, userId);
  }

  private Map<String, Object> lastAuditLog() {
    return jdbcTemplate.queryForMap("SELECT actor, action, target, "
        + "CAST(JSON_EXTRACT(detail, '$.before') AS CHAR) AS before_value, "
        + "CAST(JSON_EXTRACT(detail, '$.after') AS CHAR) AS after_value FROM audit_log ORDER BY audit_log_id DESC LIMIT 1");
  }

  private ResultActions changeRole(Long actorId, Long targetId, String json) throws Exception {
    return mvc.perform(patch("/api/admin/users/{userId}/role", targetId)
        .header(HttpHeaders.AUTHORIZATION, "Bearer " + jwtProvider.createAccessToken(actorId))
        .contentType(MediaType.APPLICATION_JSON)
        .content(json));
  }

  /** seed 등 다른 관리자를 리서처로 내린다 — 테스트 트랜잭션과 함께 롤백된다. */
  private void leaveOnlyAdmin(Long keepAdminId) {
    jdbcTemplate.update("UPDATE users SET role = 'researcher' WHERE role = 'admin' AND user_id <> ?", keepAdminId);
  }

  private String roleOf(Long userId) {
    return jdbcTemplate.queryForObject("SELECT role FROM users WHERE user_id = ?", String.class, userId);
  }

  private long auditLogCount() {
    return jdbcTemplate.queryForObject("SELECT COUNT(*) FROM audit_log", Long.class);
  }

  private ResultActions createUser(Long actorId, String json) throws Exception {
    return mvc.perform(post("/api/admin/users")
        .header(HttpHeaders.AUTHORIZATION, "Bearer " + jwtProvider.createAccessToken(actorId))
        .contentType(MediaType.APPLICATION_JSON)
        .content(json));
  }

  private LocalDateTime lastLoginAtOf(Long userId) {
    return jdbcTemplate.queryForObject("SELECT last_login_at FROM users WHERE user_id = ?", LocalDateTime.class, userId);
  }

  private Long insertProject(Long ownerId) {
    jdbcTemplate.update("INSERT INTO projects (user_id, title, target_url, allowed_domains) "
        + "VALUES (?, 'p', 'https://a.example.com', JSON_ARRAY('a.example.com'))", ownerId);
    return jdbcTemplate.queryForObject("SELECT LAST_INSERT_ID()", Long.class);
  }

  private void insertRun(Long project, String status, String costUsd) {
    jdbcTemplate.update("INSERT INTO tasks (project_id, goal, success_rule, success_url) "
        + "VALUES (?, 'g', 'rule', 'https://a.example.com/done')", project);
    Long taskId = jdbcTemplate.queryForObject("SELECT LAST_INSERT_ID()", Long.class);
    jdbcTemplate.update("INSERT INTO runs (project_id, task_id, mode, target_url_snapshot, allowed_domains_snapshot, "
            + "task_snapshot, policy_snapshot, persona_snapshot, status, cost_usd) "
            + "VALUES (?, ?, 'diagnose', 'https://a.example.com', JSON_ARRAY(), JSON_OBJECT(), JSON_OBJECT(), JSON_ARRAY(), ?, ?)",
        project, taskId, status, costUsd == null ? null : new BigDecimal(costUsd));
  }

  private ResultActions users(Long userId, MockHttpServletRequestBuilder request) throws Exception {
    return mvc.perform(request.header(HttpHeaders.AUTHORIZATION, "Bearer " + jwtProvider.createAccessToken(userId)));
  }

  private Long insertUser(String email, String authProvider, String googleSub, String name, String role, boolean active) {
    jdbcTemplate.update("INSERT INTO users (email, password_hash, auth_provider, google_sub, name, role, is_active) "
            + "VALUES (?, ?, ?, ?, ?, ?, ?)",
        email, "local".equals(authProvider) ? "hash" : null, authProvider, googleSub, name, role, active);
    return jdbcTemplate.queryForObject("SELECT user_id FROM users WHERE email = ?", Long.class, email);
  }
}
