package com.uxight.api.web.project;

import com.uxight.api.domain.project.Project;

public record ProjectSummary(Long projectId, String title, String targetUrl, String description) {

  public static ProjectSummary from(Project project) {
    return new ProjectSummary(project.projectId(), project.title(), project.targetUrl(), project.description());
  }
}
