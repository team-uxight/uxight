package com.uxight.api.web.project;

import com.uxight.api.domain.project.Project;

import java.util.List;

public record ProjectDetail(
    Long projectId,
    String title,
    String targetUrl,
    String description,
    List<String> allowedDomains
) {
  public static ProjectDetail from(Project project) {
    return new ProjectDetail(project.getId(), project.getTitle(), project.getTargetUrl(), project.getDescription(),
        project.getAllowedDomains());
  }
}
