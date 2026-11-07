package com.uxight.api.domain.user;

import java.util.List;

/** 관리자 계정 목록 — 읽기 전용 집계 조회(JdbcTemplate). 비활성 계정을 포함한 모든 계정. */
public interface AdminUserQueryRepository {

  /** 최근 가입 순. */
  List<AdminUserSummary> findUsers(long offset, int limit);

  long countUsers();
}
