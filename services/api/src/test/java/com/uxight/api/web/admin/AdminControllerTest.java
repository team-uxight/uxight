package com.uxight.api.web.admin;

import static org.hamcrest.Matchers.hasSize;
import static org.hamcrest.Matchers.nullValue;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

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
import org.springframework.test.web.servlet.request.MockHttpServletRequestBuilder;
import org.springframework.transaction.annotation.Transactional;

/**
 * 계정 목록(GET /api/admin/users) — admin · maintainer 만. 가입한 모든 계정을 최근 가입 순으로 페이지 단위로 돌려준다.
 * 실제 MySQL, 테스트마다 롤백. seed 계정이 있을 수 있어 건수는 테스트 안에서 센 값과 비교한다.
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
