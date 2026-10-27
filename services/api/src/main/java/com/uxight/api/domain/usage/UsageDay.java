package com.uxight.api.domain.usage;

import java.math.BigDecimal;
import java.time.LocalDate;

/**
 * 하루 사용량. 그날(KST) 요청된 회차들의 합이다.
 *
 * @param costUsd  비용(USD). AI 모듈이 스텝마다 누적한 runs.cost_usd 의 합 — 실패 · 취소 · 진행 중 회차도 쓴 만큼 들어간다
 * @param tokens   토큰 합
 * @param runCount 회차 수
 */
public record UsageDay(LocalDate date, BigDecimal costUsd, long tokens, long runCount) {

  public static UsageDay empty(LocalDate date) {
    return new UsageDay(date, BigDecimal.ZERO, 0, 0);
  }
}
