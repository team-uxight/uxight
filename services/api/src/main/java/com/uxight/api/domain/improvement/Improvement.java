package com.uxight.api.domain.improvement;

import com.uxight.api.domain.run.Run;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.FetchType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;
import org.hibernate.annotations.Immutable;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

/**
 * 개선안 — AI 모듈이 회차의 진단을 종합해 산출한 수정 제안(회차당 최대 3안). 패치 4종 중 하나로 표현된다.
 * 행은 AI 모듈이 쓰고 Spring 은 읽기만 하므로 @Immutable. 승인 · 반려는 사람이 하는 행위라 approvals 에 따로 쓴다.
 */
@Entity
@Table(name = "improvements")
@Immutable
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class Improvement {

  @Id
  @Column(name = "improvement_id")
  private Long id;

  @ManyToOne(fetch = FetchType.LAZY)
  @JoinColumn(name = "run_id")
  private Run run;              // 개선안을 산출한 회차

  @JdbcTypeCode(SqlTypes.JSON)
  private List<Long> findingIds;   // 다루는 진단 — JSON 이라 외래 키가 없다. 같은 회차의 진단만 읽는다

  private int optionNo;         // 1~3안

  @Enumerated(EnumType.STRING)
  private PatchKind patchKind;

  @JdbcTypeCode(SqlTypes.JSON)
  private Map<String, Object> patch;   // 종류별 파라미터. 구조는 미정 — 저장된 그대로 전달한다

  private String rationale;     // 근거

  private String expectedEffect;   // 예상 효과

  private String fixCost;       // 구현 비용 추정

  private LocalDateTime createdAt;
}
