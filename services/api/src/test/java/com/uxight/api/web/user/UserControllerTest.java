package com.uxight.api.web.user;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.uxight.api.domain.user.JwtProvider;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.HttpHeaders;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.transaction.annotation.Transactional;

/**
 * 대시보드 사용자 정보(GET /api/users/me)의 응답 필드를 본다. 토큰 · 비활성 계정 오류는 LoginCheckInterceptorTest 가 본다.
 * 실제 MySQL, 테스트마다 롤백.
 */
@SpringBootTest
@AutoConfigureMockMvc
@Transactional
class UserControllerTest {

  @Autowired
  private MockMvc mvc;

  @Autowired
  private JwtProvider jwtProvider;

  @Autowired
  private JdbcTemplate jdbcTemplate;

  @ParameterizedTest
  @ValueSource(strings = {"researcher", "maintainer", "admin"})
  void me_returnsUserIdNameAndRole(String role) throws Exception {
    jdbcTemplate.update("INSERT INTO users (email, password_hash, auth_provider, name, role, is_active) "
        + "VALUES ('me-test@uxight.com', 'hash', 'local', '대시보드', ?, TRUE)", role);
    Long userId = jdbcTemplate.queryForObject("SELECT LAST_INSERT_ID()", Long.class);

    mvc.perform(get("/api/users/me").header(HttpHeaders.AUTHORIZATION, "Bearer " + jwtProvider.createAccessToken(userId)))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.userId").value(userId))
        .andExpect(jsonPath("$.name").value("대시보드"))
        .andExpect(jsonPath("$.role").value(role));
  }
}
