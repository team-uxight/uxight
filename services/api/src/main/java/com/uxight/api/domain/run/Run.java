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
    Long improvementId,
    String targetUrlSnapshot,
    String taskSnapshot,
    String policySnapshot,
    String personaSnapshot,
    String dispatchState,
    boolean cancelRequested,
    String status,
    Integer progress,
    LocalDateTime heartbeatAt,
    boolean nextLoopRequested,
    String error,
    Long tokens,
    BigDecimal costUsd,
    LocalDateTime acceptedAt,
    LocalDateTime startedAt,
    LocalDateTime createdAt
) {
  public static Run newRun(Long projectId, Long taskId, String targetUrlSnapshot, String taskSnapshot,
      String policySnapshot, String personaSnapshot) {
    return new Run(null, projectId, taskId, "diagnose", null, null, null,
        targetUrlSnapshot, taskSnapshot, policySnapshot, personaSnapshot,
        null, false, "queued", null, null, false, null, null, null, null, null, null);
  }
}
