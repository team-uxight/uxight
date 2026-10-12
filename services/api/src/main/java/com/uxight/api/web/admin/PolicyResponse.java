package com.uxight.api.web.admin;

import com.uxight.api.domain.policy.Policy;

/**
 * 전역 정책(관리자 화면). AI 모듈이 집행하는 실행 한도다. modelMap(역할별 모델 · 주소)은 화면에 싣지 않는다.
 *
 * @param maxSeconds         Persona 당 최대 실행 시간(초)
 * @param rateLimitPerDomain 대상 도메인당 요청 상한 — 단위(분당 · 초당)는 미정
 * @param dailyTokenBudget   일일 토큰 예산 — 회차 스냅샷에 넣지 않아 수정하면 진행 중인 실험에도 바로 적용된다
 */
public record PolicyResponse(
    Integer maxSteps,
    Integer maxSeconds,
    Integer maxTokens,
    Integer runConcurrency,
    Integer personaConcurrency,
    Integer rateLimitPerDomain,
    Long dailyTokenBudget
) {
  public static PolicyResponse from(Policy policy) {
    return new PolicyResponse(policy.getMaxSteps(), policy.getMaxSeconds(), policy.getMaxTokens(),
        policy.getRunConcurrency(), policy.getPersonaConcurrency(), policy.getRateLimitPerDomain(),
        policy.getDailyTokenBudget());
  }
}
