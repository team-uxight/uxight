package com.uxight.api.domain.user;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.RepeatedTest;
import org.junit.jupiter.api.Test;

import java.util.HashSet;
import java.util.Set;

/** 초기 비밀번호 — Spring 없이. 이메일 가입 비밀번호 규칙(SignupRequest 정규식)을 그대로 통과해야 로그인할 수 있다. */
class InitialPasswordTest {

  private static final String SIGNUP_PASSWORD_RULE = "^(?=.*[a-z])(?=.*\\d).{8,12}$";

  @RepeatedTest(200)
  void isTwelveLowercaseOrDigitChars_withAtLeastOneOfEach_andPassesSignupRule() {
    String password = InitialPassword.generate();

    assertThat(password).hasSize(12).matches("[a-z0-9]+").matches(SIGNUP_PASSWORD_RULE);
  }

  @Test
  void differsEachTime() {
    Set<String> passwords = new HashSet<>();
    for (int i = 0; i < 100; i++) {
      passwords.add(InitialPassword.generate());
    }
    assertThat(passwords).hasSize(100);
  }
}
