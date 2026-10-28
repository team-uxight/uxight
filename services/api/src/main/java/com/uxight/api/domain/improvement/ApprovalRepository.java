package com.uxight.api.domain.improvement;

import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

/** approvals — Spring 이 쓴다. 개선안당 결정은 하나(uk_approvals_improvement_id). */
public interface ApprovalRepository extends JpaRepository<Approval, Long> {

  /** 회차의 개선안들에 대한 결정. */
  List<Approval> findByImprovementRunId(Long runId);

  Optional<Approval> findByImprovementId(Long improvementId);

  boolean existsByImprovementId(Long improvementId);

  /** 이 회차에서 승인된 개선안이 있는지 — 한 회차에서 승인할 수 있는 개선안은 하나다. */
  boolean existsByImprovementRunIdAndDecision(Long runId, Decision decision);
}
