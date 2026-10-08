package com.uxight.api.web.project;

import com.fasterxml.jackson.annotation.JsonRawValue;
import com.uxight.api.domain.project.Project;

public record ProjectDetail(
    Long projectId,
    String title,
    String targetUrl,
    String description,
    @JsonRawValue String allowedDomains   // DB 의 JSON 배열을 그대로 싣는다
) {
  public static ProjectDetail from(Project project) {
    return new ProjectDetail(project.projectId(), project.title(), project.targetUrl(), project.description(),
        project.allowedDomains());
  }
}
