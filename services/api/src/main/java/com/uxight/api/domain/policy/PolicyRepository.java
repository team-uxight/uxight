package com.uxight.api.domain.policy;

import jakarta.persistence.LockModeType;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Lock;
import org.springframework.data.jpa.repository.Query;

import java.util.Optional;

/** 정책 관리자 API 전까지 전역 정책은 V4 마이그레이션이 넣은 한 행(policy_id 1)뿐이다. */
public interface PolicyRepository extends JpaRepository<Policy, Long> {

  /** 전역 정책. 행이 없으면 마이그레이션이 빠진 것이라 실험을 만들 수 없다(500). */
  default Policy getGlobal() {
    return findFirstByOrderByIdAsc()
        .orElseThrow(() -> new IllegalStateException("global policy row is missing (V4__policies)"));
  }

  Optional<Policy> findFirstByOrderByIdAsc();

  /**
   * getGlobal 과 같지만 행을 잠근다(SELECT ... FOR UPDATE). 트랜잭션 안에서만 쓴다.
   * 관리자 둘이 동시에 고쳐도 차례로 처리돼, 서로의 수정을 덮지 않고 감사 로그의 수정 전 값도 정확하다.
   * 잠금은 쓰기끼리만 막는다 — AI 모듈 · 실험 요청의 일반 조회는 기다리지 않는다.
   */
  default Policy getGlobalForUpdate() {
    return findGlobalForUpdate()
        .orElseThrow(() -> new IllegalStateException("global policy row is missing (V4__policies)"));
  }

  @Lock(LockModeType.PESSIMISTIC_WRITE)
  @Query("SELECT p FROM Policy p WHERE p.id = (SELECT MIN(q.id) FROM Policy q)")
  Optional<Policy> findGlobalForUpdate();
}
