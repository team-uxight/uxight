package com.uxight.api.domain.run;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.uxight.api.common.ApiException;
import com.uxight.api.common.ErrorCode;
import com.uxight.api.domain.persona.Persona;
import com.uxight.api.domain.persona.PersonaRepository;
import com.uxight.api.domain.project.Project;
import com.uxight.api.domain.project.ProjectRepository;
import com.uxight.api.domain.task.Task;
import com.uxight.api.domain.task.TaskRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.support.TransactionTemplate;

import java.io.UncheckedIOException;
import java.util.List;
import java.util.Map;
import java.util.Set;

@Service
public class RunService {

  // Walking Skeleton: 성공 기준 생성 Agent(내부 API 0, POST /success-rules) 연동 전까지 고정값을 넣는다.
  private static final String MOCK_SUCCESS_RULE = "mock success rule";
  // Walking Skeleton: policies 테이블 도입 전까지 정책 스냅샷은 고정값이다.
  private static final Map<String, Object> MOCK_POLICY_SNAPSHOT = Map.of("max_steps", 3);

  private static final Set<String> EXPERIMENT_STATES = Set.of("in_progress", "awaiting_approval", "completed", "stopped");
  private static final Set<String> IN_PROGRESS_STATUSES = Set.of("queued", "accepted", "running");

  private final ProjectRepository projectRepository;
  private final PersonaRepository personaRepository;
  private final TaskRepository taskRepository;
  private final RunRepository runRepository;
  private final AgentClient agentClient;
  private final ObjectMapper objectMapper;
  private final TransactionTemplate transactionTemplate;

  public RunService(ProjectRepository projectRepository, PersonaRepository personaRepository,
      TaskRepository taskRepository, RunRepository runRepository, AgentClient agentClient,
      ObjectMapper objectMapper, TransactionTemplate transactionTemplate) {
    this.projectRepository = projectRepository;
    this.personaRepository = personaRepository;
    this.taskRepository = taskRepository;
    this.runRepository = runRepository;
    this.agentClient = agentClient;
    this.objectMapper = objectMapper;
    this.transactionTemplate = transactionTemplate;
  }

  /** 실험 요청 — Task 생성과 최초 회차 생성. 최초 회차의 runId(= firstRunId)를 돌려준다. */
  public Long createExperiment(Long userId, Long projectId, ExperimentCreateRequest request) {
    boolean loop = "loop".equals(request.mode());
    if (loop && request.loopMax() == null) {
      throw ApiException.invalidField("loopMax", "mode가 loop이면 필수입니다");
    }

    Project project = projectRepository.findByIdAndUserId(projectId, userId)
        .orElseThrow(() -> new ApiException(ErrorCode.PROJECT_NOT_FOUND));
    List<Long> personaIds = request.personaIds().stream().distinct().toList();
    List<Persona> personas = personaRepository.findUsableByIds(userId, personaIds);
    if (personas.size() != personaIds.size()) {
      throw new ApiException(ErrorCode.PERSONA_NOT_FOUND);
    }

    // 커밋이 끝난 뒤에 dispatch 한다. Python 은 'status=queued 일 때만 accepted' UPDATE 로 수락하므로
    // 커밋 전에 부르면 행을 보지 못한다.
    Long runId = transactionTemplate.execute(tx -> {
      Long taskId = taskRepository.save(
          Task.newTask(projectId, request.goal(), MOCK_SUCCESS_RULE, request.successUrl()));

      Map<String, Object> taskSnapshot = Map.of(
          "task_id", taskId,
          "goal", request.goal(),
          "success_rule", MOCK_SUCCESS_RULE,
          "success_url", request.successUrl(),
          "is_one_shot", false
      );
      List<Map<String, Object>> personaSnapshot = personas.stream()
          .map(persona -> Map.<String, Object>of(
              "persona_id", persona.personaId(),
              "name", persona.name(),
              "profile", readJson(persona.profile())
          ))
          .toList();

      Long newRunId = runRepository.save(Run.newFirstRound(projectId, taskId, request.mode(),
          loop ? request.loopMax() : null, project.targetUrl(), project.allowedDomains(),
          writeJson(taskSnapshot), writeJson(MOCK_POLICY_SNAPSHOT), writeJson(personaSnapshot)));
      runRepository.updateFirstRunId(newRunId, newRunId);   // 최초 회차는 자기 자신이 실험 식별자
      return newRunId;
    });

    // fire-and-forget: Python 응답을 기다리지 않고 돌아간다. dispatch_state 는 응답이 오면 비동기 스레드에서 기록된다.
    agentClient.dispatch(runId)
        .thenAccept(dispatchState -> dispatchState.ifPresent(state -> runRepository.updateDispatchState(runId, state)));
    return runId;
  }

  public List<ExperimentSummary> getExperiments(Long userId, String state, int page, int size) {
    validateState(state);
    return runRepository.findExperiments(userId, state, page * size, size);
  }

  public long countExperiments(Long userId, String state) {
    validateState(state);
    return runRepository.countExperiments(userId, state);
  }

  /**
   * 실험 취소 요청 — 마지막 회차의 cancel_requested 만 기록한다. 실제 중단과 status 변경은 Python 이 한다.
   * 이미 취소 요청된 실험은 상태와 관계없이 성공(멱등).
   * TODO: 승인 대기 중인 실험의 취소는 improvements · approvals 도입 때 (design-decision 4.5).
   */
  public void cancelExperiment(Long userId, Long firstRunId) {
    Run lastRound = runRepository.findLastRound(firstRunId, userId)
        .orElseThrow(() -> new ApiException(ErrorCode.EXPERIMENT_NOT_FOUND));
    if (lastRound.cancelRequested()) {
      return;
    }
    // 읽은 뒤 회차가 끝났을 수 있다 — UPDATE 의 status 조건이 최종 판정이다.
    if (!IN_PROGRESS_STATUSES.contains(lastRound.status()) || !runRepository.requestCancel(lastRound.runId())) {
      throw new ApiException(ErrorCode.NOT_CANCELLABLE);
    }
  }

  private void validateState(String state) {
    if (state != null && !EXPERIMENT_STATES.contains(state)) {
      throw new ApiException(ErrorCode.BAD_REQUEST);
    }
  }

  // Jackson 2 의 checked 예외를 unchecked 로 감싼다 — GlobalExceptionHandler 에서 500 이 된다.
  private Object readJson(String json) {
    try {
      return objectMapper.readValue(json, Object.class);
    } catch (JsonProcessingException e) {
      throw new UncheckedIOException(e);
    }
  }

  private String writeJson(Object value) {
    try {
      return objectMapper.writeValueAsString(value);
    } catch (JsonProcessingException e) {
      throw new UncheckedIOException(e);
    }
  }
}
