package com.uxight.api.domain.run;

import java.util.List;

/** 관리자 전체 실험 목록 — 읽기 전용 집계 조회(JdbcTemplate). 모든 사용자 · 삭제된 프로젝트의 실험을 포함한다. */
public interface AdminExperimentQueryRepository {

  /** 최근 요청 순. */
  List<AdminExperimentSummary> findExperiments(int offset, int limit);

  long countExperiments();
}
