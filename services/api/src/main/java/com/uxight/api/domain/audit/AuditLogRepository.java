package com.uxight.api.domain.audit;

import org.springframework.data.jpa.repository.JpaRepository;

/**
 * save 는 JpaRepository 가 제공한다. 감사 로그는 추가만 하고 고치지 않으며 비즈니스 로직이 없어 서비스 계층을 두지 않는다 —
 * 운영 행위를 하는 서비스가 같은 트랜잭션에서 직접 저장한다(행위와 기록이 함께 커밋 · 롤백).
 */
public interface AuditLogRepository extends JpaRepository<AuditLog, Long> {
}
