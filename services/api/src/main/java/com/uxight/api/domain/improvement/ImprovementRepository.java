package com.uxight.api.domain.improvement;

import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

/** improvements 읽기. 행은 AI 모듈이 쓴다. */
public interface ImprovementRepository extends JpaRepository<Improvement, Long> {

  /** 회차의 개선안 — 안 번호 순. */
  List<Improvement> findByRunIdOrderByOptionNoAsc(Long runId);

  long countByRunId(Long runId);

  /** 본인 프로젝트의 개선안 하나. 남의 개선안과 삭제한 프로젝트의 개선안은 없는 것과 같다. 회차가 done 인지는 서비스가 본다. */
  Optional<Improvement> findByIdAndRunProjectUserIdAndRunProjectDeletedAtIsNull(Long improvementId, Long userId);
}
