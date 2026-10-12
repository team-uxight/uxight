package com.uxight.api.domain.policy;

import com.uxight.api.domain.audit.AuditLog;
import com.uxight.api.domain.audit.AuditLogRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.Map;

@Service
public class PolicyService {

  static final String AUDIT_ACTION_UPDATE = "policy.update";

  private final PolicyRepository policyRepository;
  private final AuditLogRepository auditLogRepository;

  @Autowired
  public PolicyService(PolicyRepository policyRepository, AuditLogRepository auditLogRepository) {
    this.policyRepository = policyRepository;
    this.auditLogRepository = auditLogRepository;
  }

  /**
   * 전역 정책. 관리자 정책 화면과 실험 요청의 정책 스냅샷이 모두 이 값을 쓴다 — 화면에 보이는 값이 회차에 실린다.
   * 행이 없으면 V4 마이그레이션이 빠진 것이라 500 이다.
   */
  @Transactional(readOnly = true)
  public Policy getGlobalPolicy() {
    return policyRepository.getGlobal();
  }

  /**
   * 보낸 항목만 바꾸고, 실제로 바뀐 항목이 있으면 감사 로그에 남긴다(같은 트랜잭션 — 함께 커밋 · 롤백).
   * 바꾼 값은 이후 요청되는 실험부터 적용된다. 진행 중인 실험은 시작 시점의 스냅샷으로 실행되며 멈추지 않는다
   * (전체 중단은 별도 API). 단 일일 토큰 예산은 스냅샷에 없어 진행 중인 실험에도 바로 적용된다.
   */
  @Transactional
  public Policy updateGlobalPolicy(Long adminId, PolicyUpdateRequest request) {
    Policy policy = policyRepository.getGlobalForUpdate();
    Map<String, Map<String, Object>> changes = policy.update(request.maxSteps(), request.maxSeconds(),
        request.maxTokens(), request.runConcurrency(), request.personaConcurrency(), request.rateLimitPerDomain(),
        request.dailyTokenBudget());
    if (!changes.isEmpty()) {
      auditLogRepository.save(AuditLog.byUser(adminId, AUDIT_ACTION_UPDATE, "policy:" + policy.getId(),
          Map.of("changes", changes)));
    }
    return policy;
  }
}
