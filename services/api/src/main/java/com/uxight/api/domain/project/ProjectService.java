package com.uxight.api.domain.project;

import com.uxight.api.common.ApiException;
import com.uxight.api.common.ErrorCode;
import com.uxight.api.domain.user.UserRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

@Service
public class ProjectService {

  private final ProjectRepository projectRepository;
  private final UserRepository userRepository;

  @Autowired
  public ProjectService(ProjectRepository projectRepository, UserRepository userRepository) {
    this.projectRepository = projectRepository;
    this.userRepository = userRepository;
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
    // Optional.empty()(null 을 보냄)는 Bean Validation 이 description 외에는 막았다.
    // 호스트를 읽을 수 없어 400 이 날 수 있는 두 항목을 먼저 바꾼다 (실패하면 트랜잭션이 롤백되어 아무것도 바뀌지 않는다).
    // 시작 URL 을 허용 도메인보다 먼저 바꿔야 둘을 함께 보냈을 때 새 시작 URL 의 호스트가 들어간다.
    if (request.getTargetUrl() != null) {
      project.changeTargetUrl(request.getTargetUrl().orElseThrow());
    }
    if (request.getAllowedDomains() != null) {
      project.changeAllowedDomains(request.getAllowedDomains().orElseThrow());
    }
    if (request.getTitle() != null) {
      project.changeTitle(request.getTitle().orElseThrow());
    }
    if (request.getDescription() != null) {
      project.changeDescription(request.getDescription().orElse(null));
    }
    return project;
  }

  @Transactional(readOnly = true)
  public Project getProject(Long userId, Long projectId) {
    return projectRepository.findByIdAndUserId(projectId, userId)
        .orElseThrow(() -> new ApiException(ErrorCode.PROJECT_NOT_FOUND));
  }

  @Transactional(readOnly = true)
  public List<Project> getProjectsByUser(Long userId) {
    return projectRepository.findByUserIdOrderByIdDesc(userId);
  }
}
