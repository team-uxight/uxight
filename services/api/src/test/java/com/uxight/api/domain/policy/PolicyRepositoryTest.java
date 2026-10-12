package com.uxight.api.domain.policy;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.transaction.annotation.Transactional;

/** V4 마이그레이션이 넣는 전역 정책 1행이 엔티티로 읽히는지 본다. 로컬 seed 가 아니라 모든 환경에 들어가는 행이다. */
@SpringBootTest
@Transactional
class PolicyRepositoryTest {

  @Autowired
  private PolicyRepository policyRepository;

  @Test
  void v4Migration_insertsOneGlobalPolicy_withSmallLimits() {
    assertThat(policyRepository.count()).isEqualTo(1);

    Policy policy = policyRepository.findById(1L).orElseThrow();
    assertThat(policy.getMaxSteps()).isEqualTo(10);
    assertThat(policy.getMaxSeconds()).isEqualTo(120);
    assertThat(policy.getMaxTokens()).isEqualTo(20000);
    assertThat(policy.getRunConcurrency()).isEqualTo(1);
    assertThat(policy.getPersonaConcurrency()).isEqualTo(2);
    assertThat(policy.getRateLimitPerDomain()).isEqualTo(30);
    assertThat(policy.getDailyTokenBudget()).isEqualTo(200000L);
    assertThat(policy.getModelMap()).isNull();
    assertThat(policy.getCreatedAt()).isNotNull();
  }
}
