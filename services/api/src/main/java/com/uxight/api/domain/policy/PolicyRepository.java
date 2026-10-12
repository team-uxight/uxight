package com.uxight.api.domain.policy;

import org.springframework.data.jpa.repository.JpaRepository;

/** 정책 관리자 API 전까지 전역 정책은 V4 마이그레이션이 넣은 한 행(policy_id 1)뿐이다. */
public interface PolicyRepository extends JpaRepository<Policy, Long> {
}
