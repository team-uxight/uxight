package com.uxight.api.domain.task;

import com.uxight.api.domain.project.Project;
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

import java.time.LocalDateTime;

/** 과업 정의. 실험 요청마다 하나 생기고, 그 실험의 회차가 모두 참조한다. 아무도 수정 · 삭제하지 않는다 (design-decision 7.1). */
@Entity
@Table(name = "tasks")
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class Task {

  @Id
  @GeneratedValue(strategy = GenerationType.IDENTITY)
  @Column(name = "task_id")
  private Long id;

  @ManyToOne(fetch = FetchType.LAZY)
  @JoinColumn(name = "project_id")
  private Project project;

  private String goal;          // 사람이 읽는 목표 문장

  private String successRule;   // 메인 성공 기준 — 성공 기준 생성 Agent 산출

  private String successUrl;    // 보조 성공 기준 — 리서처 입력

  @Column(name = "is_one_shot")
  private boolean oneShot;      // 되돌릴 수 없는 Task(해지 · 탈퇴) 제외 플래그 — 미결, 지금은 항상 false

  // 두 시각은 DB 기본값(CURRENT_TIMESTAMP · ON UPDATE)이 채운다. JPA 가 null 로 덮지 않게 쓰기에서 뺀다.
  @Column(insertable = false, updatable = false)
  private LocalDateTime createdAt;

  @Column(insertable = false, updatable = false)
  private LocalDateTime updatedAt;

  private Task(Project project, String goal, String successRule, String successUrl) {
    this.project = project;
    this.goal = goal;
    this.successRule = successRule;
    this.successUrl = successUrl;
  }

  public static Task create(Project project, String goal, String successRule, String successUrl) {
    return new Task(project, goal, successRule, successUrl);
  }
}
