package com.uxight.api.domain.run;

import com.uxight.api.common.ApiException;
import com.uxight.api.common.ErrorCode;
import com.uxight.api.domain.persona.Persona;
import com.uxight.api.domain.persona.PersonaRepository;
import com.uxight.api.domain.project.Project;
import com.uxight.api.domain.project.ProjectRepository;
import com.uxight.api.domain.task.Task;
import com.uxight.api.domain.task.TaskRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.support.TransactionTemplate;

import java.util.List;
import java.util.Map;
import java.util.Set;

@Service
public class RunService {

  // Walking Skeleton: 성공 기준 생성 Agent(내부 API 0, POST /success-rules) 연동 전까지 고정값을 넣는다.
  private static final String MOCK_SUCCESS_RULE = "mock success rule";
  // Walking Skeleton: 전역 정책(policies)을 스냅샷으로 복사하기 전까지 고정값이다.
  private static final Map<String, Object> MOCK_POLICY_SNAPSHOT = Map.of("max_steps", 3);

  private static final Set<String> EXPERIMENT_STATES = Set.of("in_progress", "awaiting_approval", "completed", "stopped");

  private final ProjectRepository projectRepository;
  private final PersonaRepository personaRepository;
  private final TaskRepository taskRepository;
  private final RunRepository runRepository;
  private final ExperimentQueryRepository experimentQueryRepository;
  private final AgentClient agentClient;
  private final TransactionTemplate transactionTemplate;

  @Autowired
  public RunService(ProjectRepository projectRepository, PersonaRepository personaRepository,
      TaskRepository taskRepository, RunRepository runRepository, ExperimentQueryRepository experimentQueryRepository,
      AgentClient agentClient, TransactionTemplate transactionTemplate) {
    this.projectRepository = projectRepository;
    this.personaRepository = personaRepository;
    this.taskRepository = taskRepository;
    this.runRepository = runRepository;
    this.experimentQueryRepository = experimentQueryRepository;
    this.agentClient = agentClient;
    this.transactionTemplate = transactionTemplate;
  }

  /** 실험 요청 — Task 생성과 최초 회차 생성. 최초 회차의 runId(= firstRunId)를 돌려준다. */
  public Long createExperiment(Long userId, Long projectId, ExperimentCreateRequest request) {
    RunMode mode = RunMode.valueOf(request.mode());   // diagnose · improve · loop 는 Bean Validation 이 확인했다
    if (mode == RunMode.loop && request.loopMax() == null) {
      throw ApiException.invalidField("loopMax", "mode가 loop이면 필수입니다");
    }

    Project project = projectRepository.findByIdAndUserIdAndDeletedAtIsNull(projectId, userId)
        .orElseThrow(() -> new ApiException(ErrorCode.PROJECT_NOT_FOUND));
    List<Long> personaIds = request.personaIds().stream().distinct().toList();
    List<Persona> personas = personaRepository.findUsableByIds(userId, personaIds);
    if (personas.size() != personaIds.size()) {
      throw new ApiException(ErrorCode.PERSONA_NOT_FOUND);
    }

    // 커밋이 끝난 뒤에 dispatch 한다. Python 은 'status=queued 일 때만 accepted' UPDATE 로 수락하므로
    // 커밋 전에 부르면 행을 보지 못한다.
    Long runId = transactionTemplate.execute(tx -> {
      Project projectRef = projectRepository.getReferenceById(projectId);
      Task task = taskRepository.save(Task.create(projectRef, request.goal(), MOCK_SUCCESS_RULE, request.successUrl()));

      Map<String, Object> taskSnapshot = Map.of(
          "task_id", task.getId(),
          "goal", task.getGoal(),
          "success_rule", task.getSuccessRule(),
          "success_url", task.getSuccessUrl(),
          "is_one_shot", task.isOneShot()
      );
      List<Map<String, Object>> personaSnapshot = personas.stream()
          .map(persona -> Map.<String, Object>of(
              "persona_id", persona.getId(),
              "name", persona.getName(),
              "profile", persona.getProfile()
          ))
          .toList();

      Run run = runRepository.save(Run.firstRound(projectRef, task, mode, request.loopMax(), project.getTargetUrl(),
          project.getAllowedDomains(), taskSnapshot, MOCK_POLICY_SNAPSHOT, personaSnapshot));
      run.markAsFirstRound();   // 커밋 때 first_run_id 를 자기 run_id 로 UPDATE
      return run.getId();
    });

    // fire-and-forget: Python 응답을 기다리지 않고 돌아간다. dispatch_state 는 응답이 오면 비동기 스레드에서 기록된다.
    agentClient.dispatch(runId)
        .thenAccept(dispatchState -> dispatchState.ifPresent(state -> runRepository.updateDispatchState(runId, state)));
    return runId;
  }

  public List<ExperimentSummary> getExperiments(Long userId, String state, int page, int size) {
    validateState(state);
    return experimentQueryRepository.findExperiments(userId, state, page * size, size);
  }

  public long countExperiments(Long userId, String state) {
    validateState(state);
    return experimentQueryRepository.countExperiments(userId, state);
  }

  /**
   * 실험 취소 요청 — 마지막 회차의 cancel_requested 만 기록한다. 실제 중단과 status 변경은 Python 이 한다.
   * 이미 취소 요청된 실험은 상태와 관계없이 성공(멱등).
   * TODO: 승인 대기 중인 실험의 취소는 improvements · approvals 도입 때 (design-decision 4.5).
   */
  public void cancelExperiment(Long userId, Long firstRunId) {
    Run lastRound = runRepository.findLastRound(firstRunId, userId)
        .orElseThrow(() -> new ApiException(ErrorCode.EXPERIMENT_NOT_FOUND));
    if (lastRound.isCancelRequested()) {
      return;
    }
    // 읽은 뒤 회차가 끝났을 수 있다 — UPDATE 의 status 조건이 최종 판정이다.
    if (!lastRound.isInProgress() || !runRepository.requestCancel(lastRound.getId())) {
      throw new ApiException(ErrorCode.NOT_CANCELLABLE);
    }
  }

  private void validateState(String state) {
    if (state != null && !EXPERIMENT_STATES.contains(state)) {
      throw new ApiException(ErrorCode.BAD_REQUEST);
    }
  }
}
