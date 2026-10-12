package com.uxight.api.domain.run;

import java.util.List;

/**
 * 실험 목록 · 건수 — 읽기 전용 집계 조회. 서브쿼리 · CASE · JSON_LENGTH 가 많아 JPQL 대신 SQL 로 둔다 (JdbcTemplate).
 * 회차의 저장 · 변경은 RunRepository(JPA).
 */
public interface ExperimentQueryRepository {

  /** state 가 null 이면 전체. 최근 요청 순. */
  List<ExperimentSummary> findExperiments(Long userId, String state, int offset, int limit);

  long countExperiments(Long userId, String state);
}
