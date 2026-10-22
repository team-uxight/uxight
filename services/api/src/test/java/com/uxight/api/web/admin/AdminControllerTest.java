package com.uxight.api.web.admin;

import static org.assertj.core.api.Assertions.assertThat;
import static org.hamcrest.Matchers.hasSize;
import static org.hamcrest.Matchers.nullValue;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.patch;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.uxight.api.domain.user.JwtProvider;
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
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.ResultActions;
import org.springframework.test.web.servlet.request.MockHttpServletRequestBuilder;
import org.springframework.transaction.annotation.Transactional;

/**
 * 계정 목록(GET /api/admin/users) · 역할 변경(PATCH /api/admin/users/{userId}/role) — admin · maintainer 만.
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
        .andExpect(jsonPath("$.content[0].*", hasSize(7)))
        .andExpect(jsonPath("$.content[0].userId").value(google))
        .andExpect(jsonPath("$.content[0].email").value("users-google@uxight.com"))
        .andExpect(jsonPath("$.content[0].name").value(nullValue()))   // 이름 없이 가입한 계정
        .andExpect(jsonPath("$.content[0].role").value("maintainer"))
        .andExpect(jsonPath("$.content[0].authProvider").value("google"))
        .andExpect(jsonPath("$.content[0].isActive").value(true))
        .andExpect(jsonPath("$.content[0].createdAt").isNotEmpty())
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
    // 메인테이너 · 관리자를 부여하거나, 메인테이너 · 관리자 계정을 바꾸면 403
    for (String[] c : new String[][] {
        {String.valueOf(researcher), "maintainer"}, {String.valueOf(researcher), "admin"},
        {String.valueOf(otherMaintainer), "researcher"}, {String.valueOf(adminId), "researcher"},
        {String.valueOf(maintainer), "researcher"}}) {
      changeRole(maintainer, Long.valueOf(c[0]), "{\"role\":\"" + c[1] + "\"}")
          .andExpect(status().isForbidden())
          .andExpect(jsonPath("$.code").value("AUT-ERR-006"));
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
