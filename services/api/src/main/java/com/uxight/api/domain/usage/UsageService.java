package com.uxight.api.domain.usage;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDate;
import java.time.YearMonth;
import java.time.ZoneId;
import java.util.List;
import java.util.Map;
import java.util.function.Function;
import java.util.stream.Collectors;

@Service
public class UsageService {

  private static final ZoneId SERVICE_ZONE = ZoneId.of("Asia/Seoul");   // '오늘' · 날짜 경계 — runs.created_at 과 같은 시간대

  private final UsageQueryRepository usageQueryRepository;

  @Autowired
  public UsageService(UsageQueryRepository usageQueryRepository) {
    this.usageQueryRepository = usageQueryRepository;
  }

  /**
   * 한 달 사용량(비용 · 토큰 · 회차 수)과 일별 값. 회차가 없는 날도 0 으로 채워 날짜가 빠지지 않게 한다.
   * 이번 달은 오늘까지, 지난달은 말일까지, 앞으로의 달은 빈 목록이다.
   */
  @Transactional(readOnly = true)
  public MonthlyUsage getMonthlyUsage(YearMonth month) {
    LocalDate today = LocalDate.now(SERVICE_ZONE);
    LocalDate first = month.atDay(1);
    LocalDate last = month.atEndOfMonth().isAfter(today) ? today : month.atEndOfMonth();
    if (last.isBefore(first)) {
      return new MonthlyUsage(month, UsageTotal.of(List.of()), List.of());
    }

    Map<LocalDate, UsageDay> byDate = usageQueryRepository.findDaily(first, last).stream()
        .collect(Collectors.toMap(UsageDay::date, Function.identity()));
    List<UsageDay> daily = first.datesUntil(last.plusDays(1))
        .map(date -> byDate.getOrDefault(date, UsageDay.empty(date)))
        .toList();
    return new MonthlyUsage(month, UsageTotal.of(daily), daily);
  }

  /** month 를 생략했을 때의 달 — 서비스 시간대(KST)의 이번 달. */
  public YearMonth currentMonth() {
    return YearMonth.now(SERVICE_ZONE);
  }
}
