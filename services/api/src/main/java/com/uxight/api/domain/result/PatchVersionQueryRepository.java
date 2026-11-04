package com.uxight.api.domain.result;

import java.util.List;

/** patch_versions 읽기 전용 조회(JdbcTemplate). 테이블은 Python 이 쓰고 Spring 은 읽기만 한다. */
public interface PatchVersionQueryRepository {

  /** 실험 회차들에 주입된 패치 — 회차 순 · 기록 순. round 는 실험 안의 회차 순번이다. 소유 확인은 호출하는 쪽이 한다. */
  List<Comparison.AppliedPatch> findByFirstRunId(long firstRunId);
}
