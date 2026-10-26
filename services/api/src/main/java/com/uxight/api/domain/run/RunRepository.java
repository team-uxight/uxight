package com.uxight.api.domain.run;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.transaction.annotation.Transactional;

import java.util.Collection;
import java.util.List;
import java.util.Optional;

/**
 * 회차의 저장 · 변경. save 는 JpaRepository 가 제공한다. 실험 목록 · 건수 같은 집계 조회는 ExperimentQueryRepository(JdbcTemplate).
 * 메서드 이름의 FirstRunId 는 firstRun.id, ProjectId 는 project.id, ProjectUserId 는 project.user.id 로 풀린다.
 */
public interface RunRepository extends JpaRepository<Run, Long> {

  /**
   * 본인 실험의 마지막 회차. 남의 실험과 삭제한 프로젝트의 실험은 없는 것과 같다(실험 목록에서도 보이지 않는다).
   * 다음 회차는 이전 회차가 끝난 뒤 생기므로 run_id 가 가장 큰 회차다.
   */
  default Optional<Run> findLastRound(Long firstRunId, Long userId) {
    return findTopByFirstRunIdAndProjectUserIdAndProjectDeletedAtIsNullOrderByIdDesc(firstRunId, userId);
  }

  Optional<Run> findTopByFirstRunIdAndProjectUserIdAndProjectDeletedAtIsNullOrderByIdDesc(Long firstRunId, Long userId);

  /** 본인 회차 하나. 남의 회차와 삭제한 프로젝트의 회차는 없는 것과 같다. */
  Optional<Run> findByIdAndProjectUserIdAndProjectDeletedAtIsNull(Long runId, Long userId);

  /**
   * 프로젝트에 진행 중(queued · accepted · running)인 회차가 있는가. 취소 요청된 회차도 실제로 멈추기 전까지는 진행 중이다.
   * 프로젝트 하나의 진행 중인 실험은 최대 1개 — 회차 하나라도 진행 중이면 그 실험이 진행 중이다 (design-decision 5.2).
   */
  default boolean existsInProgressByProjectId(Long projectId) {
    return existsByProjectIdAndStatusIn(projectId, RunStatus.IN_PROGRESS);
  }

  boolean existsByProjectIdAndStatusIn(Long projectId, Collection<RunStatus> statuses);

  /**
   * queued 로 seconds 초 넘게 남은 회차의 run_id. 재전송 대상이다 (design-decision 4.6). 취소 요청된 회차도 포함한다.
   * 시각 비교는 DB 시계(NOW())로만 한다 — created_at 은 DB 기본값이라 JVM 시계와 섞으면 시간대에 따라 어긋난다.
   */
  @Query(value = "SELECT run_id FROM runs WHERE status = 'queued' AND created_at < NOW() - INTERVAL :seconds SECOND "
      + "ORDER BY run_id", nativeQuery = true)
  List<Long> findQueuedRunIdsOlderThan(@Param("seconds") long seconds);

  /**
   * POST /runs 결과만 한 줄 UPDATE 로 기록한다 — 행을 읽어 고쳐 쓰지 않으므로 Python 이 그사이 바꾼 컬럼을 건드리지 않는다.
   * 커밋 뒤 비동기 스레드에서 부르므로 자체 트랜잭션으로 돈다.
   */
  @Transactional
  @Modifying(flushAutomatically = true, clearAutomatically = true)   // 영속성 컨텍스트에 옛 값이 남지 않게
  @Query("UPDATE Run r SET r.dispatchState = :state WHERE r.id = :runId")
  int updateDispatchState(@Param("runId") Long runId, @Param("state") DispatchState state);

  /**
   * 전체 중단 대상 — 모든 프로젝트에서 진행 중(queued · accepted · running)이고 아직 취소 요청이 없는 회차의 run_id.
   * 행을 잠근다(FOR UPDATE): 이어서 기록할 때까지 Python 이 status 를 바꾸지 못해, 기록한 회차와 감사 로그의 목록이 같다.
   * 승인 대기 중인 실험(마지막 회차 done)은 실행 자원을 쓰지 않으므로 status 조건에서 빠진다. 트랜잭션 안에서만 쓴다.
   */
  @Query(value = "SELECT run_id FROM runs WHERE status IN ('queued', 'accepted', 'running') AND cancel_requested = FALSE "
      + "ORDER BY run_id FOR UPDATE", nativeQuery = true)
  List<Long> lockInProgressRunIdsWithoutCancelRequest();

  @Transactional
  @Modifying(flushAutomatically = true, clearAutomatically = true)   // 영속성 컨텍스트에 옛 값이 남지 않게
  @Query("UPDATE Run r SET r.cancelRequested = true WHERE r.id IN :runIds")
  int markCancelRequested(@Param("runIds") Collection<Long> runIds);

  /**
   * 회차에 취소 요청을 기록한다 — cancel_requested 한 컬럼만 한 줄 UPDATE 로 바꿔 Python 이 그사이 쓴 컬럼을 건드리지 않는다.
   * 취소할 수 있는지(진행 중 · 승인 대기)는 RunService 가 프로젝트 행을 잠근 뒤 판정한다. 기록했으면 true.
   */
  default boolean requestCancel(Long runId) {
    return markCancelRequested(runId) == 1;
  }

  @Transactional
  @Modifying(flushAutomatically = true, clearAutomatically = true)   // 영속성 컨텍스트에 옛 값이 남지 않게
  @Query("UPDATE Run r SET r.cancelRequested = true WHERE r.id = :runId")
  int markCancelRequested(@Param("runId") Long runId);
}
