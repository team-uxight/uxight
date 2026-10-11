package com.uxight.api.web.project;

import com.uxight.api.domain.project.ProjectCreateRequest;
import com.uxight.api.domain.project.ProjectService;
import com.uxight.api.domain.project.ProjectUpdateRequest;
import com.uxight.api.web.common.AuthConst;
import jakarta.validation.Valid;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.bind.annotation.RequestAttribute;

@RestController
@RequestMapping("/api/projects")
public class ProjectController {

  private final ProjectService projectService;

  @Autowired
  public ProjectController(ProjectService projectService) {
    this.projectService = projectService;
  }

  /** 대시보드 — 본인 프로젝트 목록. 없으면 빈 배열. */
  @GetMapping
  public ProjectListResponse projects(@RequestAttribute(AuthConst.LOGIN_USER_ID) Long userId) {
    return new ProjectListResponse(projectService.getProjectsByUser(userId).stream()
        .map(ProjectSummary::from)
        .toList());
  }

  /** 요청한 리서처를 소유자로 저장한다. 허용 도메인은 여기서 프로젝트에 고정되고, 실험 요청 때마다 받지 않는다. */
  @PostMapping
  @ResponseStatus(HttpStatus.CREATED)
  public ProjectCreateResponse createProject(@Valid @RequestBody ProjectCreateRequest request,
      @RequestAttribute(AuthConst.LOGIN_USER_ID) Long userId) {
    return new ProjectCreateResponse(projectService.createProject(userId, request));
  }

  /** 보낸 항목만 바꾼다. 남의 프로젝트는 없는 것과 같다 (404 PRJ-ERR-001). */
  @PatchMapping("/{projectId}")
  public ProjectDetail updateProject(@PathVariable Long projectId, @Valid @RequestBody ProjectUpdateRequest request,
      @RequestAttribute(AuthConst.LOGIN_USER_ID) Long userId) {
    return ProjectDetail.from(projectService.updateProject(userId, projectId, request));
  }

  /** 삭제 표시만 한다. 남의 · 이미 삭제한 프로젝트는 404, 진행 중인 실험이 있으면 409 EXP-ERR-004. */
  @DeleteMapping("/{projectId}")
  @ResponseStatus(HttpStatus.NO_CONTENT)
  public void deleteProject(@PathVariable Long projectId, @RequestAttribute(AuthConst.LOGIN_USER_ID) Long userId) {
    projectService.deleteProject(userId, projectId);
  }

  @GetMapping("/{projectId}")
  public ProjectDetail project(@PathVariable Long projectId, @RequestAttribute(AuthConst.LOGIN_USER_ID) Long userId) {
    return ProjectDetail.from(projectService.getProject(userId, projectId));
  }
}
