package com.uxight.api.domain.finding;

import com.uxight.api.domain.run.RunStatus;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.Collection;
import java.util.List;
import java.util.Optional;

/** findings 읽기. 행은 AI 모듈이 쓴다. */
public interface FindingRepository extends JpaRepository<Finding, Long> {

  /** 회차의 진단 — 검출 순. */
  List<Finding> findByRunIdOrderByIdAsc(Long runId);

  /** 회차의 진단 중 findingIds 에 든 것 — 검출 순. 개선안의 finding_ids 는 JSON 이라 외래 키가 없어 같은 회차로 한정한다. */
  List<Finding> findByRunIdAndIdInOrderByIdAsc(Long runId, Collection<Long> findingIds);

  /** 본인 프로젝트의 진단 하나. 남의 진단과 삭제한 프로젝트의 진단은 없는 것과 같다. 회차가 done 인지는 서비스가 본다. */
  Optional<Finding> findByIdAndRunProjectUserIdAndRunProjectDeletedAtIsNull(Long findingId, Long userId);

  /**
   * 본인 실험(삭제한 프로젝트 제외)의 최초 회차가 status 회차인 진단을 Taxonomy 별로 센다 — [taxonomy, count] 행.
   * 진단이 없는 Taxonomy 는 행이 없다.
   */
  @Query("SELECT f.taxonomy, COUNT(f) FROM Finding f "
      + "WHERE f.run.project.user.id = :userId AND f.run.project.deletedAt IS NULL "
      + "AND f.run.id = f.run.firstRun.id AND f.run.status = :status "
      + "GROUP BY f.taxonomy")
  List<Object[]> countFirstRoundFindingsByTaxonomy(@Param("userId") Long userId, @Param("status") RunStatus status);
}
