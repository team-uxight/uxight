package com.uxight.api.domain.user;

import jakarta.persistence.LockModeType;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Lock;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

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
}
