package com.uxight.api.domain.user;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;
import org.springframework.security.crypto.password.PasswordEncoder;

import java.time.LocalDateTime;

@Entity
@Table(name = "users")
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class User {

  @Id
  @GeneratedValue(strategy = GenerationType.IDENTITY)
  @Column(name = "user_id")
  private Long id;

  private String email;

  private String passwordHash;   // local 가입만. Google 전용 계정이면 null

  @Enumerated(EnumType.STRING)
  private AuthProvider authProvider;

  private String googleSub;

  private String name;

  @Enumerated(EnumType.STRING)
  private Role role;

  @Column(name = "is_active")
  private boolean active;

  // 두 시각은 DB 기본값(CURRENT_TIMESTAMP · ON UPDATE)이 채운다. JPA 가 null 로 덮지 않게 쓰기에서 뺀다.
  @Column(insertable = false, updatable = false)
  private LocalDateTime createdAt;

  @Column(insertable = false, updatable = false)
  private LocalDateTime updatedAt;

  // 가입 계정은 모두 활성 리서처로 시작한다. 관리자 승격은 계정 역할 변경으로 한다.
  private User(String email, String passwordHash, AuthProvider authProvider, String googleSub, String name) {
    this.email = email;
    this.passwordHash = passwordHash;
    this.authProvider = authProvider;
    this.googleSub = googleSub;
    this.name = name;
    this.role = Role.researcher;
    this.active = true;
  }

  /** 이메일 가입. passwordHash 는 해시된 값이어야 한다. */
  public static User signUp(String email, String passwordHash, String name) {
    return new User(email, passwordHash, AuthProvider.local, null, name);
  }

  /** 처음 보는 Google 계정의 가입. 비밀번호 없이 Google 계정 고유 식별자(googleSub)로 로그인한다. */
  public static User signUpWithGoogle(String email, String googleSub, String name) {
    return new User(email, null, AuthProvider.google, googleSub, name);
  }

  /** 역할 변경. 권한 · 마지막 관리자 확인은 UserService 가 잠금 안에서 한다. 토큰에 역할이 없어 다음 요청부터 적용된다. */
  public void changeRole(Role role) {
    this.role = role;
  }

  /**
   * 활성 상태 변경. 대상 확인(리서처만)은 UserService 가 한다. 활성 여부는 매 요청 DB 에서 확인하므로 다음 요청부터 적용되고,
   * refresh 토큰 행은 그대로 둔다 — 비활성 동안은 재발급이 막히고, 다시 활성화하면 만료 전 토큰을 이어서 쓴다.
   */
  public void changeActive(boolean active) {
    this.active = active;
  }

  /** 이메일 로그인 비밀번호 확인. Google 로만 가입해 비밀번호가 없는 계정은 항상 false. */
  public boolean matchesPassword(String rawPassword, PasswordEncoder passwordEncoder) {
    return passwordHash != null && passwordEncoder.matches(rawPassword, passwordHash);
  }
}
