package com.uxight.api.web.admin;

import com.uxight.api.domain.usage.MonthlyUsage;
import com.uxight.api.domain.usage.UsageService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.time.YearMonth;

/** 모델 사용량(관리자). /api/admin/** 는 AdminCheckInterceptor 가 admin · maintainer 만 통과시킨다 — 리서처는 403 AUT-ERR-006. */
@RestController
@RequestMapping("/api/admin/usage")
public class UsageController {

  private final UsageService usageService;

  @Autowired
  public UsageController(UsageService usageService) {
    this.usageService = usageService;
  }

  /**
   * 한 달의 비용 · 토큰 · 회차 수 합계와 일별 값. month 는 yyyy-MM(예: 2026-10), 생략하면 이번 달(KST).
   * 형식이 틀리면(2026-13 · 202610) 400 GLB-ERR-001.
   */
  @GetMapping
  public MonthlyUsage usage(@RequestParam(required = false) @DateTimeFormat(pattern = "yyyy-MM") YearMonth month) {
    return usageService.getMonthlyUsage(month == null ? usageService.currentMonth() : month);
  }
}
