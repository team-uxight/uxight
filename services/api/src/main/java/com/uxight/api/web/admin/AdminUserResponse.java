package com.uxight.api.web.admin;

import com.uxight.api.domain.user.AuthProvider;
import com.uxight.api.domain.user.Role;
import com.uxight.api.domain.user.User;

import java.time.LocalDateTime;

/** 관리자 계정 목록의 한 행. 비밀번호 해시와 Google 계정 고유 식별자(googleSub)는 싣지 않는다. */
public record AdminUserResponse(Long userId, String email, String name, Role role, AuthProvider authProvider,
    boolean isActive, LocalDateTime createdAt) {

  public static AdminUserResponse from(User user) {
    return new AdminUserResponse(user.getId(), user.getEmail(), user.getName(), user.getRole(), user.getAuthProvider(),
        user.isActive(), user.getCreatedAt());
  }
}
