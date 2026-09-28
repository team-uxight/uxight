package com.uxight.api.domain.project;

import java.util.List;
import java.util.Optional;

public interface ProjectRepository {

  Optional<Project> findById(Long projectId);

  List<Project> findByUserId(Long userId);

  Long save(Project project);
}
