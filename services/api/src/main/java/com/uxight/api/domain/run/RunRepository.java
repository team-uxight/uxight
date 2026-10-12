package com.uxight.api.domain.run;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.transaction.annotation.Transactional;

import java.util.Collection;
import java.util.Optional;

/**
 * 회차의 저장 · 변경. save 는 JpaRepository 가 제공한다. 실험 목록 · 건수 같은 집계 조회는 ExperimentQueryRepository(JdbcTemplate).
 * 메서드 이름의 FirstRunId 는 firstRun.id, ProjectId 는 project.id, ProjectUserId 는 project.user.id 로 풀린다.
 */
public interface RunRepository extends JpaRepository<Run, Long> {

  /** 본인 실험의 마지막 회차. 남의 실험은 없는 것과 같다. 다음 회차는 이전 회차가 끝난 뒤 생기므로 run_id 가 가장 큰 회차다. */
  default Optional<Run> findLastRound(Long firstRunId, Long userId) {
    return findTopByFirstRunIdAndProjectUserIdOrderByIdDesc(firstRunId, userId);
  }

  Optional<Run> findTopByFirstRunIdAndProjectUserIdOrderByIdDesc(Long firstRunId, Long userId);

  /**
   * 프로젝트에 진행 중(queued · accepted · running)인 회차가 있는가. 취소 요청된 회차도 실제로 멈추기 전까지는 진행 중이다.
   * 프로젝트 하나의 진행 중인 실험은 최대 1개 — 회차 하나라도 진행 중이면 그 실험이 진행 중이다 (design-decision 5.2).
   */
  default boolean existsInProgressByProjectId(Long projectId) {
    return existsByProjectIdAndStatusIn(projectId, RunStatus.IN_PROGRESS);
  }

  boolean existsByProjectIdAndStatusIn(Long projectId, Collection<RunStatus> statuses);

  /**
   * POST /runs 결과만 한 줄 UPDATE 로 기록한다 — 행을 읽어 고쳐 쓰지 않으므로 Python 이 그사이 바꾼 컬럼을 건드리지 않는다.
   * 커밋 뒤 비동기 스레드에서 부르므로 자체 트랜잭션으로 돈다.
   */
  @Transactional
  @Modifying(flushAutomatically = true, clearAutomatically = true)   // 영속성 컨텍스트에 옛 값이 남지 않게
  @Query("UPDATE Run r SET r.dispatchState = :state WHERE r.id = :runId")
  int updateDispatchState(@Param("runId") Long runId, @Param("state") DispatchState state);

  /** 진행 중인 회차에만 취소 요청을 기록한다. 읽은 뒤 회차가 끝났을 수 있어 UPDATE 의 status 조건이 최종 판정이다. 기록했으면 true. */
  default boolean requestCancel(Long runId) {
    return markCancelRequested(runId, RunStatus.IN_PROGRESS) == 1;
  }

  @Transactional
  @Modifying(flushAutomatically = true, clearAutomatically = true)   // 영속성 컨텍스트에 옛 값이 남지 않게
  @Query("UPDATE Run r SET r.cancelRequested = true WHERE r.id = :runId AND r.status IN :statuses")
  int markCancelRequested(@Param("runId") Long runId, @Param("statuses") Collection<RunStatus> statuses);
}
