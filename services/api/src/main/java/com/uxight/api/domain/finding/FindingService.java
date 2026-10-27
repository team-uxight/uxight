package com.uxight.api.domain.finding;

import com.uxight.api.common.ApiException;
import com.uxight.api.common.ErrorCode;
import com.uxight.api.domain.run.Run;
import com.uxight.api.domain.run.RunRepository;
import com.uxight.api.domain.run.RunStatus;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

/**
 * 리서처의 진단 목록 · 상세. 회차가 본인 프로젝트의 것이고(삭제한 프로젝트 제외) status 가 done 일 때만 보인다 —
 * done 은 mode 의 마지막 단계가 끝난 뒤라, 작성 중인 진단이 보이지 않는다. 어긋나면 없는 것과 같은 404 다.
 */
@Service
public class FindingService {

  // improvements 테이블은 개선안 기능에서 만든다 — 그 전까지 개선안은 없다('개선안 확인' 버튼이 꺼진다)
  private static final int NO_IMPROVEMENTS_YET = 0;

  private final RunRepository runRepository;
  private final FindingRepository findingRepository;

  @Autowired
  public FindingService(RunRepository runRepository, FindingRepository findingRepository) {
    this.runRepository = runRepository;
    this.findingRepository = findingRepository;
  }

  /** 회차 정보와 진단 전체. 회차가 없거나 · 남의 것 · 삭제한 프로젝트 · done 아님이면 404 EXP-ERR-002. */
  @Transactional(readOnly = true)
  public FindingList getFindings(Long userId, Long runId) {
    Run run = runRepository.findByIdAndProjectUserIdAndProjectDeletedAtIsNull(runId, userId)
        .filter(found -> found.getStatus() == RunStatus.done)
        .orElseThrow(() -> new ApiException(ErrorCode.RUN_NOT_FOUND));

    Long firstRunId = run.getFirstRun().getId();
    // 다음 회차는 이전 회차가 끝나고 승인된 뒤에만 생기므로 run_id 순서가 회차 순서와 같다
    int round = (int) runRepository.countByFirstRunIdAndIdLessThanEqual(firstRunId, run.getId());
    FindingList.RoundInfo info = new FindingList.RoundInfo(firstRunId, round, run.getProject().getTitle(),
        run.getTask().getGoal(), NO_IMPROVEMENTS_YET);
    List<FindingList.Summary> findings = findingRepository.findByRunIdOrderByIdAsc(run.getId()).stream()
        .map(f -> new FindingList.Summary(f.getId(), f.getTaxonomy(), f.getSeverity(), f.getSummary()))
        .toList();
    return new FindingList(info, findings);
  }

  /** 진단 상세. 진단이 없거나 · 남의 것 · 삭제한 프로젝트 · 회차가 done 아님이면 404 FND-ERR-001. */
  @Transactional(readOnly = true)
  public FindingDetail getFinding(Long userId, Long findingId) {
    return findingRepository.findByIdAndRunProjectUserIdAndRunProjectDeletedAtIsNull(findingId, userId)
        .filter(found -> found.getRun().getStatus() == RunStatus.done)
        .map(FindingDetail::from)
        .orElseThrow(() -> new ApiException(ErrorCode.FINDING_NOT_FOUND));
  }
}
