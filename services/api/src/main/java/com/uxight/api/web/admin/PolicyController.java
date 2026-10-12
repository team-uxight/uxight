package com.uxight.api.web.admin;

import com.uxight.api.domain.policy.PolicyService;
import com.uxight.api.domain.policy.PolicyUpdateRequest;
import com.uxight.api.web.common.AuthConst;
import jakarta.validation.Valid;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.RequestAttribute;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/** 정책 관리(관리자). /api/admin/** 는 AdminCheckInterceptor 가 관리자만 통과시킨다 — 리서처는 403 AUT-ERR-006. */
@RestController
@RequestMapping("/api/admin/policy")
public class PolicyController {

  private final PolicyService policyService;

  @Autowired
  public PolicyController(PolicyService policyService) {
    this.policyService = policyService;
  }

  /** 관리자 정책 화면의 전역 정책 값. */
  @GetMapping
  public PolicyResponse policy() {
    return PolicyResponse.from(policyService.getGlobalPolicy());
  }

  /**
   * 바꾼 항목만 보낸다. 수정 후의 전역 정책 전체를 돌려준다. 바뀐 항목은 감사 로그(policy.update)에 남는다.
   * 이후 요청되는 실험부터 적용되고 진행 중인 실험은 멈추지 않는다 — 일일 토큰 예산만 즉시 적용된다.
   */
  @PatchMapping
  public PolicyResponse updatePolicy(@Valid @RequestBody PolicyUpdateRequest request,
      @RequestAttribute(AuthConst.LOGIN_USER_ID) Long adminId) {
    return PolicyResponse.from(policyService.updateGlobalPolicy(adminId, request));
  }
}
