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

  private User(String email, String passwordHash, AuthProvider authProvider, String name, Role role) {
    this.email = email;
    this.passwordHash = passwordHash;
    this.authProvider = authProvider;
    this.name = name;
    this.role = role;
    this.active = true;
  }

  /** 이메일 가입. 가입 계정은 리서처로 시작한다. passwordHash 는 해시된 값이어야 한다. */
  public static User signUp(String email, String passwordHash, String name) {
    return new User(email, passwordHash, AuthProvider.local, name, Role.researcher);
  }
}
