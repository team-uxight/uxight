package com.uxight.api.domain.improvement;

import com.uxight.api.common.ApiException;
import com.uxight.api.common.ErrorCode;
import com.uxight.api.domain.audit.AuditLog;
import com.uxight.api.domain.audit.AuditLogRepository;
import com.uxight.api.domain.finding.FindingList;
import com.uxight.api.domain.finding.FindingRepository;
import com.uxight.api.domain.project.ProjectRepository;
import com.uxight.api.domain.run.ExperimentQueryRepository;
import com.uxight.api.domain.run.Run;
import com.uxight.api.domain.run.RunRepository;
import com.uxight.api.domain.run.RunService;
import com.uxight.api.domain.run.RunStatus;
import com.uxight.api.domain.user.UserRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.transaction.support.TransactionTemplate;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

/**
 * 개선안 목록 · 상세와 다음 회차 승인 · 반려 (design-decision 2.2 · 2.3 · 5.4).
 * 조회는 본인 프로젝트(삭제 제외)의 done 회차만 — 개선안은 회차가 done 으로 기록되기 전에 저장되고 그 뒤 실패 · 취소되어도 남는다.
 */
@Service
public class ImprovementService {

  static final String AUDIT_ACTION_APPROVE = "run.approve";
  static final String AUDIT_ACTION_REJECT = "run.reject";

  private static final String AWAITING_APPROVAL = "awaiting_approval";

  private final ImprovementRepository improvementRepository;
  private final ApprovalRepository approvalRepository;
  private final FindingRepository findingRepository;
  private final RunRepository runRepository;
  private final ProjectRepository projectRepository;
  private final UserRepository userRepository;
  private final AuditLogRepository auditLogRepository;
  private final ExperimentQueryRepository experimentQueryRepository;
  private final RunService runService;
  private final TransactionTemplate transactionTemplate;

  @Autowired
  public ImprovementService(ImprovementRepository improvementRepository, ApprovalRepository approvalRepository,
      FindingRepository findingRepository, RunRepository runRepository, ProjectRepository projectRepository,
      UserRepository userRepository, AuditLogRepository auditLogRepository,
      ExperimentQueryRepository experimentQueryRepository, RunService runService, TransactionTemplate transactionTemplate) {
    this.improvementRepository = improvementRepository;
    this.approvalRepository = approvalRepository;
    this.findingRepository = findingRepository;
    this.runRepository = runRepository;
    this.projectRepository = projectRepository;
    this.userRepository = userRepository;
    this.auditLogRepository = auditLogRepository;
    this.experimentQueryRepository = experimentQueryRepository;
    this.runService = runService;
    this.transactionTemplate = transactionTemplate;
  }

  /** 회차 정보와 개선안(안 번호 순)과 각 결정. 회차가 없거나 · 남의 것 · 삭제한 프로젝트 · done 아님이면 404 EXP-ERR-002. */
  @Transactional(readOnly = true)
  public ImprovementList getImprovements(Long userId, Long runId) {
    Run run = runRepository.findByIdAndProjectUserIdAndProjectDeletedAtIsNull(runId, userId)
        .filter(found -> found.getStatus() == RunStatus.done)
        .orElseThrow(() -> new ApiException(ErrorCode.RUN_NOT_FOUND));

    Map<Long, Decision> decisions = approvalRepository.findByImprovementRunId(run.getId()).stream()
        .collect(Collectors.toMap(approval -> approval.getImprovement().getId(), Approval::getDecision));
    List<ImprovementList.Summary> improvements = improvementRepository.findByRunIdOrderByOptionNoAsc(run.getId()).stream()
        .map(i -> new ImprovementList.Summary(i.getId(), i.getOptionNo(), i.getPatchKind(), i.getFixCost(),
            decisions.get(i.getId())))
        .toList();
    ImprovementList.RoundInfo info = new ImprovementList.RoundInfo(run.getFirstRun().getId(), roundOf(run),
        run.getProject().getTitle(), run.getTask().getGoal(), awaitingApproval(userId, run));
    return new ImprovementList(info, improvements);
  }

  /** 개선안 상세. 개선안이 없거나 · 남의 것 · 삭제한 프로젝트 · 회차가 done 아님이면 404 IMP-ERR-001. */
  @Transactional(readOnly = true)
  public ImprovementDetail getImprovement(Long userId, Long improvementId) {
    Improvement improvement = improvementRepository
        .findByIdAndRunProjectUserIdAndRunProjectDeletedAtIsNull(improvementId, userId)
        .filter(found -> found.getRun().getStatus() == RunStatus.done)
        .orElseThrow(() -> new ApiException(ErrorCode.IMPROVEMENT_NOT_FOUND));
    Run run = improvement.getRun();

    List<FindingList.Summary> findings = findingRepository
        .findByRunIdAndIdInOrderByIdAsc(run.getId(), improvement.getFindingIds()).stream()
        .map(f -> new FindingList.Summary(f.getId(), f.getTaxonomy(), f.getSeverity(), f.getSummary()))
        .toList();
    ImprovementDetail.ApprovalInfo approval = approvalRepository.findByImprovementId(improvement.getId())
        .map(ImprovementDetail.ApprovalInfo::from)
        .orElse(null);
    return new ImprovementDetail(improvement.getId(), run.getId(), improvement.getOptionNo(), improvement.getPatchKind(),
        improvement.getPatch(), improvement.getRationale(), improvement.getExpectedEffect(), improvement.getFixCost(),
        findings, approval, awaitingApproval(userId, run));
  }

  /**
   * 다음 회차 승인 · 반려 (design-decision 5.4). 순서:
   * <ol>
   *   <li>회차 소유 확인 — 없거나 · 남의 것 · 삭제한 프로젝트면 404 EXP-ERR-002</li>
   *   <li>트랜잭션: 프로젝트 행 잠금(실험 요청 · 취소와 같은 잠금 — 연타 · 취소와 차례로 처리) → 이 회차의 개선안인지(404 IMP-ERR-001)
   *       → 승인 가능 조건(409 IMP-ERR-002) → 승인이면 진행 중인 실험(409 EXP-ERR-004)
   *       → 결정 · 감사 로그 저장, 승인이면 다음 회차(queued) 저장 → 커밋</li>
   *   <li>승인이면 커밋 뒤 POST /runs — 실험 요청과 같은 경로</li>
   * </ol>
   * TODO: 테스트 계정 수 확인(409 EXP-ERR-005)과 새 회차 배정은 test_accounts 도입 때 넣는다(실험 요청과 같다).
   */
  public ApprovalResult decide(Long userId, Long runId, ApprovalCreateRequest request) {
    Decision decision = Decision.valueOf(request.decision());   // approve · reject 는 Bean Validation 이 확인했다
    Long projectId = runRepository.findByIdAndProjectUserIdAndProjectDeletedAtIsNull(runId, userId)
        .map(run -> run.getProject().getId())
        .orElseThrow(() -> new ApiException(ErrorCode.RUN_NOT_FOUND));

    ApprovalResult result = transactionTemplate.execute(tx -> {
      projectRepository.findForUpdate(projectId, userId)
          .orElseThrow(() -> new ApiException(ErrorCode.RUN_NOT_FOUND));   // 그사이 프로젝트가 삭제됨
      // 잠근 뒤에 다시 읽는다 — 그사이 취소 요청이 기록됐을 수 있다
      Run run = runRepository.findByIdAndProjectUserIdAndProjectDeletedAtIsNull(runId, userId)
          .orElseThrow(() -> new ApiException(ErrorCode.RUN_NOT_FOUND));
      Improvement improvement = improvementRepository.findById(request.improvementId())
          .filter(found -> found.getRun().getId().equals(run.getId()))
          .orElseThrow(() -> new ApiException(ErrorCode.IMPROVEMENT_NOT_FOUND));

      if (!run.isNextRoundDecidable(roundOf(run))
          || approvalRepository.existsByImprovementRunIdAndDecision(run.getId(), Decision.approve)
          || approvalRepository.existsByImprovementId(improvement.getId())) {
        throw new ApiException(ErrorCode.NOT_DECIDABLE);
      }
      // 승인 대기 중인 실험은 프로젝트를 점유하지 않아, 그사이 같은 프로젝트에 다른 실험이 요청됐을 수 있다
      if (decision == Decision.approve && runRepository.existsInProgressByProjectId(projectId)) {
        throw new ApiException(ErrorCode.EXPERIMENT_IN_PROGRESS);
      }

      Approval approval = approvalRepository.save(
          Approval.decide(improvement, userRepository.getReferenceById(userId), decision, request.note()));
      Long nextRunId = decision == Decision.approve ? runRepository.save(Run.nextRound(run, improvement)).getId() : null;

      Map<String, Object> detail = new LinkedHashMap<>();
      detail.put("runId", run.getId());
      detail.put("nextRunId", nextRunId);
      detail.put("note", approval.getNote());
      auditLogRepository.save(AuditLog.byUser(userId,
          decision == Decision.approve ? AUDIT_ACTION_APPROVE : AUDIT_ACTION_REJECT, "improvement:" + improvement.getId(),
          detail));
      return new ApprovalResult(approval.getId(), nextRunId);
    });

    // 커밋이 끝난 뒤에 dispatch 한다 — Python 은 queued 인 행만 접수하므로 커밋 전에 부르면 행을 보지 못한다
    if (result.runId() != null) {
      runService.dispatch(result.runId());
    }
    return result;
  }

  // 몇 번째 회차인지 — 다음 회차는 이전 회차가 끝나고 승인된 뒤에만 생겨 run_id 순서가 회차 순서다 (design-decision 2.2)
  private int roundOf(Run run) {
    return (int) runRepository.countByFirstRunIdAndIdLessThanEqual(run.getFirstRun().getId(), run.getId());
  }

  // 회차 단위 값 — 이 회차가 실험의 마지막 회차이고 실험 상태가 승인 대기. 상태 계산은 실험 목록 SQL 한 곳의 정의를 쓴다
  private boolean awaitingApproval(Long userId, Run run) {
    return experimentQueryRepository.findExperiment(userId, run.getFirstRun().getId())
        .filter(experiment -> experiment.runId().equals(run.getId()))
        .map(experiment -> AWAITING_APPROVAL.equals(experiment.state()))
        .orElse(false);
  }
}
