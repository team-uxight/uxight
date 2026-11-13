package com.uxight.api.web.admin;

import com.uxight.api.domain.user.AdminUserSummary;
import com.uxight.api.domain.user.AuthProvider;
import com.uxight.api.domain.user.Role;

import java.math.BigDecimal;
import java.time.LocalDateTime;

/** 관리자 계정 목록의 한 행. 비밀번호 해시와 Google 계정 고유 식별자(googleSub)는 싣지 않는다. */
public record AdminUserResponse(Long userId, String email, String name, Role role, AuthProvider authProvider,
    boolean isActive, LocalDateTime createdAt, LocalDateTime lastLoginAt, BigDecimal totalCostUsd) {

  public static AdminUserResponse from(AdminUserSummary user) {
    return new AdminUserResponse(user.userId(), user.email(), user.name(), user.role(), user.authProvider(),
        user.isActive(), user.createdAt(), user.lastLoginAt(), user.totalCostUsd());
  }
}
