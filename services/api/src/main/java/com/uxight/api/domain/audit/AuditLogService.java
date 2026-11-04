package com.uxight.api.domain.audit;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Sort;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.time.OffsetDateTime;
import java.time.ZoneId;

@Service
public class AuditLogService {

  // audit_log.ts 는 DB 기본값(CURRENT_TIMESTAMP)이고 MySQL 시간대가 +09:00 이다
  private static final ZoneId DB_ZONE = ZoneId.of("Asia/Seoul");

  private final AuditLogRepository auditLogRepository;

  @Autowired
  public AuditLogService(AuditLogRepository auditLogRepository) {
    this.auditLogRepository = auditLogRepository;
  }

  /**
   * 기간 안의 감사 로그 — 최근 기록 순. from 이상 · to 미만이고, 둘 다 없으면 전체다.
   * Spring(운영 행위)과 AI 모듈(가드 차단)이 쓴 행을 구분하지 않고 함께 돌려준다.
   */
  @Transactional(readOnly = true)
  public Page<AuditLog> getAuditLogs(OffsetDateTime from, OffsetDateTime to, int page, int size) {
    // 같은 시각에 여러 행이 기록될 수 있어 audit_log_id 로 순서를 고정한다
    Sort newestFirst = Sort.by(Sort.Direction.DESC, "ts").and(Sort.by(Sort.Direction.DESC, "id"));
    return auditLogRepository.findByPeriod(toDbTime(from), toDbTime(to), PageRequest.of(page, size, newestFirst));
  }

  private static LocalDateTime toDbTime(OffsetDateTime time) {
    return time == null ? null : time.atZoneSameInstant(DB_ZONE).toLocalDateTime();
  }
}
