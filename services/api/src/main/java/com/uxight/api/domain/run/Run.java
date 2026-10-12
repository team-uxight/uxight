package com.uxight.api.domain.run;

import com.uxight.api.domain.project.Project;
import com.uxight.api.domain.task.Task;
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
import org.hibernate.annotations.DynamicUpdate;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

/**
 * 회차 1회 = Persona N명 전체. 실험은 first_run_id 가 같은 회차들이다.
 *
 * <p>Spring [S] 과 Python [P] 이 같은 행을 나눠 쓴다 (architecture 3.3). JPA 가 Python 이 쓴 값을 옛 값으로 되돌리지 않게
 * <ul>
 *   <li>@DynamicUpdate — UPDATE 에 바뀐 컬럼만 넣는다</li>
 *   <li>[P] 컬럼은 쓰기에서 뺀다. status 만 INSERT 때 queued 를 넣고 그 뒤로는 쓰지 않는다</li>
 *   <li>INSERT 뒤 바뀌지 않는 [S] 컬럼(스냅샷 등)도 updatable = false</li>
 * </ul>
 * dispatch_state · cancel_requested 는 조건부 한 줄 UPDATE 로 바꾼다 (RunRepository).
 */
@Entity
@Table(name = "runs")
@DynamicUpdate
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class Run {

  @Id
  @GeneratedValue(strategy = GenerationType.IDENTITY)
  @Column(name = "run_id")
  private Long id;

  // ───────── [S] Spring — INSERT 뒤 바뀌지 않는다 ─────────

  @ManyToOne(fetch = FetchType.LAZY)
  @JoinColumn(name = "project_id", updatable = false)
  private Project project;

  @ManyToOne(fetch = FetchType.LAZY)
  @JoinColumn(name = "task_id", updatable = false)
  private Task task;

  @Enumerated(EnumType.STRING)
  @Column(updatable = false)
  private RunMode mode;

  @Column(updatable = false)
  private Integer loopMax;            // mode = loop 일 때만. 최초 회차 포함 최대 회차 수

  @ManyToOne(fetch = FetchType.LAZY)
  @JoinColumn(name = "parent_run_id", updatable = false)
  private Run parentRun;              // 다음 회차만. 직전 회차

  @Column(updatable = false)
  private Long improvementId;         // 다음 회차만. improvements 테이블 도입 때 연관 관계로 바꾼다

  @Column(updatable = false)
  private String targetUrlSnapshot;

  @JdbcTypeCode(SqlTypes.JSON)
  @Column(updatable = false)
  private List<String> allowedDomainsSnapshot;

  @JdbcTypeCode(SqlTypes.JSON)
  @Column(updatable = false)
  private Map<String, Object> taskSnapshot;

  @JdbcTypeCode(SqlTypes.JSON)
  @Column(updatable = false)
  private Map<String, Object> policySnapshot;

  @JdbcTypeCode(SqlTypes.JSON)
  @Column(updatable = false)
  private List<Map<String, Object>> personaSnapshot;

  // ───────── [S] Spring — INSERT 뒤에도 바뀐다 ─────────

  @ManyToOne(fetch = FetchType.LAZY)
  @JoinColumn(name = "first_run_id")
  private Run firstRun;               // 실험 식별자. 최초 회차는 INSERT 직후 자기 자신 (markAsFirstRound)

  @Enumerated(EnumType.STRING)
  private DispatchState dispatchState;

  private boolean cancelRequested;

  // ───────── [P] Python — Spring 은 읽기만 한다 ─────────

  @Enumerated(EnumType.STRING)
  @Column(updatable = false)
  private RunStatus status;           // INSERT 때 queued 만 쓴다

  @Column(insertable = false, updatable = false)
  private Integer progress;           // 완료 Persona 수

  @Column(insertable = false, updatable = false)
  private LocalDateTime heartbeatAt;

  @Column(insertable = false, updatable = false)
  private String error;

  @Column(insertable = false, updatable = false)
  private Long tokens;

  @Column(insertable = false, updatable = false)
  private BigDecimal costUsd;

  @Column(insertable = false, updatable = false)
  private LocalDateTime acceptedAt;

  @Column(insertable = false, updatable = false)
  private LocalDateTime startedAt;

  @Column(insertable = false, updatable = false)
  private LocalDateTime finishedAt;

  @Column(insertable = false, updatable = false)
  private LocalDateTime createdAt;    // DB 기본값

  private Run(Project project, Task task, RunMode mode, Integer loopMax, String targetUrlSnapshot,
      List<String> allowedDomainsSnapshot, Map<String, Object> taskSnapshot, Map<String, Object> policySnapshot,
      List<Map<String, Object>> personaSnapshot) {
    this.project = project;
    this.task = task;
    this.mode = mode;
    this.loopMax = loopMax;
    this.targetUrlSnapshot = targetUrlSnapshot;
    this.allowedDomainsSnapshot = allowedDomainsSnapshot;
    this.taskSnapshot = taskSnapshot;
    this.policySnapshot = policySnapshot;
    this.personaSnapshot = personaSnapshot;
    this.status = RunStatus.queued;
  }

  /**
   * 실험의 최초 회차. status 는 queued 로 시작한다 — Python 은 queued 인 행만 접수한다.
   * first_run_id 는 run_id 가 정해진 뒤 같은 트랜잭션에서 markAsFirstRound 로 채운다.
   */
  public static Run firstRound(Project project, Task task, RunMode mode, Integer loopMax, String targetUrlSnapshot,
      List<String> allowedDomainsSnapshot, Map<String, Object> taskSnapshot, Map<String, Object> policySnapshot,
      List<Map<String, Object>> personaSnapshot) {
    return new Run(project, task, mode, mode == RunMode.loop ? loopMax : null, targetUrlSnapshot,
        allowedDomainsSnapshot, taskSnapshot, policySnapshot, personaSnapshot);
  }

  /** 최초 회차는 자기 자신이 실험 식별자다. INSERT(IDENTITY) 뒤에 부른다 — 커밋 때 first_run_id 만 UPDATE 된다. */
  public void markAsFirstRound() {
    this.firstRun = this;
  }
}
