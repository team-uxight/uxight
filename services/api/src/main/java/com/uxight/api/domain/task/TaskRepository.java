package com.uxight.api.domain.task;

import java.util.Optional;

public interface TaskRepository {

  Optional<Task> findById(Long taskId);

  Long save(Task task);
}
