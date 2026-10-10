package com.uxight.api.domain.user;

import com.uxight.api.common.ApiException;
import com.uxight.api.common.ErrorCode;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/** 실제 MySQL 에 붙는다. 테스트마다 롤백한다. */
@SpringBootTest
@Transactional
class AuthServiceTest {

  @Autowired
  private AuthService authService;

  @Autowired
  private UserRepository userRepository;

  @Autowired
  private RefreshTokenRepository refreshTokenRepository;

  @Autowired
  private PasswordEncoder passwordEncoder;

  @Autowired
  private JwtProvider jwtProvider;

  @Autowired
  private JdbcTemplate jdbcTemplate;

  @Test
  void signup_savesResearcherWithHashedPassword() {
    Long userId = authService.signup("signup@uxight.com", "password12", "홍길동");

    User saved = userRepository.findById(userId).orElseThrow();
    assertThat(saved.getEmail()).isEqualTo("signup@uxight.com");
    assertThat(saved.getName()).isEqualTo("홍길동");
    assertThat(saved.getRole()).isEqualTo(Role.researcher);
    assertThat(saved.getPasswordHash()).isNotEqualTo("password12");
    assertThat(passwordEncoder.matches("password12", saved.getPasswordHash())).isTrue();
  }

  @Test
  void signup_rejectsDuplicateEmail() {
    assertThatThrownBy(() -> authService.signup("test@uxight.com", "password12", "중복"))
        .isInstanceOf(ApiException.class)
        .extracting(e -> ((ApiException) e).errorCode())
        .isEqualTo(ErrorCode.EMAIL_DUPLICATED);
  }

  @Test
  void login_issuesAccessTokenAndStoresOnlyRefreshTokenHash() {
    Long userId = authService.signup("login@uxight.com", "password12", "홍길동");

    LoginTokens tokens = authService.login("login@uxight.com", "password12");

    assertThat(jwtProvider.parseUserId(tokens.accessToken())).contains(userId);
    assertThat(tokens.refreshToken()).hasSize(64);
    RefreshToken stored = refreshTokenRepository.findByTokenHash(RefreshToken.hash(tokens.refreshToken())).orElseThrow();
    assertThat(stored.getTokenHash()).isNotEqualTo(tokens.refreshToken());
    assertThat(stored.getUser().getId()).isEqualTo(userId);
    assertThat(stored.getRevokedAt()).isNull();
    assertThat(stored.getExpiresAt()).isAfter(LocalDateTime.now().plusDays(13));
  }

  @Test
  void login_rejectsUnknownEmail() {
    assertLoginFails("no-such-user@uxight.com", "password12", ErrorCode.LOGIN_FAILED);
  }

  @Test
  void login_rejectsWrongPassword() {
    authService.signup("login@uxight.com", "password12", "홍길동");

    assertLoginFails("login@uxight.com", "password99", ErrorCode.LOGIN_FAILED);
  }

  @Test
  void login_rejectsGoogleOnlyAccountWithoutPassword() {
    jdbcTemplate.update("INSERT INTO users (email, password_hash, auth_provider, google_sub, name, role, is_active) "
        + "VALUES ('google@uxight.com', NULL, 'google', 'google-sub-1', '구글', 'researcher', true)");

    assertLoginFails("google@uxight.com", "password12", ErrorCode.LOGIN_FAILED);
  }

  @Test
  void login_rejectsInactiveAccount_onlyAfterPasswordMatches() {
    jdbcTemplate.update("INSERT INTO users (email, password_hash, auth_provider, name, role, is_active) "
        + "VALUES ('inactive@uxight.com', ?, 'local', '비활성', 'researcher', false)", passwordEncoder.encode("password12"));

    assertLoginFails("inactive@uxight.com", "password99", ErrorCode.LOGIN_FAILED);   // 비밀번호가 틀리면 계정 상태를 숨긴다
    assertLoginFails("inactive@uxight.com", "password12", ErrorCode.ACCOUNT_DISABLED);
  }

  private void assertLoginFails(String email, String password, ErrorCode expected) {
    assertThatThrownBy(() -> authService.login(email, password))
        .isInstanceOf(ApiException.class)
        .extracting(e -> ((ApiException) e).errorCode())
        .isEqualTo(expected);
  }
}
