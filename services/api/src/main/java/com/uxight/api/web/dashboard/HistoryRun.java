package com.uxight.api.web.dashboard;

public record HistoryRun(
    Long runId,
    String endType,
    String projectTitle,
    String taskGoal,
    String elapsedDisplay,
    int completedPersonas,
    int totalPersonas
) {
}
