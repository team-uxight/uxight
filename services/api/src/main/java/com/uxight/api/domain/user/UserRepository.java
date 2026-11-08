package com.uxight.api.domain.user;

import jakarta.persistence.LockModeType;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Lock;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;

/** save · findById 는 JpaRepository 가 제공한다. */
public interface UserRepository extends JpaRepository<User, Long> {

  Optional<User> findByEmail(String email);

  Optional<User> findByGoogleSub(String googleSub);

  /**
   * 역할 변경용 잠금 — 그 역할의 계정 행 전부를 user_id 순으로 잠근다. 관리자 수 확인과 변경이 끝날 때까지
   * 다른 역할 변경이 기다리므로, 두 관리자를 동시에 내려도 관리자가 0명이 되지 않는다.
   */
  @Lock(LockModeType.PESSIMISTIC_WRITE)
  @Query("SELECT u FROM User u WHERE u.role = :role ORDER BY u.id")
  List<User> findByRoleForUpdate(@Param("role") Role role);

  @Lock(LockModeType.PESSIMISTIC_WRITE)
  @Query("SELECT u FROM User u WHERE u.id = :userId")
  Optional<User> findForUpdate(@Param("userId") Long userId);

  /**
   * 마지막 로그인 시각만 바꾼다. Google 로그인은 트랜잭션 밖에서 불러 엔티티 변경이 저장되지 않고, 엔티티를 통째로 저장하면
   * 그사이 운영자가 바꾼 활성 상태 · 역할을 옛 값으로 덮는다. 트랜잭션 안(이메일 로그인)에서는 그 트랜잭션에 들어간다.
   */
  @Transactional
  @Modifying
  @Query("UPDATE User u SET u.lastLoginAt = :at WHERE u.id = :userId")
  int updateLastLoginAt(@Param("userId") Long userId, @Param("at") LocalDateTime at);
}
