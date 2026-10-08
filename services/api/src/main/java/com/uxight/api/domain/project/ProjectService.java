package com.uxight.api.domain.project;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.uxight.api.common.ApiException;
import com.uxight.api.common.ErrorCode;
import org.springframework.stereotype.Service;

import java.io.UncheckedIOException;
import java.util.List;

@Service
public class ProjectService {

  private final ProjectRepository projectRepository;
  private final ObjectMapper objectMapper;

  public ProjectService(ProjectRepository projectRepository, ObjectMapper objectMapper) {
    this.projectRepository = projectRepository;
    this.objectMapper = objectMapper;
  }

  public Long createProject(Long userId, ProjectCreateRequest request) {
    Project project = Project.newProject(userId, request.title(), request.targetUrl(),
        request.description(), writeJson(request.allowedDomains()));
    return projectRepository.save(project);
  }

  public Project getProject(Long userId, Long projectId) {
    return projectRepository.findByIdAndUserId(projectId, userId)
        .orElseThrow(() -> new ApiException(ErrorCode.PROJECT_NOT_FOUND));
  }

  public List<Project> getProjectsByUser(Long userId) {
    return projectRepository.findByUserId(userId);
  }

  private String writeJson(Object value) {
    try {
      return objectMapper.writeValueAsString(value);
    } catch (JsonProcessingException e) {
      throw new UncheckedIOException(e);
    }
  }
}
