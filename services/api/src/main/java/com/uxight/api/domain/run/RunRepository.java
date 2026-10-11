package com.uxight.api.domain.run;

import java.util.List;
import java.util.Optional;

public interface RunRepository {

  Long save(Run run);

  void updateFirstRunId(Long runId, Long firstRunId);

  void updateDispatchState(Long runId, String dispatchState);

  /** 본인 실험의 마지막 회차. 남의 실험은 없는 것과 같다. */
  Optional<Run> findLastRound(Long firstRunId, Long userId);

  /**
   * 프로젝트에 진행 중(queued · accepted · running)인 회차가 있는가. 취소 요청된 회차도 실제로 멈추기 전까지는 진행 중이다.
   * 프로젝트 하나의 진행 중인 실험은 최대 1개 — 회차 하나라도 진행 중이면 그 실험이 진행 중이다 (design-decision 5.2).
   */
  boolean existsInProgressByProjectId(Long projectId);

  /** 진행 중(queued · accepted · running)인 회차에만 기록한다. 기록했으면 true. */
  boolean requestCancel(Long runId);

  /** state 가 null 이면 전체. 최근 요청 순. */
  List<ExperimentSummary> findExperiments(Long userId, String state, int offset, int limit);

  long countExperiments(Long userId, String state);
}
