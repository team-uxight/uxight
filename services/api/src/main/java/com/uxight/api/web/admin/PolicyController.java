package com.uxight.api.web.admin;

import com.uxight.api.domain.policy.PolicyService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.GetMapping;
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
}
