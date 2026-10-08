package com.uxight.api.domain.project;

import java.util.List;
import java.util.Optional;

public interface ProjectRepository {

  /** 본인 소유일 때만 찾는다 — 남의 프로젝트는 없는 것과 같다 (403 대신 404). */
  Optional<Project> findByIdAndUserId(Long projectId, Long userId);

  List<Project> findByUserId(Long userId);

  Long save(Project project);
}
