package com.uxight.api.domain.usage;

import java.time.LocalDate;
import java.util.List;

/** 사용량 — 읽기 전용 집계 조회(JdbcTemplate). 새 테이블 없이 runs 의 tokens · cost_usd 를 날짜별로 더한다. */
public interface UsageQueryRepository {

  /** [from, to] 기간(KST 날짜)에 요청된 회차의 일별 합. 회차가 없는 날은 빠진다. 모든 사용자 · 삭제된 프로젝트 포함. */
  List<UsageDay> findDaily(LocalDate from, LocalDate to);
}
