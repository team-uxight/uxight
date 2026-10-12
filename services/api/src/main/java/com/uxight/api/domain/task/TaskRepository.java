package com.uxight.api.domain.task;

import org.springframework.data.jpa.repository.JpaRepository;

/** save 는 JpaRepository 가 제공한다. */
public interface TaskRepository extends JpaRepository<Task, Long> {
}
