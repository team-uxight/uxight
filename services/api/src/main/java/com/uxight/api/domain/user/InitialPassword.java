package com.uxight.api.domain.user;

import java.security.SecureRandom;

/**
 * 관리자가 만든 계정의 초기 비밀번호. 영어 소문자 · 숫자 12자로, 소문자와 숫자를 하나씩 이상 넣는다 —
 * 이메일 가입 비밀번호 규칙(SignupRequest: 소문자 · 숫자 포함 8~12자)과 같아 그대로 로그인할 수 있다.
 */
public final class InitialPassword {

  static final int LENGTH = 12;

  private static final String LOWERCASE = "abcdefghijklmnopqrstuvwxyz";
  private static final String DIGITS = "0123456789";
  private static final String CHARS = LOWERCASE + DIGITS;
  private static final SecureRandom RANDOM = new SecureRandom();

  private InitialPassword() {
  }

  public static String generate() {
    while (true) {
      StringBuilder password = new StringBuilder(LENGTH);
      for (int i = 0; i < LENGTH; i++) {
        password.append(CHARS.charAt(RANDOM.nextInt(CHARS.length())));
      }
      // 소문자만 · 숫자만 나온 경우(확률 1% 미만)는 다시 뽑는다 — 자리를 정해 넣으면 위치가 드러난다
      if (password.chars().anyMatch(c -> LOWERCASE.indexOf(c) >= 0) && password.chars().anyMatch(Character::isDigit)) {
        return password.toString();
      }
    }
  }
}
