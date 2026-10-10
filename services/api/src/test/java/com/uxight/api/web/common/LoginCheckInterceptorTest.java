package com.uxight.api.web.common;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.options;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.uxight.api.domain.user.JwtProvider;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.HttpHeaders;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.ResultActions;
import org.springframework.transaction.annotation.Transactional;

/** 로그인이 필요한 API(GET /api/users/me)로 access 토큰 검증을 본다. 실제 MySQL, 테스트마다 롤백. */
@SpringBootTest
@AutoConfigureMockMvc
@Transactional
class LoginCheckInterceptorTest {

  @Autowired
  private MockMvc mvc;

  @Autowired
  private JwtProvider jwtProvider;

  @Autowired
  private JdbcTemplate jdbcTemplate;

  @Value("${uxight.web-origin}")
  private String webOrigin;

  @Test
  void validToken_passesUserIdToController() throws Exception {
    Long userId = insertUser("me@uxight.com", true);

    me("Bearer " + jwtProvider.createAccessToken(userId))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.userId").value(userId))
        .andExpect(jsonPath("$.role").value("researcher"));
  }

  @Test
  void missingOrMalformedToken_returnsUnauthorized() throws Exception {
    expectUnauthorized(mvc.perform(get("/api/users/me")));
    expectUnauthorized(me("Basic abc"));
    expectUnauthorized(me("Bearer not-a-jwt"));
  }

  @Test
  void tokenOfUnknownUser_returnsUnauthorized() throws Exception {
    expectUnauthorized(me("Bearer " + jwtProvider.createAccessToken(Long.MAX_VALUE)));
  }

  @Test
  void tokenOfInactiveUser_returnsUnauthorized() throws Exception {
    Long userId = insertUser("inactive@uxight.com", false);

    me("Bearer " + jwtProvider.createAccessToken(userId))
        .andExpect(status().isUnauthorized())
        .andExpect(jsonPath("$.code").value("AUT-ERR-005"));
  }

  @Test
  void corsPreflight_passesWithoutToken() throws Exception {
    mvc.perform(options("/api/users/me")
            .header(HttpHeaders.ORIGIN, webOrigin)
            .header(HttpHeaders.ACCESS_CONTROL_REQUEST_METHOD, "GET")
            .header(HttpHeaders.ACCESS_CONTROL_REQUEST_HEADERS, "authorization"))
        .andExpect(status().isOk());
  }

  private ResultActions me(String authorization) throws Exception {
    return mvc.perform(get("/api/users/me").header(HttpHeaders.AUTHORIZATION, authorization));
  }

  private void expectUnauthorized(ResultActions result) throws Exception {
    result.andExpect(status().isUnauthorized())
        .andExpect(jsonPath("$.code").value("AUT-ERR-001"))
        .andExpect(jsonPath("$.message").value("인증이 필요합니다."));
  }

  private Long insertUser(String email, boolean active) {
    jdbcTemplate.update("INSERT INTO users (email, password_hash, auth_provider, name, role, is_active) "
        + "VALUES (?, 'hash', 'local', '홍길동', 'researcher', ?)", email, active);
    return jdbcTemplate.queryForObject("SELECT user_id FROM users WHERE email = ?", Long.class, email);
  }
}
