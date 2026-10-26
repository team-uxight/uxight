package com.uxight.api.domain.usage;

import java.time.YearMonth;
import java.util.List;

/** 한 달 사용량. daily 는 그 달 1일부터 — 이번 달이면 오늘까지, 지난달이면 말일까지, 앞으로의 달이면 비어 있다. */
public record MonthlyUsage(YearMonth month, UsageTotal total, List<UsageDay> daily) {
}
