package com.uxight.api.domain.audit;

import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.time.LocalDateTime;

/**
 * save 는 JpaRepository 가 제공한다. 감사 로그는 추가만 하고 고치지 않는다 — 운영 행위를 하는 서비스가 같은 트랜잭션에서
 * 직접 저장한다(행위와 기록이 함께 커밋 · 롤백). 조회만 AuditLogService 를 거친다.
 */
public interface AuditLogRepository extends JpaRepository<AuditLog, Long> {

  /** 기록 시각이 [from, to) 인 행. 둘 다 DB 시간대(KST) 기준이고, null 이면 그쪽 경계가 없다. */
  @Query("SELECT a FROM AuditLog a WHERE (:from IS NULL OR a.ts >= :from) AND (:to IS NULL OR a.ts < :to)")
  Page<AuditLog> findByPeriod(@Param("from") LocalDateTime from, @Param("to") LocalDateTime to, Pageable pageable);
}
