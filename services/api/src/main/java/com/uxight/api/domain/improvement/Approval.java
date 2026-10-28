package com.uxight.api.domain.improvement;

import com.uxight.api.domain.user.User;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
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
import org.hibernate.annotations.Immutable;

import java.time.LocalDateTime;

/**
 * 개선안 하나에 대한 결정(승인 · 반려). 승인은 개선안 자체가 아니라 그 개선안을 적용한 다음 회차 진행에 대한 승인이다.
 * Spring 이 쓴다. 개선안당 결정은 하나뿐이고(UNIQUE) 바꾸지 않으므로 @Immutable — INSERT 만 한다.
 */
@Entity
@Table(name = "approvals")
@Immutable
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class Approval {

  @Id
  @GeneratedValue(strategy = GenerationType.IDENTITY)
  @Column(name = "approval_id")
  private Long id;

  @ManyToOne(fetch = FetchType.LAZY)
  @JoinColumn(name = "improvement_id")
  private Improvement improvement;

  @ManyToOne(fetch = FetchType.LAZY)
  @JoinColumn(name = "user_id")
  private User user;            // 결정한 사람

  @Enumerated(EnumType.STRING)
  private Decision decision;

  private String note;          // 결정 사유

  @Column(insertable = false, updatable = false)
  private LocalDateTime decidedAt;   // DB 기본값

  private Approval(Improvement improvement, User user, Decision decision, String note) {
    this.improvement = improvement;
    this.user = user;
    this.decision = decision;
    this.note = note;
  }

  /** 결정 기록. 승인 가능 조건은 ImprovementService 가 프로젝트 행 잠금 안에서 확인한 뒤 부른다. 빈 사유는 null 로 둔다. */
  public static Approval decide(Improvement improvement, User user, Decision decision, String note) {
    return new Approval(improvement, user, decision, note == null || note.isBlank() ? null : note.strip());
  }
}
