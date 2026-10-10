package com.uxight.api.domain.user;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.security.SecureRandom;
import java.time.Duration;
import java.time.LocalDateTime;
import java.util.HexFormat;

/** 발급된 refresh 토큰. 원문은 쿠키로만 나가고 DB 에는 SHA-256 해시만 남는다. */
@Entity
@Table(name = "refresh_tokens")
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class RefreshToken {

  private static final SecureRandom RANDOM = new SecureRandom();
  private static final int TOKEN_BYTES = 32;

  @Id
  @GeneratedValue(strategy = GenerationType.IDENTITY)
  @Column(name = "refresh_token_id")
  private Long id;

  @ManyToOne(fetch = FetchType.LAZY)
  @JoinColumn(name = "user_id")
  private User user;

  private String tokenHash;

  private LocalDateTime expiresAt;

  private LocalDateTime revokedAt;   // null 이면 유효

  @Column(insertable = false, updatable = false)
  private LocalDateTime createdAt;

  private RefreshToken(User user, String tokenHash, LocalDateTime expiresAt) {
    this.user = user;
    this.tokenHash = tokenHash;
    this.expiresAt = expiresAt;
  }

  /** rawToken 의 해시와 만료 시각을 담은 행을 만든다. rawToken 은 newRawToken() 으로 만든 값이다. */
  public static RefreshToken issue(User user, String rawToken, Duration ttl) {
    return new RefreshToken(user, hash(rawToken), LocalDateTime.now().plus(ttl));
  }

  /** 무효화(로그아웃)되지 않았고 만료 전이면 access 토큰 재발급에 쓸 수 있다. */
  public boolean isUsable() {
    return revokedAt == null && expiresAt.isAfter(LocalDateTime.now());
  }

  /** 로그아웃. 무효화 시각을 기록한다. 이미 무효화된 토큰이면 처음 시각을 유지한다. */
  public void revoke() {
    if (revokedAt == null) {
      revokedAt = LocalDateTime.now();
    }
  }

  /** 쿠키에 담을 원문. JWT 가 아닌 무작위 문자열(32바이트, hex 64자)이다. */
  public static String newRawToken() {
    byte[] bytes = new byte[TOKEN_BYTES];
    RANDOM.nextBytes(bytes);
    return HexFormat.of().formatHex(bytes);
  }

  /** 원문 → SHA-256 hex(64자). 재발급 · 로그아웃에서 쿠키 값으로 행을 찾을 때도 쓴다. */
  public static String hash(String rawToken) {
    try {
      byte[] digest = MessageDigest.getInstance("SHA-256").digest(rawToken.getBytes(StandardCharsets.UTF_8));
      return HexFormat.of().formatHex(digest);
    } catch (NoSuchAlgorithmException e) {
      throw new IllegalStateException(e);   // SHA-256 은 모든 JVM 이 지원한다
    }
  }
}
