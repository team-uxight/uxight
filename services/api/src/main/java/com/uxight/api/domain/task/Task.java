package com.uxight.api.domain.task;

import java.time.LocalDateTime;

public record Task(
    Long taskId,
    Long projectId,
    String goal,
    String successRule,   // 메인 성공 기준 — 성공 기준 생성 Agent 산출
    String successUrl,    // 보조 성공 기준 — 리서처 입력
    boolean isOneShot,
    LocalDateTime createdAt,
    LocalDateTime updatedAt
) {
  public static Task newTask(Long projectId, String goal, String successRule, String successUrl) {
    return new Task(null, projectId, goal, successRule, successUrl, false, null, null);
  }
}
