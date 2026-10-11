package com.uxight.api.domain.persona;

import com.uxight.api.common.ApiException;
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
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** 가상 사용자 정의. 리서처 소유이거나, 소유자가 없으면(user_id NULL) 관리자 소유의 공용 Persona 다. */
@Entity
@Table(name = "personas")
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class Persona {

  /** 생성 시 반드시 있어야 하는 profile 속성. 임시 스키마라(GACA-66) 바뀌면 이 목록만 고친다. */
  public static final List<String> REQUIRED_PROFILE_KEYS = List.of("webSkill", "device", "domainKnowledge", "background");

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

  private Persona(User user, String name, Map<String, Object> profile) {
    this.user = user;
    this.name = name;
    this.profile = profile;
  }

  /**
   * 리서처 소유 Persona 를 만든다. 이름 · 속성이 같은 Persona 가 있어도 새로 만든다 — 수정 대신 삭제 후 다시 생성하기 때문이다.
   * profile 에는 필수 속성이 모두 있어야 하고, 그 밖의 키는 그대로 저장한다.
   */
  public static Persona create(User owner, String name, Map<String, Object> profile) {
    validateProfile(profile);
    return new Persona(owner, name, profile);
  }

  /**
   * 행을 지우지 않고 삭제 시각만 기록한다 — run_personas 가 persona_id 를 참조하고, 삭제 전에 요청된 실험의 회차도
   * AI 모듈이 스냅샷의 persona_id 로 실행 결과를 기록한다. 진행 중인 실험은 스냅샷으로 돌므로 확인하지 않는다.
   */
  public void delete() {
    this.deletedAt = LocalDateTime.now();
  }

  /** 관리자 소유의 공용 Persona 인가. 리서처는 공용 Persona 를 삭제할 수 없다. */
  public boolean isCommon() {
    return user == null;
  }

  // 빠졌거나 null · 빈 문자열인 필수 속성을 모두 모아 한 번에 알린다 (fieldErrors 의 field 는 profile.webSkill 형식).
  // 값의 형식(등급 · 척도 · 서술형)은 미정이라 문자열이 아닌 값은 그대로 둔다.
  private static void validateProfile(Map<String, Object> profile) {
    Map<String, String> errors = new LinkedHashMap<>();
    for (String key : REQUIRED_PROFILE_KEYS) {
      Object value = profile.get(key);
      if (value == null || (value instanceof String text && text.isBlank())) {
        errors.put("profile." + key, "필수 속성입니다");
      }
    }
    if (!errors.isEmpty()) {
      throw ApiException.invalidFields(errors);
    }
  }
}
