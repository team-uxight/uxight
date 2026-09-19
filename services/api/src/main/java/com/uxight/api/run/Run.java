package com.uxight.api.run;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.time.Instant;

/**
 * 실행 1건. 테이블 소유권: 생성은 api, 상태(status) · 결과 갱신은 agent 가 MySQL 에 직접 쓴다 (tech-stack §4).
 * 스키마가 굳으면 ddl-auto 대신 마이그레이션(Flyway)으로 옮긴다 — 마이그레이션 주체는 api 하나.
 */
@Entity
@Table(name = "runs")
public class Run {
  @Id
  @GeneratedValue(strategy = GenerationType.IDENTITY)
  private Long id;

  @Column(name = "target_url", nullable = false, length = 2048)
  private String targetUrl;

  @Column(nullable = false, length = 1000)
  private String task;

  /** QUEUED → RUNNING → DONE | FAILED. RUNNING 이후는 agent 가 쓴다. */
  @Column(nullable = false, length = 16)
  private String status = "QUEUED";

  @Column(name = "created_at", nullable = false, updatable = false)
  private Instant createdAt = Instant.now();

  protected Run() {}

  public Run(String targetUrl, String task) {
    this.targetUrl = targetUrl;
    this.task = task;
  }

  public Long getId() { return id; }
  public String getTargetUrl() { return targetUrl; }
  public String getTask() { return task; }
  public String getStatus() { return status; }
  public Instant getCreatedAt() { return createdAt; }
}
