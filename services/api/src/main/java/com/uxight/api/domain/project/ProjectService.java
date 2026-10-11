package com.uxight.api.domain.project;

import com.uxight.api.common.ApiException;
import com.uxight.api.common.ErrorCode;
import com.uxight.api.domain.run.RunRepository;
import com.uxight.api.domain.user.UserRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

@Service
public class ProjectService {

  private final ProjectRepository projectRepository;
  private final UserRepository userRepository;
  private final RunRepository runRepository;

  @Autowired
  public ProjectService(ProjectRepository projectRepository, UserRepository userRepository,
      RunRepository runRepository) {
    this.projectRepository = projectRepository;
    this.userRepository = userRepository;
    this.runRepository = runRepository;
  }

  @Transactional
  public Long createProject(Long userId, ProjectCreateRequest request) {
    // 소유자는 user_id FK 만 쓰면 된다 — 사용자 행은 읽지 않는다 (LoginCheckInterceptor 가 이미 확인했다).
    Project project = Project.create(userRepository.getReferenceById(userId), request.title(), request.targetUrl(),
        request.description(), request.allowedDomains());
    return projectRepository.save(project).getId();
  }

  /** 보낸 항목만 바꾼다. 변경은 커밋 때 dirty checking 으로 UPDATE 된다. 아무것도 보내지 않으면 그대로 돌려준다. */
  @Transactional
  public Project updateProject(Long userId, Long projectId, ProjectUpdateRequest request) {
    Project project = getProject(userId, projectId);
    // 호스트를 읽을 수 없어 400 이 날 수 있는 두 항목을 먼저 바꾼다 (실패하면 트랜잭션이 롤백되어 아무것도 바뀌지 않는다).
    // 시작 URL 을 허용 도메인보다 먼저 바꿔야 둘을 함께 보냈을 때 새 시작 URL 의 호스트가 들어간다.
    if (request.targetUrl() != null) {
      project.changeTargetUrl(request.targetUrl());
    }
    if (request.allowedDomains() != null) {
      project.changeAllowedDomains(request.allowedDomains());
    }
    if (request.title() != null) {
      project.changeTitle(request.title());
    }
    if (request.description() != null) {
      project.changeDescription(request.description());
    }
    return project;
  }

  /**
   * 삭제 표시만 한다. 진행 중인 실험이 있으면 409 — 실행 중인 회차의 프로젝트가 사라지면 안 된다.
   * 프로젝트 행을 먼저 잠그므로 같은 프로젝트의 실험 요청과 차례로 처리된다. 잠근 뒤에 읽으므로 확인 직후 새 실험이
   * 생기는 경우가 없다 (실험 요청도 같은 행을 잠근다는 전제, design-decision 5.2 · 5.3).
   */
  @Transactional
  public void deleteProject(Long userId, Long projectId) {
    Project project = projectRepository.findForUpdate(projectId, userId)
        .orElseThrow(() -> new ApiException(ErrorCode.PROJECT_NOT_FOUND));
    if (runRepository.existsInProgressByProjectId(projectId)) {
      throw new ApiException(ErrorCode.EXPERIMENT_IN_PROGRESS);
    }
    project.delete();
  }

  @Transactional(readOnly = true)
  public Project getProject(Long userId, Long projectId) {
    return projectRepository.findByIdAndUserIdAndDeletedAtIsNull(projectId, userId)
        .orElseThrow(() -> new ApiException(ErrorCode.PROJECT_NOT_FOUND));
  }

  @Transactional(readOnly = true)
  public List<Project> getProjectsByUser(Long userId) {
    return projectRepository.findByUserIdAndDeletedAtIsNullOrderByIdDesc(userId);
  }
}
