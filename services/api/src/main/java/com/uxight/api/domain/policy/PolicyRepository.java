package com.uxight.api.domain.policy;

import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;

/** 정책 관리자 API 전까지 전역 정책은 V4 마이그레이션이 넣은 한 행(policy_id 1)뿐이다. */
public interface PolicyRepository extends JpaRepository<Policy, Long> {

  /** 전역 정책. 행이 없으면 마이그레이션이 빠진 것이라 실험을 만들 수 없다(500). */
  default Policy getGlobal() {
    return findFirstByOrderByIdAsc()
        .orElseThrow(() -> new IllegalStateException("global policy row is missing (V4__policies)"));
  }

  Optional<Policy> findFirstByOrderByIdAsc();
}
