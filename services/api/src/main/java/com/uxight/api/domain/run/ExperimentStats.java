package com.uxight.api.domain.run;

import java.time.OffsetDateTime;

/**
 * 실험 모니터링 · 실험 이력의 건수. 상태 네 분류는 겹치지 않으므로 totalCount 는 네 분류 건수의 합이다
 * (중단 건수는 응답에 없다 — totalCount 에서 나머지를 빼면 된다).
 *
 * @param completedThisWeekCount 완료된 실험 중 마지막 회차의 종료 시각이 thisWeekFrom 이후인 것
 * @param totalTokens            본인 실험의 모든 회차 누적 토큰 합
 * @param thisWeekFrom           이번 주 시작 시각. '이번 주 완료'로 이동할 때 GET /api/runs 의 finishedFrom 으로 넘긴다
 */
public record ExperimentStats(
    long totalCount,
    long inProgressCount,
    long completedCount,
    long completedThisWeekCount,
    long awaitingApprovalCount,
    long totalTokens,
    OffsetDateTime thisWeekFrom
) {
}
