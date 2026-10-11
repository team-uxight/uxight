package com.uxight.api.domain.project;

import jakarta.persistence.LockModeType;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Lock;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.List;
import java.util.Optional;

/**
 * save 는 JpaRepository 가 제공한다. 메서드 이름의 UserId 는 user.id(projects.user_id)로 풀린다.
 * 삭제 표시된 프로젝트(deleted_at 있음)는 없는 것과 같다 — 조회 메서드는 모두 DeletedAtIsNull 조건을 단다.
 */
public interface ProjectRepository extends JpaRepository<Project, Long> {

  /** 본인 소유일 때만 찾는다 — 남의 프로젝트는 없는 것과 같다 (403 대신 404). */
  Optional<Project> findByIdAndUserIdAndDeletedAtIsNull(Long projectId, Long userId);

  /** 최근 생성 순. id 는 생성 순으로 커지므로 같은 초에 만든 프로젝트끼리도 순서가 정해진다. */
  List<Project> findByUserIdAndDeletedAtIsNullOrderByIdDesc(Long userId);

  /**
   * findByIdAndUserIdAndDeletedAtIsNull 과 같지만 행을 잠근다(SELECT ... FOR UPDATE). 트랜잭션 안에서만 쓴다.
   * 같은 프로젝트의 삭제 · 실험 요청이 이 잠금에서 차례로 처리된다 (design-decision 5.2).
   */
  @Lock(LockModeType.PESSIMISTIC_WRITE)
  @Query("SELECT p FROM Project p WHERE p.id = :projectId AND p.user.id = :userId AND p.deletedAt IS NULL")
  Optional<Project> findForUpdate(@Param("projectId") Long projectId, @Param("userId") Long userId);
}
