package com.uxight.api.domain.user;

import com.uxight.api.common.ApiException;
import com.uxight.api.common.ErrorCode;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.transaction.annotation.Transactional;

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
  private PasswordEncoder passwordEncoder;

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
}
