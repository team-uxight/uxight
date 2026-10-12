package com.uxight.api.domain.policy;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class PolicyService {

  private final PolicyRepository policyRepository;

  @Autowired
  public PolicyService(PolicyRepository policyRepository) {
    this.policyRepository = policyRepository;
  }

  /**
   * 전역 정책. 관리자 정책 화면과 실험 요청의 정책 스냅샷이 모두 이 값을 쓴다 — 화면에 보이는 값이 회차에 실린다.
   * 행이 없으면 V4 마이그레이션이 빠진 것이라 500 이다.
   */
  @Transactional(readOnly = true)
  public Policy getGlobalPolicy() {
    return policyRepository.getGlobal();
  }
}
