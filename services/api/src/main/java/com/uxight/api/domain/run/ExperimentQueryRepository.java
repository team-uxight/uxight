package com.uxight.api.domain.run;

import java.time.OffsetDateTime;
import java.util.List;

/**
 * 실험 목록 · 건수 — 읽기 전용 집계 조회. 서브쿼리 · CASE · JSON_LENGTH 가 많아 JPQL 대신 SQL 로 둔다 (JdbcTemplate).
 * 실험 상태(state) · 종료 유형 계산은 구현의 SQL 한 곳에만 두고 목록 · 건수가 함께 쓴다 (design-decision 2.6).
 * 회차의 저장 · 변경은 RunRepository(JPA).
 */
public interface ExperimentQueryRepository {

  /** 최근 요청 순. */
  List<ExperimentSummary> findExperiments(Long userId, ExperimentFilter filter, int offset, int limit);

  long countExperiments(Long userId, ExperimentFilter filter);

  /** 상태별 건수와 총 소요 토큰. 이번 주 완료 건수는 thisWeekFrom 을 기준으로 센다. */
  ExperimentStats findStats(Long userId, OffsetDateTime thisWeekFrom);
}
