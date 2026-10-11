package com.uxight.api.domain.project;

import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

/** save 는 JpaRepository 가 제공한다. 메서드 이름의 UserId 는 user.id(projects.user_id)로 풀린다. */
public interface ProjectRepository extends JpaRepository<Project, Long> {

  /** 본인 소유일 때만 찾는다 — 남의 프로젝트는 없는 것과 같다 (403 대신 404). */
  Optional<Project> findByIdAndUserId(Long projectId, Long userId);

  /** 최근 생성 순. id 는 생성 순으로 커지므로 같은 초에 만든 프로젝트끼리도 순서가 정해진다. */
  List<Project> findByUserIdOrderByIdDesc(Long userId);
}
