package com.uxight.api.domain.user;

import org.junit.jupiter.api.Test;

import java.time.Duration;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class JwtProviderTest {

  private static final String SECRET = "test-secret-key-must-be-at-least-32-bytes";

  private final JwtProvider jwtProvider = newProvider(SECRET, Duration.ofHours(1));

  @Test
  void createdToken_parsesToSameUserId() {
    String token = jwtProvider.createAccessToken(42L);

    assertThat(jwtProvider.parseUserId(token)).contains(42L);
  }

  @Test
  void expiredToken_isRejected() {
    String token = newProvider(SECRET, Duration.ofSeconds(-1)).createAccessToken(42L);

    assertThat(jwtProvider.parseUserId(token)).isEmpty();
  }

  @Test
  void tokenSignedWithAnotherKey_isRejected() {
    String token = newProvider("another-secret-key-also-at-least-32-bytes", Duration.ofHours(1)).createAccessToken(42L);

    assertThat(jwtProvider.parseUserId(token)).isEmpty();
  }

  @Test
  void tamperedToken_isRejected() {
    String token = jwtProvider.createAccessToken(42L);
    String tampered = token.substring(0, token.length() - 2) + (token.endsWith("AA") ? "BB" : "AA");

    assertThat(jwtProvider.parseUserId(tampered)).isEmpty();
  }

  @Test
  void unsignedToken_isRejected() {
    // alg=none, sub=42 — 서명 없는 토큰
    String unsigned = "eyJhbGciOiJub25lIn0.eyJzdWIiOiI0MiJ9.";

    assertThat(jwtProvider.parseUserId(unsigned)).isEmpty();
    assertThat(jwtProvider.parseUserId("not-a-jwt")).isEmpty();
  }

  @Test
  void shortSecret_failsAtStartup() {
    assertThatThrownBy(() -> new JwtProvider("too-short", Duration.ofHours(1)))
        .isInstanceOf(IllegalStateException.class);
  }

  private static JwtProvider newProvider(String secret, Duration ttl) {
    try {
      return new JwtProvider(secret, ttl);
    } catch (Exception e) {
      throw new IllegalStateException(e);
    }
  }
}
