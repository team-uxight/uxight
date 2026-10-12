package com.uxight.api.domain.run;

import java.util.List;

/**
 * 실험의 회차 목록과 실험 단위 상태.
 *
 * @param rounds           runId 순
 * @param awaitingApproval 실험이 다음 회차 승인을 기다리는 중인가 — 실험 상태(state)가 awaiting_approval
 */
public record ExperimentRounds(List<RoundSummary> rounds, boolean awaitingApproval) {
}
