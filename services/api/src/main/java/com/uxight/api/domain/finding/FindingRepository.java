package com.uxight.api.domain.finding;

import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

/** findings 읽기. 행은 AI 모듈이 쓴다. */
public interface FindingRepository extends JpaRepository<Finding, Long> {

  /** 회차의 진단 — 검출 순. */
  List<Finding> findByRunIdOrderByIdAsc(Long runId);

  /** 본인 프로젝트의 진단 하나. 남의 진단과 삭제한 프로젝트의 진단은 없는 것과 같다. 회차가 done 인지는 서비스가 본다. */
  Optional<Finding> findByIdAndRunProjectUserIdAndRunProjectDeletedAtIsNull(Long findingId, Long userId);
}
