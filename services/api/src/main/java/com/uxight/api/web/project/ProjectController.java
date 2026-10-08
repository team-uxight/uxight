package com.uxight.api.web.project;

import com.uxight.api.domain.project.ProjectCreateRequest;
import com.uxight.api.domain.project.ProjectService;
import com.uxight.api.web.common.SessionConst;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.bind.annotation.SessionAttribute;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/projects")
public class ProjectController {

  private final ProjectService projectService;

  public ProjectController(ProjectService projectService) {
    this.projectService = projectService;
  }

  @GetMapping
  public Map<String, List<ProjectSummary>> projects(@SessionAttribute(SessionConst.LOGIN_USER_ID) Long userId) {
    List<ProjectSummary> projects = projectService.getProjectsByUser(userId).stream()
        .map(ProjectSummary::from)
        .toList();
    return Map.of("projects", projects);
  }

  @PostMapping
  @ResponseStatus(HttpStatus.CREATED)
  public Map<String, Long> createProject(@Valid @RequestBody ProjectCreateRequest request,
      @SessionAttribute(SessionConst.LOGIN_USER_ID) Long userId) {
    return Map.of("projectId", projectService.createProject(userId, request));
  }

  @GetMapping("/{projectId}")
  public ProjectDetail project(@PathVariable Long projectId, @SessionAttribute(SessionConst.LOGIN_USER_ID) Long userId) {
    return ProjectDetail.from(projectService.getProject(userId, projectId));
  }
}
