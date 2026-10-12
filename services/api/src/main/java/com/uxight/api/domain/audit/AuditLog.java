package com.uxight.api.domain.audit;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;
import org.hibernate.annotations.Immutable;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

import java.time.LocalDateTime;
import java.util.Map;

/**
 * 감사 로그 한 줄. append-only — Spring(운영 행위)과 Python(가드가 차단한 액션)이 각자 행을 추가하고, 고치는 쪽은 없다.
 * @Immutable 이라 JPA 는 INSERT 만 하고 UPDATE 를 만들지 않는다.
 */
@Entity
@Table(name = "audit_log")
@Immutable
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class AuditLog {

  @Id
  @GeneratedValue(strategy = GenerationType.IDENTITY)
  @Column(name = "audit_log_id")
  private Long id;

  private String actor;    // user:<id> 또는 agent:<run_id>

  private String action;   // 행위 종류 (예: policy.update)

  private String target;   // 대상 (예: policy:1)

  @JdbcTypeCode(SqlTypes.JSON)
  private Map<String, Object> detail;

  @Column(insertable = false, updatable = false)
  private LocalDateTime ts;   // DB 기본값

  private AuditLog(String actor, String action, String target, Map<String, Object> detail) {
    this.actor = actor;
    this.action = action;
    this.target = target;
    this.detail = detail;
  }

  /** 사람(관리자 등)의 운영 행위. actor 는 user:<userId>. */
  public static AuditLog byUser(Long userId, String action, String target, Map<String, Object> detail) {
    return new AuditLog("user:" + userId, action, target, detail);
  }
}
