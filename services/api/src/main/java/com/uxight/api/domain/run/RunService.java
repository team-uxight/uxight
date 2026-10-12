package com.uxight.api.domain.run;

import com.uxight.api.common.ApiException;
import com.uxight.api.common.ErrorCode;
import com.uxight.api.domain.persona.Persona;
import com.uxight.api.domain.persona.PersonaRepository;
import com.uxight.api.domain.policy.PolicyRepository;
import com.uxight.api.domain.project.Project;
import com.uxight.api.domain.project.ProjectRepository;
import com.uxight.api.domain.task.SuccessRuleClient;
import com.uxight.api.domain.task.Task;
import com.uxight.api.domain.task.TaskService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.support.TransactionTemplate;

import java.time.Duration;
import java.util.List;
import java.util.Map;
import java.util.Set;

@Service
@Slf4j
public class RunService {

  private static final Set<String> EXPERIMENT_STATES = Set.of("in_progress", "awaiting_approval", "completed", "stopped");

  private final ProjectRepository projectRepository;
  private final PersonaRepository personaRepository;
  private final PolicyRepository policyRepository;
  private final TaskService taskService;
  private final RunRepository runRepository;
  private final ExperimentQueryRepository experimentQueryRepository;
  private final SuccessRuleClient successRuleClient;
  private final AgentClient agentClient;
  private final TransactionTemplate transactionTemplate;

  @Autowired
  public RunService(ProjectRepository projectRepository, PersonaRepository personaRepository,
      PolicyRepository policyRepository, TaskService taskService, RunRepository runRepository,
      ExperimentQueryRepository experimentQueryRepository, SuccessRuleClient successRuleClient, AgentClient agentClient,
      TransactionTemplate transactionTemplate) {
    this.projectRepository = projectRepository;
    this.personaRepository = personaRepository;
    this.policyRepository = policyRepository;
    this.taskService = taskService;
    this.runRepository = runRepository;
    this.experimentQueryRepository = experimentQueryRepository;
    this.successRuleClient = successRuleClient;
    this.agentClient = agentClient;
    this.transactionTemplate = transactionTemplate;
  }

  /**
   * 실험 요청 — Task 와 최초 회차를 만들고 AI 모듈에 실행을 요청한다. 최초 회차의 runId(= firstRunId)를 돌려준다 (design-decision 5.3).
   * <ol>
   *   <li>잠금 없이 확인: 프로젝트 · Persona · 진행 중인 실험. 어차피 거절될 요청으로 LLM 을 부르지 않기 위해서다</li>
   *   <li>성공 기준 생성 Agent 호출 — 트랜잭션 밖. LLM 을 기다리는 동안 DB 커넥션과 잠금을 붙잡지 않는다</li>
   *   <li>트랜잭션: 프로젝트 행 잠금 → 진행 중인 실험 재확인 → Task · 최초 회차(queued) 저장 → 커밋</li>
   *   <li>POST /runs — 커밋 뒤, 트랜잭션 밖. 결과는 dispatch_state 에만 기록한다</li>
   * </ol>
   * TODO: 테스트 계정 수 확인(409 EXP-ERR-005)과 배정(assigned_run_id)은 test_accounts 도입 때 1 · 3단계에 넣는다.
   */
  public Long createExperiment(Long userId, Long projectId, ExperimentCreateRequest request) {
    RunMode mode = RunMode.valueOf(request.mode());   // diagnose · improve · loop 는 Bean Validation 이 확인했다
    if (mode == RunMode.loop && request.loopMax() == null) {
      throw ApiException.invalidField("loopMax", "mode가 loop이면 필수입니다");
    }
    List<Long> personaIds = request.personaIds();
    if (personaIds.stream().distinct().count() != personaIds.size()) {   // 명세 uniqueItems
      throw ApiException.invalidField("personaIds", "같은 Persona를 두 번 선택할 수 없습니다");
    }

    // 1. 잠금 없이 확인
    Project project = projectRepository.findByIdAndUserIdAndDeletedAtIsNull(projectId, userId)
        .orElseThrow(() -> new ApiException(ErrorCode.PROJECT_NOT_FOUND));
    List<Persona> personas = personaRepository.findUsableByIds(userId, personaIds);
    if (personas.size() != personaIds.size()) {
      throw new ApiException(ErrorCode.PERSONA_NOT_FOUND);
    }
    if (runRepository.existsInProgressByProjectId(projectId)) {
      throw new ApiException(ErrorCode.EXPERIMENT_IN_PROGRESS);
    }

    // 2. 성공 기준 생성 — 트랜잭션 밖. 실패 502 · 시간 초과 504 는 클라이언트가 ApiException 으로 던진다
    String successRule = successRuleClient.createSuccessRule(project.getTargetUrl(), request.goal(),
        request.successUrl());

    // 3. 커밋이 끝난 뒤에 dispatch 한다. Python 은 'status=queued 일 때만 accepted' UPDATE 로 수락하므로
    //    커밋 전에 부르면 행을 보지 못한다.
    Long runId = transactionTemplate.execute(tx -> {
      // LLM 을 기다리는 동안 다른 요청이 실험을 만들었거나 프로젝트를 지웠을 수 있다 — 잠근 뒤 다시 확인한다.
      // 프로젝트 삭제도 같은 행을 잠그므로 삭제와 실험 요청은 차례로 처리된다.
      Project locked = projectRepository.findForUpdate(projectId, userId)
          .orElseThrow(() -> new ApiException(ErrorCode.PROJECT_NOT_FOUND));
      if (runRepository.existsInProgressByProjectId(projectId)) {
        throw new ApiException(ErrorCode.EXPERIMENT_IN_PROGRESS);
      }

      Task task = taskService.createTask(locked, request.goal(), successRule, request.successUrl());

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

      // 스냅샷 — 프로젝트 · 정책이 나중에 바뀌거나 Persona 가 삭제되어도 지난 회차를 재현할 수 있게 실험 요청 시점의 값을 담는다
      Run run = runRepository.save(Run.firstRound(locked, task, mode, request.loopMax(), locked.getTargetUrl(),
          locked.getAllowedDomains(), taskSnapshot, policyRepository.getGlobal().toSnapshot(), personaSnapshot));
      run.markAsFirstRound();   // 커밋 때 first_run_id 를 자기 run_id 로 UPDATE
      return run.getId();
    });

    // 4. POST /runs — Python 응답을 기다리지 않고 돌아간다. 닿지 않았으면 redispatchStaleQueuedRuns 가 다시 보낸다.
    //    status 는 바꾸지 않는다 — 응답을 못 받았어도 Python 이 이미 접수했을 수 있다.
    dispatch(runId);
    return runId;
  }

  /**
   * queued 로 staleAfter 넘게 남은 회차에 POST /runs 를 다시 보낸다 (design-decision 4.6). 다시 보낸 회차 수를 돌려준다.
   * AI 모듈은 살아 있는데 요청이 닿지 않았거나, Spring 이 커밋 직후 죽어 호출하지 못한 회차가 프로젝트를 계속 점유하지 않게 한다.
   * POST /runs 는 멱등이라 이미 받은 회차에 다시 보내도 200 만 돌아온다. 취소 요청된 회차도 보낸다 — AI 모듈이 접수해야 취소가 끝난다.
   */
  public int redispatchStaleQueuedRuns(Duration staleAfter) {
    List<Long> runIds = runRepository.findQueuedRunIdsOlderThan(staleAfter.toSeconds());
    if (!runIds.isEmpty()) {
      log.info("redispatch {} queued run(s) older than {}: {}", runIds.size(), staleAfter, runIds);
    }
    runIds.forEach(this::dispatch);
    return runIds.size();
  }

  // fire-and-forget: 응답을 기다리지 않는다. 결과는 비동기 스레드에서 dispatch_state 에만 기록한다(200 이면 그대로 둔다).
  private void dispatch(Long runId) {
    agentClient.dispatch(runId)
        .thenAccept(dispatchState -> dispatchState.ifPresent(state -> runRepository.updateDispatchState(runId, state)));
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
