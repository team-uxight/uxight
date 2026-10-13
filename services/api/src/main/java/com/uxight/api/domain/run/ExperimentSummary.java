package com.uxight.api.domain.run;

import java.time.LocalDateTime;

/** 실험 목록의 한 줄. runId · round · status · progress 는 실험의 마지막 회차 기준이다. */
public record ExperimentSummary(
    Long firstRunId,
    Long runId,
    int round,
    String status,
    String state,          // in_progress / awaiting_approval / completed / stopped (design-decision 2.6)
    String endType,        // state=stopped 일 때만: cancelling / cancelled / failed
    boolean stale,
    boolean agentUnreachable,   // 마지막 회차가 queued 인데 AI 모듈에 전달하지 못함 — 웹의 "실행 서비스에 연결할 수 없음" 배너
    boolean hasResult,
    String projectTitle,
    String taskGoal,
    String mode,
    Integer progress,
    int personaCount,
    long elapsedSeconds,
    LocalDateTime createdAt
) {
}
