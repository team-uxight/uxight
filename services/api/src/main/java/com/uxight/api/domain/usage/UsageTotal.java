package com.uxight.api.domain.usage;

import java.math.BigDecimal;
import java.util.List;

/** 기간 합계. 일별 사용량을 더한 값이다. */
public record UsageTotal(BigDecimal costUsd, long tokens, long runCount) {

  public static UsageTotal of(List<UsageDay> days) {
    return new UsageTotal(
        days.stream().map(UsageDay::costUsd).reduce(BigDecimal.ZERO, BigDecimal::add),
        days.stream().mapToLong(UsageDay::tokens).sum(),
        days.stream().mapToLong(UsageDay::runCount).sum());
  }
}
