package com.uxight.api.domain.run;

import com.uxight.api.common.ApiException;
import com.uxight.api.common.ErrorCode;
import com.uxight.api.domain.persona.Persona;
import com.uxight.api.domain.persona.PersonaRepository;
import com.uxight.api.domain.policy.PolicyService;
import com.uxight.api.domain.project.Project;
import com.uxight.api.domain.project.ProjectRepository;
import com.uxight.api.domain.task.SuccessRuleClient;
import com.uxight.api.domain.task.Task;
import com.uxight.api.domain.task.TaskService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.support.TransactionTemplate;

import java.time.DayOfWeek;
import java.time.Duration;
import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.time.ZoneId;
import java.time.temporal.TemporalAdjusters;
import java.util.List;
import java.util.Map;
import java.util.Set;

@Service
@Slf4j
public class RunService {

  private static final Set<String> EXPERIMENT_STATES = Set.of("in_progress", "awaiting_approval", "completed", "stopped");
  private static final Set<String> CANCELLABLE_STATES = Set.of("in_progress", "awaiting_approval");
  private static final ZoneId WEEK_ZONE = ZoneId.of("Asia/Seoul");   // 이번 주 계산 기준 — 서비스 사용자 시간대

  private final ProjectRepository projectRepository;
  private final PersonaRepository personaRepository;
  private final PolicyService policyService;
  private final TaskService taskService;
  private final RunRepository runRepository;
  private final ExperimentQueryRepository experimentQueryRepository;
  private final SuccessRuleClient successRuleClient;
  private final AgentClient agentClient;
  private final TransactionTemplate transactionTemplate;

  @Autowired
  public RunService(ProjectRepository projectRepository, PersonaRepository personaRepository,
      PolicyService policyService, TaskService taskService, RunRepository runRepository,
      ExperimentQueryRepository experimentQueryRepository, SuccessRuleClient successRuleClient, AgentClient agentClient,
      TransactionTemplate transactionTemplate) {
    this.projectRepository = projectRepository;
    this.personaRepository = personaRepository;
    this.policyService = policyService;
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
          locked.getAllowedDomains(), taskSnapshot, policyService.getGlobalPolicy().toSnapshot(), personaSnapshot));
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

  /** 본인 실험 목록 — 최근 요청 순. 마지막 회차 기준 값이며 상태는 조회할 때 계산한다. */
  public List<ExperimentSummary> getExperiments(Long userId, ExperimentFilter filter, int page, int size) {
    validateState(filter.state());
    return experimentQueryRepository.findExperiments(userId, filter, page * size, size);
  }

  /**
   * 실험의 회차 목록 — runId 순. 남의 실험, 삭제한 프로젝트의 실험, 최초 회차가 아닌 runId 는 404 EXP-ERR-001.
   * 승인 대기 여부는 실험 목록과 같은 상태 계산(state)에서 읽는다 — 승인 기능을 넣을 때 그 계산 한 곳만 바꾸면 여기도 따라온다.
   */
  public ExperimentRounds getRounds(Long userId, Long firstRunId) {
    ExperimentSummary experiment = experimentQueryRepository.findExperiment(userId, firstRunId)
        .orElseThrow(() -> new ApiException(ErrorCode.EXPERIMENT_NOT_FOUND));
    return new ExperimentRounds(experimentQueryRepository.findRounds(userId, firstRunId),
        "awaiting_approval".equals(experiment.state()));
  }

  /** getExperiments 와 같은 조건의 전체 건수(페이지 계산용). */
  public long countExperiments(Long userId, ExperimentFilter filter) {
    validateState(filter.state());
    return experimentQueryRepository.countExperiments(userId, filter);
  }

  /**
   * 상태별 건수와 총 소요 토큰. 실험 목록과 같은 상태 계산을 쓴다.
   * '이번 주'는 월요일 0시(KST)부터 — 기준(시작 요일 · 시간대)은 설계 미결이다 [확인 필요].
   */
  public ExperimentStats getStats(Long userId) {
    OffsetDateTime thisWeekFrom = LocalDate.now(WEEK_ZONE)
        .with(TemporalAdjusters.previousOrSame(DayOfWeek.MONDAY))
        .atStartOfDay(WEEK_ZONE)
        .toOffsetDateTime();
    return experimentQueryRepository.findStats(userId, thisWeekFrom);
  }

  /**
   * 실험 취소 요청 — 실험 단위로 받고 마지막 회차의 cancel_requested 만 기록한다 (design-decision 4.5).
   * 진행 중 · 승인 대기인 실험만 받는다(202). 이미 취소 요청된 실험은 상태와 관계없이 202(멱등), 그 밖은 409 EXP-ERR-006.
   * 진행 중인 회차는 Python 이 step 경계에서 확인해 멈추고 status 를 cancelled 로 기록한다 — 그때까지 프로젝트를 점유한다.
   * 승인 대기인 실험은 실행 중인 회차가 없어 기록하는 즉시 취소가 끝나고, 더 이상 다음 회차를 승인할 수 없다.
   * 승인 대기 분류는 상태 계산(state)에 승인 기능이 들어가면 따라온다 — 여기에는 승인 로직이 없다.
   */
  public void cancelExperiment(Long userId, Long firstRunId) {
    // 소유 확인 — 남의 실험 · 삭제한 프로젝트의 실험 · 최초 회차가 아닌 runId 는 404
    Long projectId = runRepository.findLastRound(firstRunId, userId)
        .map(run -> run.getProject().getId())
        .orElseThrow(() -> new ApiException(ErrorCode.EXPERIMENT_NOT_FOUND));

    transactionTemplate.executeWithoutResult(tx -> {
      // 프로젝트 행을 잠근다 — 승인 대기 중인 실험에서 취소와 다음 회차 승인이 같은 회차를 두고 경쟁하기 때문이다.
      // 잠그지 않으면 취소가 done 인 마지막 회차를 읽은 사이 승인이 다음 회차를 만들어, 취소는 이전 회차에 기록되고
      // 새 회차는 취소 요청 없이 실행된다. 잠근 뒤에 마지막 회차를 다시 읽으므로 승인이 먼저면 새 회차에 기록된다.
      projectRepository.findForUpdate(projectId, userId)
          .orElseThrow(() -> new ApiException(ErrorCode.EXPERIMENT_NOT_FOUND));   // 그사이 프로젝트가 삭제됨
      Run lastRound = runRepository.findLastRound(firstRunId, userId)
          .orElseThrow(() -> new ApiException(ErrorCode.EXPERIMENT_NOT_FOUND));
      if (lastRound.isCancelRequested()) {
        return;   // 이미 취소 요청됨 — 상태와 관계없이 202 (멱등)
      }
      // 실험 모니터링과 같은 상태 계산으로 판정한다. 완료됨 · (취소 요청 없이) 실패한 실험은 취소할 수 없다.
      String state = experimentQueryRepository.findExperiment(userId, firstRunId)
          .map(ExperimentSummary::state)
          .orElseThrow(() -> new ApiException(ErrorCode.EXPERIMENT_NOT_FOUND));
      if (!CANCELLABLE_STATES.contains(state)) {
        throw new ApiException(ErrorCode.NOT_CANCELLABLE);
      }
      // status 는 바꾸지 않는다 — 실제 중단 시점을 아는 AI 모듈이 cancelled 로 기록한다.
      // 판정 뒤 회차가 done 으로 끝났어도 기록한다 — 그 실험의 종료 유형은 취소다.
      runRepository.requestCancel(lastRound.getId());
    });
  }

  private void validateState(String state) {
    if (state != null && !EXPERIMENT_STATES.contains(state)) {
      throw ApiException.invalidField("state", "in_progress, awaiting_approval, completed, stopped 중 하나여야 합니다");
    }
  }
}
