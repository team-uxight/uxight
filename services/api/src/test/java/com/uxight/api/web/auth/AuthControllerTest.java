package com.uxight.api.web.auth;

import static org.assertj.core.api.Assertions.assertThat;
import static org.hamcrest.Matchers.containsInAnyOrder;
import static org.hamcrest.Matchers.empty;
import static org.hamcrest.Matchers.matchesPattern;
import static org.hamcrest.Matchers.notNullValue;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.uxight.api.domain.user.GoogleAccount;
import com.uxight.api.domain.user.GoogleIdTokenVerifier;
import com.uxight.api.domain.user.RefreshToken;
import jakarta.servlet.http.Cookie;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.ResultActions;
import org.springframework.transaction.annotation.Transactional;

import java.util.Map;
import java.util.Optional;

/**
 * POST /api/auth/signup · login · google 의 요청 · 응답이 설계(7.3 · 8.4 · OpenAPI)와 같은지 본다. 실제 MySQL, 테스트마다 롤백.
 * Google ID 토큰 검증은 GoogleIdTokenVerifierTest 가 보고, 여기서는 검증 결과를 정해 두고 가입 · 로그인 흐름만 본다.
 */
@SpringBootTest
@AutoConfigureMockMvc
@Transactional
class AuthControllerTest {

  private static final String GOOGLE_ID_TOKEN = "google-id-token";

  @Autowired
  private MockMvc mvc;

  @Autowired
  private JdbcTemplate jdbcTemplate;

  @Autowired
  private PasswordEncoder passwordEncoder;

  @MockitoBean
  private GoogleIdTokenVerifier googleIdTokenVerifier;

  @Test
  void signup_created() throws Exception {
    signup("""
        {"email": "researcher@uxight.com", "password": "password12", "name": "홍길동"}
        """)
        .andExpect(status().isCreated())
        .andExpect(jsonPath("$.userId").value(notNullValue()));
  }

  @Test
  void signup_invalidInput_returnsFieldErrors() throws Exception {
    signup("""
        {"email": "not-an-email", "password": "", "name": "홍길동"}
        """)
        .andExpect(status().isBadRequest())
        .andExpect(jsonPath("$.code").value("GLB-ERR-002"))
        .andExpect(jsonPath("$.message").value("입력값이 올바르지 않습니다."))
        .andExpect(jsonPath("$.fieldErrors[*].field").value(containsInAnyOrder("email", "password")));
  }

  // 8~12자 · 영어 소문자 포함 · 숫자 포함 중 하나라도 어기면 거절한다
  @ParameterizedTest
  @ValueSource(strings = {"pass123", "password12345", "passwordab", "12345678", "PASSWORD12"})
  void signup_passwordRuleViolation_returnsFieldError(String password) throws Exception {
    signup("""
        {"email": "researcher@uxight.com", "password": "%s", "name": "홍길동"}
        """.formatted(password))
        .andExpect(status().isBadRequest())
        .andExpect(jsonPath("$.code").value("GLB-ERR-002"))
        .andExpect(jsonPath("$.fieldErrors[0].field").value("password"))
        .andExpect(jsonPath("$.fieldErrors[0].message").value("비밀번호는 영어 소문자와 숫자를 포함한 8~12자여야 합니다"));
  }

  @ParameterizedTest
  @ValueSource(strings = {"abcdefg1", "Password1234"})   // 경계값 8자 · 12자(대문자 허용)
  void signup_passwordRuleBoundary_created(String password) throws Exception {
    signup("""
        {"email": "researcher@uxight.com", "password": "%s", "name": "홍길동"}
        """.formatted(password))
        .andExpect(status().isCreated());
  }

  @Test
  void signup_malformedBody_returnsBadRequest() throws Exception {
    signup("{\"email\": ")
        .andExpect(status().isBadRequest())
        .andExpect(jsonPath("$.code").value("GLB-ERR-001"))
        .andExpect(jsonPath("$.message").value("잘못된 요청입니다."))
        .andExpect(jsonPath("$.fieldErrors").value(empty()));
  }

  @Test
  void signup_duplicateEmail_returnsConflict() throws Exception {
    signup("""
        {"email": "test@uxight.com", "password": "password12", "name": "중복"}
        """)
        .andExpect(status().isConflict())
        .andExpect(jsonPath("$.code").value("AUT-ERR-007"))
        .andExpect(jsonPath("$.message").value("이미 가입된 이메일입니다."))
        .andExpect(jsonPath("$.fieldErrors").value(empty()));
  }

  @Test
  void login_ok_returnsAccessTokenAndRefreshTokenCookie() throws Exception {
    insertUser("login@uxight.com", true);

    login("login@uxight.com", "password12")
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.accessToken").value(notNullValue()))
        .andExpect(header().string(HttpHeaders.SET_COOKIE, matchesPattern(
            "refreshToken=[0-9a-f]{64}; Path=/api/auth; Max-Age=1209600; Expires=.+; Secure; HttpOnly; SameSite=Strict")));
  }

  @Test
  void login_invalidEmail_returnsFieldErrors() throws Exception {
    login("not-an-email", "password12")
        .andExpect(status().isBadRequest())
        .andExpect(jsonPath("$.code").value("GLB-ERR-002"))
        .andExpect(jsonPath("$.message").value("입력값이 올바르지 않습니다."))
        .andExpect(jsonPath("$.fieldErrors[0].field").value("email"))
        .andExpect(jsonPath("$.fieldErrors[0].message").value("이메일 형식이 올바르지 않습니다."));
  }

  @Test
  void login_wrongPassword_returnsUnauthorized() throws Exception {
    insertUser("login@uxight.com", true);

    login("login@uxight.com", "password99")
        .andExpect(status().isUnauthorized())
        .andExpect(header().doesNotExist(HttpHeaders.SET_COOKIE))
        .andExpect(jsonPath("$.code").value("AUT-ERR-002"))
        .andExpect(jsonPath("$.message").value("이메일 또는 비밀번호가 올바르지 않습니다."))
        .andExpect(jsonPath("$.fieldErrors").value(empty()));
  }

  @Test
  void login_unknownEmail_returnsUnauthorized() throws Exception {
    login("no-such-user@uxight.com", "password12")
        .andExpect(status().isUnauthorized())
        .andExpect(jsonPath("$.code").value("AUT-ERR-002"));
  }

  @Test
  void login_inactiveAccount_returnsUnauthorized() throws Exception {
    insertUser("inactive@uxight.com", false);

    login("inactive@uxight.com", "password12")
        .andExpect(status().isUnauthorized())
        .andExpect(jsonPath("$.code").value("AUT-ERR-005"))
        .andExpect(jsonPath("$.message").value("비활성화된 계정입니다."))
        .andExpect(jsonPath("$.fieldErrors").value(empty()));
  }

  @Test
  void refresh_withLoginCookie_returnsNewAccessTokenAndKeepsCookie() throws Exception {
    insertUser("login@uxight.com", true);
    Cookie refreshTokenCookie = login("login@uxight.com", "password12").andReturn().getResponse().getCookie("refreshToken");

    String body = mvc.perform(post("/api/auth/refresh").cookie(refreshTokenCookie))
        .andExpect(status().isOk())
        .andExpect(header().doesNotExist(HttpHeaders.SET_COOKIE))   // rotation 없음 — 쿠키는 그대로
        .andExpect(jsonPath("$.accessToken").value(notNullValue()))
        .andReturn().getResponse().getContentAsString();

    // 새 access 토큰으로 로그인이 필요한 API 를 부를 수 있다
    String accessToken = body.replaceAll(".*\"accessToken\":\"([^\"]+)\".*", "$1");
    mvc.perform(get("/api/users/me").header(HttpHeaders.AUTHORIZATION, "Bearer " + accessToken))
        .andExpect(status().isOk());
  }

  @Test
  void refresh_withoutCookie_returnsUnauthorized() throws Exception {
    mvc.perform(post("/api/auth/refresh"))
        .andExpect(status().isUnauthorized())
        .andExpect(jsonPath("$.code").value("AUT-ERR-004"))
        .andExpect(jsonPath("$.message").value("로그인이 만료되었습니다."))
        .andExpect(jsonPath("$.fieldErrors").value(empty()));
  }

  @Test
  void refresh_unknownToken_returnsUnauthorized() throws Exception {
    mvc.perform(post("/api/auth/refresh").cookie(new Cookie("refreshToken", RefreshToken.newRawToken())))
        .andExpect(status().isUnauthorized())
        .andExpect(jsonPath("$.code").value("AUT-ERR-004"));
  }

  @Test
  void refresh_inactiveAccount_returnsUnauthorized() throws Exception {
    insertUser("inactive@uxight.com", false);
    String raw = RefreshToken.newRawToken();
    jdbcTemplate.update("INSERT INTO refresh_tokens (user_id, token_hash, expires_at) "
        + "SELECT user_id, ?, NOW() + INTERVAL 1 DAY FROM users WHERE email = 'inactive@uxight.com'", RefreshToken.hash(raw));

    mvc.perform(post("/api/auth/refresh").cookie(new Cookie("refreshToken", raw)))
        .andExpect(status().isUnauthorized())
        .andExpect(jsonPath("$.code").value("AUT-ERR-005"))
        .andExpect(jsonPath("$.message").value("비활성화된 계정입니다."));
  }

  @Test
  void logout_revokesRefreshTokenAndDeletesCookie() throws Exception {
    insertUser("login@uxight.com", true);
    Cookie refreshTokenCookie = login("login@uxight.com", "password12").andReturn().getResponse().getCookie("refreshToken");

    mvc.perform(post("/api/auth/logout").cookie(refreshTokenCookie))
        .andExpect(status().isNoContent())
        .andExpect(header().string(HttpHeaders.SET_COOKIE, matchesPattern(
            "refreshToken=; Path=/api/auth; Max-Age=0; Expires=.+; Secure; HttpOnly; SameSite=Strict")));

    // 로그아웃한 refresh 토큰으로는 재발급할 수 없다
    mvc.perform(post("/api/auth/refresh").cookie(refreshTokenCookie))
        .andExpect(status().isUnauthorized())
        .andExpect(jsonPath("$.code").value("AUT-ERR-004"));
  }

  @Test
  void logout_withoutCookie_stillDeletesCookie() throws Exception {
    mvc.perform(post("/api/auth/logout"))
        .andExpect(status().isNoContent())
        .andExpect(header().string(HttpHeaders.SET_COOKIE, matchesPattern("refreshToken=; Path=/api/auth; Max-Age=0; .+")));
  }

  @Test
  void google_newAccount_signsUpResearcherWithoutPassword() throws Exception {
    givenGoogleAccount("google-sub-1", "new-google@gmail.com");

    google(GOOGLE_ID_TOKEN)
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.accessToken").value(notNullValue()))
        .andExpect(header().string(HttpHeaders.SET_COOKIE, matchesPattern(
            "refreshToken=[0-9a-f]{64}; Path=/api/auth; Max-Age=1209600; Expires=.+; Secure; HttpOnly; SameSite=Strict")));

    Map<String, Object> user = jdbcTemplate.queryForMap(
        "SELECT email, password_hash, auth_provider, name, role, is_active FROM users WHERE google_sub = 'google-sub-1'");
    assertThat(user).containsEntry("email", "new-google@gmail.com")
        .containsEntry("password_hash", null)
        .containsEntry("auth_provider", "google")
        .containsEntry("name", "구글 사용자")
        .containsEntry("role", "researcher")
        .containsEntry("is_active", true);
  }

  @Test
  void google_existingAccount_logsInWithoutSigningUpAgain() throws Exception {
    givenGoogleAccount("google-sub-1", "google@gmail.com");

    google(GOOGLE_ID_TOKEN).andExpect(status().isOk());
    google(GOOGLE_ID_TOKEN).andExpect(status().isOk());

    assertThat(jdbcTemplate.queryForObject(
        "SELECT COUNT(*) FROM users WHERE google_sub = 'google-sub-1'", Integer.class)).isEqualTo(1);
    assertThat(jdbcTemplate.queryForObject(
        "SELECT COUNT(*) FROM refresh_tokens t JOIN users u ON u.user_id = t.user_id WHERE u.google_sub = 'google-sub-1'",
        Integer.class)).isEqualTo(2);
  }

  @Test
  void google_invalidIdToken_returnsUnauthorized() throws Exception {
    when(googleIdTokenVerifier.verify(GOOGLE_ID_TOKEN)).thenReturn(Optional.empty());

    google(GOOGLE_ID_TOKEN)
        .andExpect(status().isUnauthorized())
        .andExpect(header().doesNotExist(HttpHeaders.SET_COOKIE))
        .andExpect(jsonPath("$.code").value("AUT-ERR-003"))
        .andExpect(jsonPath("$.message").value("Google 인증에 실패했습니다."))
        .andExpect(jsonPath("$.fieldErrors").value(empty()));
  }

  @Test
  void google_emailAlreadySignedUpByEmail_returnsConflict() throws Exception {
    insertUser("taken@gmail.com", true);
    givenGoogleAccount("google-sub-1", "taken@gmail.com");

    google(GOOGLE_ID_TOKEN)
        .andExpect(status().isConflict())
        .andExpect(jsonPath("$.code").value("AUT-ERR-008"))
        .andExpect(jsonPath("$.message").value("이메일로 가입된 계정입니다. 이메일로 로그인해 주세요."))
        .andExpect(jsonPath("$.fieldErrors").value(empty()));
    assertThat(jdbcTemplate.queryForObject(
        "SELECT google_sub FROM users WHERE email = 'taken@gmail.com'", String.class)).isNull();   // 연결하지 않는다
  }

  @Test
  void google_inactiveAccount_returnsUnauthorized() throws Exception {
    jdbcTemplate.update("INSERT INTO users (email, auth_provider, google_sub, name, role, is_active) "
        + "VALUES ('inactive-google@gmail.com', 'google', 'google-sub-1', '비활성', 'researcher', false)");
    givenGoogleAccount("google-sub-1", "inactive-google@gmail.com");

    google(GOOGLE_ID_TOKEN)
        .andExpect(status().isUnauthorized())
        .andExpect(jsonPath("$.code").value("AUT-ERR-005"));
  }

  @Test
  void google_blankIdToken_returnsFieldErrors() throws Exception {
    mvc.perform(post("/api/auth/google").contentType(MediaType.APPLICATION_JSON).content("{\"idToken\": \"\"}"))
        .andExpect(status().isBadRequest())
        .andExpect(jsonPath("$.code").value("GLB-ERR-002"))
        .andExpect(jsonPath("$.fieldErrors[0].field").value("idToken"));
  }

  private void givenGoogleAccount(String sub, String email) {
    when(googleIdTokenVerifier.verify(GOOGLE_ID_TOKEN)).thenReturn(Optional.of(new GoogleAccount(sub, email, "구글 사용자")));
  }

  private ResultActions google(String idToken) throws Exception {
    return mvc.perform(post("/api/auth/google").contentType(MediaType.APPLICATION_JSON)
        .content("{\"idToken\": \"%s\"}".formatted(idToken)));
  }

  private ResultActions signup(String body) throws Exception {
    return mvc.perform(post("/api/auth/signup").contentType(MediaType.APPLICATION_JSON).content(body));
  }

  private ResultActions login(String email, String password) throws Exception {
    return mvc.perform(post("/api/auth/login").contentType(MediaType.APPLICATION_JSON)
        .content("""
            {"email": "%s", "password": "%s"}
            """.formatted(email, password)));
  }

  // 비활성 계정은 가입 API 로 만들 수 없어 직접 넣는다. 비밀번호는 password12.
  private void insertUser(String email, boolean active) {
    jdbcTemplate.update("INSERT INTO users (email, password_hash, auth_provider, name, role, is_active) "
        + "VALUES (?, ?, 'local', '홍길동', 'researcher', ?)", email, passwordEncoder.encode("password12"), active);
  }
}
