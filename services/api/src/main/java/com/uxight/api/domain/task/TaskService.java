package com.uxight.api.domain.task;

import com.uxight.api.domain.project.Project;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class TaskService {

  private final TaskRepository taskRepository;

  @Autowired
  public TaskService(TaskRepository taskRepository) {
    this.taskRepository = taskRepository;
  }

  /**
   * 실험 요청의 Task 를 저장한다. 성공 기준(successRule)은 성공 기준 생성 Agent 가 만든 값이다.
   * 실험 요청 트랜잭션(프로젝트 행 잠금 안)에 참여한다 — Task 와 최초 회차는 함께 커밋되거나 함께 롤백된다.
   */
  @Transactional
  public Task createTask(Project project, String goal, String successRule, String successUrl) {
    return taskRepository.save(Task.create(project, goal, successRule, successUrl));
  }
}
