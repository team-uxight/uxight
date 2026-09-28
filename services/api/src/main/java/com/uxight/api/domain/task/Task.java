package com.uxight.api.domain.task;

import java.time.LocalDateTime;

public record Task(
    Long taskId,
    Long projectId,
    String goal,
    String successCriteria,
    boolean isOneShot,
    LocalDateTime createdAt,
    LocalDateTime updatedAt
) {
  public static Task newTask(Long projectId, String goal, String successCriteria, boolean isOneShot) {
    return new Task(null, projectId, goal, successCriteria, isOneShot, null, null);
  }
}
