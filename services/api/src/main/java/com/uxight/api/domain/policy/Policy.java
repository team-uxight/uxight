package com.uxight.api.domain.policy;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

import java.time.LocalDateTime;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * 실행 한도 · 정책값(전역). AI 모듈이 집행하고, Spring 은 실험 요청 때 회차의 policy_snapshot 으로 복사만 한다 (design-decision 5.5).
 * 값이 null 인 항목은 한도를 두지 않는다는 뜻이 아니라 아직 정하지 않은 값이다 — 기본값은 AI 모듈이 정한다.
 */
@Entity
@Table(name = "policies")
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class Policy {

  @Id
  @GeneratedValue(strategy = GenerationType.IDENTITY)
  @Column(name = "policy_id")
  private Long id;

  private Integer maxSteps;              // Persona 당 최대 스텝

  private Integer maxSeconds;            // Persona 당 최대 시간(초)

  private Integer maxTokens;             // 회차 당 토큰 상한

  private Integer runConcurrency;        // 동시 실험(회차) 수

  private Integer personaConcurrency;    // 회차 안의 동시 Persona 수

  private Integer rateLimitPerDomain;    // 도메인당 요청 상한

  private Long dailyTokenBudget;         // 일일 토큰 예산 — 스냅샷에 넣지 않는다 (모든 회차가 나눠 쓰는 하나의 한도)

  @JdbcTypeCode(SqlTypes.JSON)
  private Map<String, Object> modelMap;  // 역할별 모델 · base URL

  // 두 시각은 DB 기본값(CURRENT_TIMESTAMP · ON UPDATE)이 채운다. JPA 가 null 로 덮지 않게 쓰기에서 뺀다.
  @Column(insertable = false, updatable = false)
  private LocalDateTime createdAt;

  @Column(insertable = false, updatable = false)
  private LocalDateTime updatedAt;

  /**
   * 회차의 policy_snapshot 으로 복사할 값. 키는 AI 모듈이 읽는 snake_case 다.
   * daily_token_budget 은 넣지 않는다 — 모든 회차가 나눠 쓰는 한도라 AI 모듈이 매번 policies 의 현재 값을 읽는다 (design-decision 5.5).
   * 값이 없는(null) 항목은 빼서 AI 모듈의 기본값을 쓰게 한다.
   */
  public Map<String, Object> toSnapshot() {
    Map<String, Object> snapshot = new LinkedHashMap<>();
    putIfPresent(snapshot, "max_steps", maxSteps);
    putIfPresent(snapshot, "max_seconds", maxSeconds);
    putIfPresent(snapshot, "max_tokens", maxTokens);
    putIfPresent(snapshot, "run_concurrency", runConcurrency);
    putIfPresent(snapshot, "persona_concurrency", personaConcurrency);
    putIfPresent(snapshot, "rate_limit_per_domain", rateLimitPerDomain);
    putIfPresent(snapshot, "model_map", modelMap);
    return snapshot;
  }

  private static void putIfPresent(Map<String, Object> snapshot, String key, Object value) {
    if (value != null) {
      snapshot.put(key, value);
    }
  }
}
