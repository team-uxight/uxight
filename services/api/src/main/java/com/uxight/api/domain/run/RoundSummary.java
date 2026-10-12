package com.uxight.api.domain.run;

import java.time.LocalDateTime;

/**
 * 실험의 회차 한 줄.
 *
 * @param round                몇 번째 회차인지 — 같은 실험에서 runId 가 이 회차 이하인 회차 수
 * @param appliedImprovementId 이 회차를 만든 승인 개선안. 최초 회차는 null
 * @param metrics              회차 종료 시 확정된 지표. 아직 없으면 null
 */
public record RoundSummary(
    Long runId,
    int round,
    String status,
    Long appliedImprovementId,
    LocalDateTime createdAt,
    LocalDateTime finishedAt,
    RunMetrics metrics
) {
}
