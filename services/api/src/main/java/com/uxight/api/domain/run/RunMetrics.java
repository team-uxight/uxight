package com.uxight.api.domain.run;

import java.math.BigDecimal;

/**
 * 회차 종료 시 확정된 지표(run_metrics) — Python 이 쓴다. 회차 목록과 결과 조회가 같은 구성을 쓴다.
 *
 * @param successRate 성공 Persona 비율 — 성공(성공 URL 에 닿고 done 으로 끝남) ÷ 판정한 Persona(성공 · 어렵게 성공 · 실패).
 *                    AI 모듈이 회차 종료 시 계산해 쓰고(T42) Spring 은 읽기만 한다. 0 이상 100 이하
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
