package com.uxight.api.domain.run;

import java.math.BigDecimal;
import java.time.LocalDateTime;

public record Run(
    Long runId,
    Long projectId,
    Long taskId,
    String mode,
    Integer loopMax,
    Long parentRunId,
    Long firstRunId,
    Long improvementId,
    String targetUrlSnapshot,
    String allowedDomainsSnapshot,   // JSON 배열 원문
    String taskSnapshot,
    String policySnapshot,
    String personaSnapshot,
    String dispatchState,
    boolean cancelRequested,
    String status,
    Integer progress,
    LocalDateTime heartbeatAt,
    String error,
    Long tokens,
    BigDecimal costUsd,
    LocalDateTime acceptedAt,
    LocalDateTime startedAt,
    LocalDateTime finishedAt,
    LocalDateTime createdAt
) {
  /** 최초 회차. first_run_id 는 INSERT 뒤 같은 트랜잭션에서 자기 run_id 로 채운다 (RunRepository.updateFirstRunId). */
  public static Run newFirstRound(Long projectId, Long taskId, String mode, Integer loopMax, String targetUrlSnapshot,
      String allowedDomainsSnapshot, String taskSnapshot, String policySnapshot, String personaSnapshot) {
    return new Run(null, projectId, taskId, mode, loopMax, null, null, null,
        targetUrlSnapshot, allowedDomainsSnapshot, taskSnapshot, policySnapshot, personaSnapshot,
        null, false, "queued", null, null, null, null, null, null, null, null, null);
  }
}
