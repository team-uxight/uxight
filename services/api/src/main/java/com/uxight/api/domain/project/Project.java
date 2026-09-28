package com.uxight.api.domain.project;

import java.time.LocalDateTime;

public record Project(
    Long projectId,
    Long userId,
    String title,
    String targetUrl,
    String description,
    String allowedDomains,
    LocalDateTime createdAt,
    LocalDateTime updatedAt
) {
  public static Project newProject(Long userId, String title, String targetUrl, String description, String allowedDomains) {
    return new Project(null, userId, title, targetUrl, description, allowedDomains, null, null);
  }
}
