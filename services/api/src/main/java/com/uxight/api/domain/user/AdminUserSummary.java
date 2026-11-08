package com.uxight.api.domain.user;

import java.math.BigDecimal;
import java.time.LocalDateTime;

/**
 * 관리자 계정 목록의 한 행. 비밀번호 해시와 Google 계정 고유 식별자(googleSub)는 싣지 않는다.
 *
 * @param lastLoginAt  마지막 이메일 · Google 로그인 시각. 로그인한 적 없으면 null
 * @param totalCostUsd 그 계정 프로젝트(삭제된 것 포함)의 모든 회차 비용(runs.cost_usd) 합. 회차가 없으면 0
 */
public record AdminUserSummary(Long userId, String email, String name, Role role, AuthProvider authProvider,
    boolean isActive, LocalDateTime createdAt, LocalDateTime lastLoginAt, BigDecimal totalCostUsd) {
}
