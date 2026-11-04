package com.uxight.api.domain.result;

import com.uxight.api.common.ApiException;
import com.uxight.api.common.ErrorCode;
import com.uxight.api.domain.finding.Finding;
import com.uxight.api.domain.finding.FindingRepository;
import com.uxight.api.domain.improvement.Improvement;
import com.uxight.api.domain.run.ExperimentQueryRepository;
import com.uxight.api.domain.run.ExperimentSummary;
import com.uxight.api.domain.run.RoundSummary;
import com.uxight.api.domain.run.Run;
import com.uxight.api.domain.run.RunMetrics;
import com.uxight.api.domain.run.RunRepository;
import com.uxight.api.domain.run.RunStatus;
import com.uxight.api.domain.runlog.RunLogReader;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.Collection;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.Set;
import java.util.function.Function;
import java.util.stream.Collectors;

/**
 * 결과 조회 — 실험의 최초 회차(Before)와 마지막 done 회차(After) 비교 (design-decision 2.4).
 * 본인 프로젝트(삭제 제외)의 실험만 — 아니면 실험 목록과 같은 404 EXP-ERR-001. 최초 회차가 done 이 아니면 결과가 없다.
 *
 * <p>Before/After 스크린샷은 패치 전 UI 와 적용 후 UI 를 같은 화면으로 비교하기 위한 것이라 <b>패치가 들어간 페이지</b>를 고른다:
 * After 까지 적용된 개선안들이 다루는 진단의 근거 URL 을 모으고, 양쪽 회차에서 Persona 마다 그 URL 에 처음 도착해 스크린샷을 남긴
 * step 하나씩. 적용된 개선안이 없으면(After 없음) 양쪽 모두 빈 목록이다. 리서처에게는 이 목록의 스크린샷만 열어 둔다 —
 * 스크린샷 전체 조회는 관리자 기능이다.
 */
@Service
public class ComparisonService {

  private static final RunMetrics NO_METRICS = new RunMetrics(null, null, null, null, null, null);

  private final ExperimentQueryRepository experimentQueryRepository;
  private final PatchVersionQueryRepository patchVersionQueryRepository;
  private final RunRepository runRepository;
  private final FindingRepository findingRepository;
  private final RunLogReader runLogReader;

  @Autowired
  public ComparisonService(ExperimentQueryRepository experimentQueryRepository,
      PatchVersionQueryRepository patchVersionQueryRepository, RunRepository runRepository,
      FindingRepository findingRepository, RunLogReader runLogReader) {
    this.experimentQueryRepository = experimentQueryRepository;
    this.patchVersionQueryRepository = patchVersionQueryRepository;
    this.runRepository = runRepository;
    this.findingRepository = findingRepository;
    this.runLogReader = runLogReader;
  }

  /** 실험이 없거나 · 남의 것 · 삭제한 프로젝트 · 최초 회차가 아닌 runId 면 404 EXP-ERR-001, 최초 회차가 done 아니면 409 CMP-ERR-001. */
  @Transactional(readOnly = true)
  public Comparison getComparison(Long userId, Long firstRunId) {
    return compare(userId, firstRunId).orElseThrow(() -> new ApiException(ErrorCode.COMPARISON_NOT_READY));
  }

  /**
   * 결과 스크린샷. 실험은 결과 조회와 같은 조건으로 확인하고(404 EXP-ERR-001), runId · personaId · step 이 Before 또는 After 의
   * screenshots 안일 때만 파일을 읽는다 — 범위 밖이거나(최초 회차가 done 아니어서 결과가 없을 때 포함) 파일이 없으면 404 LOG-ERR-002.
   */
  @Transactional(readOnly = true)
  public byte[] getScreenshot(Long userId, Long firstRunId, long runId, long personaId, int step) {
    Comparison comparison = compare(userId, firstRunId)
        .orElseThrow(() -> new ApiException(ErrorCode.SCREENSHOT_NOT_FOUND));
    Comparison.ScreenshotRef ref = new Comparison.ScreenshotRef(personaId, step);
    Comparison.After after = comparison.after();
    boolean inRange = (comparison.before().runId() == runId && comparison.before().screenshots().contains(ref))
        || (after != null && after.runId() == runId && after.screenshots().contains(ref));
    if (!inRange) {
      throw new ApiException(ErrorCode.SCREENSHOT_NOT_FOUND);
    }
    return runLogReader.readScreenshot(runId, personaId, step)
        .orElseThrow(() -> new ApiException(ErrorCode.SCREENSHOT_NOT_FOUND));
  }

  // 최초 회차가 done 이 아니면 빈 값
  private Optional<Comparison> compare(Long userId, Long firstRunId) {
    ExperimentSummary experiment = experimentQueryRepository.findExperiment(userId, firstRunId)
        .orElseThrow(() -> new ApiException(ErrorCode.EXPERIMENT_NOT_FOUND));
    List<RoundSummary> rounds = experimentQueryRepository.findRounds(userId, firstRunId);
    RoundSummary first = rounds.get(0);
    if (!isDone(first)) {
      return Optional.empty();
    }
    // 실험이 진행 중이면 그때까지 done 인 회차 중 가장 최근 회차
    Optional<RoundSummary> last = rounds.stream().skip(1).filter(ComparisonService::isDone).reduce((a, b) -> b);

    Map<Long, Run> runs = runRepository.findByFirstRunIdOrderByIdAsc(firstRunId).stream()
        .collect(Collectors.toMap(Run::getId, Function.identity()));
    Set<String> pages = last.map(after -> patchedPages(runs.values(), after.runId())).orElse(Set.of());

    Comparison.Before before = new Comparison.Before(first.runId(), metricsOf(first),
        screenshotsOf(runs.get(first.runId()), pages));
    Comparison.After after = last
        .map(round -> new Comparison.After(round.runId(), round.round(), metricsOf(round),
            screenshotsOf(runs.get(round.runId()), pages)))
        .orElse(null);
    return Optional.of(new Comparison(
        new Comparison.Experiment(experiment.projectTitle(), experiment.taskGoal(), experiment.mode(), experiment.state()),
        before, after, patchVersionQueryRepository.findByFirstRunId(firstRunId)));
  }

  // After 까지의 회차에 적용된 개선안들이 다루는 진단의 근거 URL — 개선안의 finding_ids 는 개선안과 같은 회차의 진단만 읽는다
  private Set<String> patchedPages(Collection<Run> runs, long afterRunId) {
    return runs.stream()
        .filter(run -> run.getId() <= afterRunId && run.getImprovement() != null)
        .map(Run::getImprovement)
        .flatMap(improvement -> findingsOf(improvement).stream())
        .flatMap(finding -> finding.evidenceList().stream())
        .map(Finding.Evidence::url)
        .filter(Objects::nonNull)
        .collect(Collectors.toSet());
  }

  private List<Finding> findingsOf(Improvement improvement) {
    return findingRepository.findByRunIdAndIdInOrderByIdAsc(improvement.getRun().getId(), improvement.getFindingIds());
  }

  // Persona 스냅샷 순서대로, 패치 페이지에 처음 도착해 스크린샷을 남긴 step. 못 찾은 Persona(로그가 없거나 그 페이지에 가지 않음)는 빠진다
  private List<Comparison.ScreenshotRef> screenshotsOf(Run run, Set<String> pages) {
    if (pages.isEmpty()) {
      return List.of();
    }
    return run.getPersonaSnapshot().stream()
        .map(persona -> ((Number) persona.get("persona_id")).longValue())
        .flatMap(personaId -> runLogReader.readSteps(run.getId(), personaId).orElse(List.of()).stream()
            .filter(step -> step.hasScreenshot() && pages.contains(step.url()))
            .findFirst()
            .map(step -> new Comparison.ScreenshotRef(personaId, step.step()))
            .stream())
        .toList();
  }

  private static boolean isDone(RoundSummary round) {
    return RunStatus.done.name().equals(round.status());
  }

  private static RunMetrics metricsOf(RoundSummary round) {
    return round.metrics() == null ? NO_METRICS : round.metrics();
  }
}
