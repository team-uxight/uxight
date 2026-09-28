package com.uxight.api.domain.project;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

public class ProjectForm {

  @NotBlank
  @Size(max = 100)
  private String title;

  @NotBlank
  @Size(max = 2048)
  // agent 가 여는 것은 웹 페이지뿐 — file:/ · javascript: 같은 스킴은 막는다 (agent-safety §2.2).
  @Pattern(regexp = "^https?://.+", message = "http:// 또는 https://로 시작하는 URL이어야 합니다")
  private String targetUrl;

  @Size(max = 1000)
  private String description;

  @NotBlank
  private String allowedDomains = "{\"mock\": \"test\"}";

  public String getTitle() {
    return title;
  }

  public void setTitle(String title) {
    this.title = title;
  }

  public String getTargetUrl() {
    return targetUrl;
  }

  public void setTargetUrl(String targetUrl) {
    this.targetUrl = targetUrl;
  }

  public String getDescription() {
    return description;
  }

  public void setDescription(String description) {
    this.description = description;
  }

  public String getAllowedDomains() {
    return allowedDomains;
  }

  public void setAllowedDomains(String allowedDomains) {
    this.allowedDomains = allowedDomains;
  }
}
