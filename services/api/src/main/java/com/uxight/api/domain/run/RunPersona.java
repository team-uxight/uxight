package com.uxight.api.domain.run;

import java.math.BigDecimal;
import java.time.LocalDateTime;

public record RunPersona(
    Long runPersonaId,
    Long runId,
    Long personaId,
    String status,
    Boolean agentDone,
    Boolean ruleSuccess,
    Integer steps,
    Integer backtracks,
    Long tokens,
    BigDecimal costUsd,
    String logPath,
    LocalDateTime startedAt,
    LocalDateTime finishedAt
) {
}
