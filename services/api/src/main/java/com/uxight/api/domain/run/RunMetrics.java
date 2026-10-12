package com.uxight.api.domain.run;

import java.math.BigDecimal;

/**
 * 회차 종료 시 확정된 지표(run_metrics) — Python 이 쓴다. 회차 목록과 결과 조회가 같은 구성을 쓴다.
 *
 * @param successRate 성공 Persona(run_personas.status = done) 비율. 0 이상 100 이하
 */
public record RunMetrics(
    BigDecimal successRate,
    BigDecimal avgSteps,
    BigDecimal avgBacktracks,
    BigDecimal avgSeconds,
    Long tokens,
    BigDecimal costUsd
) {
}
