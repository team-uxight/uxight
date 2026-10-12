package com.uxight.api.domain.policy;

import jakarta.validation.constraints.Positive;

/**
 * 바꿀 항목만 보낸다. null(키 없음 · null 값)인 항목은 그대로 둔다.
 * 한도라서 1 이상만 받는다 — 범위 상한은 정해지지 않았다.
 */
public record PolicyUpdateRequest(
    @Positive Integer maxSteps,
    @Positive Integer maxSeconds,
    @Positive Integer maxTokens,
    @Positive Integer runConcurrency,
    @Positive Integer personaConcurrency,
    @Positive Integer rateLimitPerDomain,
    @Positive Long dailyTokenBudget
) {
}
