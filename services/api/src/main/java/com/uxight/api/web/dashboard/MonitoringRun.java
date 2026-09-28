package com.uxight.api.web.dashboard;

public record MonitoringRun(
    Long runId,
    String projectTitle,
    String taskGoal,
    int completedPersonas,
    int totalPersonas,
    String elapsedDisplay
) {
}
