package com.uxight.api.domain.runlog;

import java.util.List;

/** run_personas 읽기 전용 조회(JdbcTemplate). 테이블은 Python 이 쓰고 Spring 은 읽기만 한다. */
public interface RunPersonaQueryRepository {

  /** 회차의 Persona 실행들. AI 모듈이 회차를 접수하기 전이면 빈 목록. */
  List<RunPersonaStatus> findByRunId(long runId);
}
