package com.uxight.api.domain.run;

import com.uxight.api.common.ApiException;
import com.uxight.api.common.ErrorCode;
import com.uxight.api.domain.runlog.RunPersonaList;
import com.uxight.api.domain.runlog.RunPersonaQueryRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.ArrayList;
import java.util.List;

/**
 * 관리자의 전체 실험 목록 · 회차 목록. 리서처용(RunService)과 달리 소유자를 가리지 않고, 삭제된 프로젝트의 실험도 본다.
 * 회차 목록에서 고른 runId · personaId 로 운영자용 step 로그 · 스크린샷(AdminRunLogController)을 조회한다.
 */
@Service
public class AdminExperimentService {

  private final AdminExperimentQueryRepository adminExperimentQueryRepository;
  private final RunRepository runRepository;
  private final RunPersonaQueryRepository runPersonaQueryRepository;

  @Autowired
  public AdminExperimentService(AdminExperimentQueryRepository adminExperimentQueryRepository,
      RunRepository runRepository, RunPersonaQueryRepository runPersonaQueryRepository) {
    this.adminExperimentQueryRepository = adminExperimentQueryRepository;
    this.runRepository = runRepository;
    this.runPersonaQueryRepository = runPersonaQueryRepository;
  }

  /** 모든 사용자의 실험 — 최근 요청 순. */
  @Transactional(readOnly = true)
  public List<AdminExperimentSummary> getExperiments(int page, int size) {
    return adminExperimentQueryRepository.findExperiments(page * size, size);
  }

  @Transactional(readOnly = true)
  public long countExperiments() {
    return adminExperimentQueryRepository.countExperiments();
  }

  /**
   * 실험의 회차들 — 회차 순. 회차마다 Persona 별 진행(AI 접수 전이면 이름만)을 붙인다.
   * 없는 실험이거나 최초 회차가 아닌 runId 면 404 EXP-ERR-001.
   */
  @Transactional(readOnly = true)
  public List<AdminRound> getRounds(Long firstRunId) {
    // 다음 회차는 이전 회차가 끝나고 승인된 뒤에만 생기므로 run_id 순서가 회차 순서와 같다
    List<Run> runs = runRepository.findByFirstRunIdOrderByIdAsc(firstRunId);
    if (runs.isEmpty()) {
      throw new ApiException(ErrorCode.EXPERIMENT_NOT_FOUND);
    }
    List<AdminRound> rounds = new ArrayList<>();
    for (Run run : runs) {
      rounds.add(new AdminRound(run.getId(), run.getProject().getTitle(), run.getTask().getGoal(), run.getMode(),
          rounds.size() + 1, run.getStatus(),
          RunPersonaList.Item.of(run.getPersonaSnapshot(), runPersonaQueryRepository.findByRunId(run.getId()))));
    }
    return rounds;
  }
}
