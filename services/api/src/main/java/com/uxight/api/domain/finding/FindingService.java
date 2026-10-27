package com.uxight.api.domain.finding;

import com.uxight.api.common.ApiException;
import com.uxight.api.common.ErrorCode;
import com.uxight.api.domain.run.Run;
import com.uxight.api.domain.run.RunRepository;
import com.uxight.api.domain.run.RunStatus;
import com.uxight.api.domain.runlog.RunLogReader;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.Arrays;
import java.util.EnumMap;
import java.util.List;
import java.util.Map;

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
  private final RunLogReader runLogReader;

  @Autowired
  public FindingService(RunRepository runRepository, FindingRepository findingRepository, RunLogReader runLogReader) {
    this.runRepository = runRepository;
    this.findingRepository = findingRepository;
    this.runLogReader = runLogReader;
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
    return FindingDetail.from(visibleFinding(userId, findingId));
  }

  /**
   * 실험 이력의 Friction Taxonomy 분포. 본인 실험(삭제한 프로젝트 제외)의 최초 회차가 done 인 것의 진단만 센다 —
   * 최초 회차가 done 이 아니면 집계하지 않는다. 4종 모두 정의 순서로 돌려주고 진단이 없는 유형은 0.
   */
  @Transactional(readOnly = true)
  public TaxonomyStats getTaxonomyStats(Long userId) {
    Map<Taxonomy, Long> counts = new EnumMap<>(Taxonomy.class);
    for (Object[] row : findingRepository.countFirstRoundFindingsByTaxonomy(userId, RunStatus.done)) {
      counts.put((Taxonomy) row[0], (Long) row[1]);
    }
    return new TaxonomyStats(Arrays.stream(Taxonomy.values())
        .map(taxonomy -> new TaxonomyStats.TaxonomyCount(taxonomy, counts.getOrDefault(taxonomy, 0L)))
        .toList());
  }

  /**
   * 진단 근거의 스크린샷. 진단은 상세와 같은 조건으로 확인하고(아니면 404 FND-ERR-001), Persona · step 이 근거 범위 안일 때만
   * 파일을 읽는다 — 범위 밖이거나 파일이 없으면 404 LOG-ERR-002. 파일 읽기는 step 스크린샷 조회와 같은 코드다.
   */
  @Transactional(readOnly = true)
  public byte[] getEvidenceScreenshot(Long userId, Long findingId, long personaId, int step) {
    Finding finding = visibleFinding(userId, findingId);
    if (!finding.coversStep(personaId, step)) {
      throw new ApiException(ErrorCode.SCREENSHOT_NOT_FOUND);
    }
    return runLogReader.readScreenshot(finding.getRun().getId(), personaId, step)
        .orElseThrow(() -> new ApiException(ErrorCode.SCREENSHOT_NOT_FOUND));
  }

  private Finding visibleFinding(Long userId, Long findingId) {
    return findingRepository.findByIdAndRunProjectUserIdAndRunProjectDeletedAtIsNull(findingId, userId)
        .filter(found -> found.getRun().getStatus() == RunStatus.done)
        .orElseThrow(() -> new ApiException(ErrorCode.FINDING_NOT_FOUND));
  }
}
