package com.uxight.api.web.admin;

import com.uxight.api.common.ApiException;
import com.uxight.api.domain.audit.AuditLog;
import com.uxight.api.domain.audit.AuditLogService;
import com.uxight.api.web.common.PageResponse;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.domain.Page;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.time.OffsetDateTime;

/** 감사 로그(관리자). /api/admin/** 는 AdminCheckInterceptor 가 admin · maintainer 만 통과시킨다 — 리서처는 403 AUT-ERR-006. */
@RestController
@RequestMapping("/api/admin/audit-logs")
public class AuditLogController {

  private final AuditLogService auditLogService;

  @Autowired
  public AuditLogController(AuditLogService auditLogService) {
    this.auditLogService = auditLogService;
  }

  /**
   * 기간 안의 감사 로그를 최근 기록 순으로. from 이상 · to 미만, 둘 다 생략할 수 있다. page 는 0부터.
   * from · to 는 시간대가 붙은 ISO-8601 시각이다(쿼리 문자열에서 + 는 %2B). 형식이 틀리면 400 GLB-ERR-001,
   * 범위 밖 값(page &lt; 0 · size &lt; 1 · from 이 to 보다 늦음)은 400 GLB-ERR-002.
   */
  @GetMapping
  public PageResponse<AuditLogResponse> auditLogs(
      @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE_TIME) OffsetDateTime from,
      @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE_TIME) OffsetDateTime to,
      @RequestParam(defaultValue = "0") int page, @RequestParam(defaultValue = "20") int size) {
    if (page < 0) {
      throw ApiException.invalidField("page", "0 이상이어야 합니다");
    }
    if (size < 1) {
      throw ApiException.invalidField("size", "1 이상이어야 합니다");
    }
    if (from != null && to != null && from.isAfter(to)) {
      throw ApiException.invalidField("to", "from 보다 이르면 안 됩니다");
    }
    Page<AuditLog> auditLogs = auditLogService.getAuditLogs(from, to, page, size);
    return PageResponse.of(auditLogs.map(AuditLogResponse::from).getContent(), page, size,
        auditLogs.getTotalElements());
  }
}
