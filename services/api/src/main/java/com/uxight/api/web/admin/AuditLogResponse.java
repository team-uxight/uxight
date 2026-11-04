package com.uxight.api.web.admin;

import com.uxight.api.domain.audit.AuditLog;

import java.time.LocalDateTime;
import java.util.Map;

/** 감사 로그 한 줄. actor 는 사람이면 user:&lt;userId&gt;, Agent 면 agent:&lt;runId&gt;. target · detail 은 없을 수 있다. */
public record AuditLogResponse(Long auditLogId, String actor, String action, String target, Map<String, Object> detail,
    LocalDateTime ts) {

  public static AuditLogResponse from(AuditLog auditLog) {
    return new AuditLogResponse(auditLog.getId(), auditLog.getActor(), auditLog.getAction(), auditLog.getTarget(),
        auditLog.getDetail(), auditLog.getTs());
  }
}
