package com.uxight.api.domain.persona;

import com.uxight.api.domain.user.User;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

import java.time.LocalDateTime;
import java.util.Map;

/** 가상 사용자 정의. 리서처 소유이거나, 소유자가 없으면(user_id NULL) 관리자 소유의 공용 Persona 다. */
@Entity
@Table(name = "personas")
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class Persona {

  @Id
  @GeneratedValue(strategy = GenerationType.IDENTITY)
  @Column(name = "persona_id")
  private Long id;

  @ManyToOne(fetch = FetchType.LAZY)
  @JoinColumn(name = "user_id")
  private User user;   // null 이면 공용 Persona

  private String name;

  // 웹 숙련도 · 사용 기기 · 도메인 지식 · 배경. 키 구성이 아직 확정되지 않아(GACA-66) 고정 타입 대신 JSON 객체 그대로 다룬다.
  @JdbcTypeCode(SqlTypes.JSON)
  private Map<String, Object> profile;

  private LocalDateTime deletedAt;   // 삭제 시각. null 이면 사용 중 (삭제 표시)

  // 두 시각은 DB 기본값(CURRENT_TIMESTAMP · ON UPDATE)이 채운다. JPA 가 null 로 덮지 않게 쓰기에서 뺀다.
  @Column(insertable = false, updatable = false)
  private LocalDateTime createdAt;

  @Column(insertable = false, updatable = false)
  private LocalDateTime updatedAt;

  /** 관리자 소유의 공용 Persona 인가. 리서처는 공용 Persona 를 삭제할 수 없다. */
  public boolean isCommon() {
    return user == null;
  }
}
