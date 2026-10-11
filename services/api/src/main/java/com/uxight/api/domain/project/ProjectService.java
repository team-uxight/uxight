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
