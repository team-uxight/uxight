package com.uxight.api.domain.runlog;

import com.uxight.api.common.ApiException;
import com.uxight.api.common.ErrorCode;
import com.uxight.api.domain.run.Run;
import com.uxight.api.domain.run.RunRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.function.Function;
import java.util.stream.Collectors;

/**
 * 회차의 Persona 진행 · step 로그 · 스크린샷 조회. 리서처용과 운영자용은 회차를 찾는 권한 확인만 다르고 읽는 코드(RunLogReader)는 같다.
 * - 리서처: 본인 프로젝트의 회차만. 남의 회차 · 삭제한 프로젝트의 회차는 없는 회차와 같은 404 EXP-ERR-002
 * - 운영자: /api/admin/** 를 통과했으면(admin · maintainer) 모든 회차
 */
@Service
public class RunLogService {

  // run_personas.status 가 이 값이거나 행이 아직 없으면 step 로그 파일이 없어도 빈 목록이다 — agent 가 아직 첫 줄을 쓰지 않았다
  private static final String RUNNING = "running";

  private final RunRepository runRepository;
  private final RunPersonaQueryRepository runPersonaQueryRepository;
  private final RunLogReader runLogReader;

  @Autowired
  public RunLogService(RunRepository runRepository, RunPersonaQueryRepository runPersonaQueryRepository,
      RunLogReader runLogReader) {
    this.runRepository = runRepository;
    this.runPersonaQueryRepository = runPersonaQueryRepository;
    this.runLogReader = runLogReader;
  }

  /** 리서처 — 회차 상태와 Persona 별 진행. 접수 전이어도 스냅샷의 Persona 이름은 보인다. */
  @Transactional(readOnly = true)
  public RunPersonaList getPersonas(Long userId, Long runId) {
    Run run = researcherRun(userId, runId);
    Map<Long, RunPersonaStatus> statuses = runPersonaQueryRepository.findByRunId(run.getId()).stream()
        .collect(Collectors.toMap(RunPersonaStatus::personaId, Function.identity()));
    List<RunPersonaList.Item> personas = run.getPersonaSnapshot().stream()
        .map(persona -> {
          long personaId = personaId(persona);
          Optional<RunPersonaStatus> status = Optional.ofNullable(statuses.get(personaId));
          return new RunPersonaList.Item(personaId, (String) persona.get("name"),
              status.map(RunPersonaStatus::status).orElse(null), status.map(RunPersonaStatus::steps).orElse(null),
              status.map(RunPersonaStatus::finishedAt).orElse(null));
        })
        .toList();
    return new RunPersonaList(run.getId(), run.getStatus(), personas);
  }

  @Transactional(readOnly = true)
  public List<StepLog> getStepsForResearcher(Long userId, Long runId, Long personaId) {
    return steps(researcherRun(userId, runId), personaId);
  }

  @Transactional(readOnly = true)
  public List<StepLog> getStepsForAdmin(Long runId, Long personaId) {
    return steps(adminRun(runId), personaId);
  }

  @Transactional(readOnly = true)
  public byte[] getScreenshotForResearcher(Long userId, Long runId, Long personaId, int step) {
    return screenshot(researcherRun(userId, runId), personaId, step);
  }

  @Transactional(readOnly = true)
  public byte[] getScreenshotForAdmin(Long runId, Long personaId, int step) {
    return screenshot(adminRun(runId), personaId, step);
  }

  private Run researcherRun(Long userId, Long runId) {
    return runRepository.findByIdAndProjectUserIdAndProjectDeletedAtIsNull(runId, userId)
        .orElseThrow(() -> new ApiException(ErrorCode.RUN_NOT_FOUND));
  }

  private Run adminRun(Long runId) {
    return runRepository.findById(runId).orElseThrow(() -> new ApiException(ErrorCode.RUN_NOT_FOUND));
  }

  /**
   * 그 회차에 해당 Persona 가 없으면 404 LOG-ERR-001. 실행 중이거나 아직 시작 전이면 파일이 없어도 빈 목록,
   * 종료된 Persona 실행인데 파일이 없으면 404 LOG-ERR-001.
   */
  private List<StepLog> steps(Run run, Long personaId) {
    if (!inRun(run, personaId)) {
      throw new ApiException(ErrorCode.STEP_LOG_NOT_FOUND);
    }
    Optional<List<StepLog>> steps = runLogReader.readSteps(run.getId(), personaId);
    if (steps.isPresent()) {
      return steps.get();
    }
    String status = runPersonaQueryRepository.findByRunId(run.getId()).stream()
        .filter(persona -> persona.personaId() == personaId)
        .map(RunPersonaStatus::status)
        .findFirst().orElse(null);
    if (status == null || status.equals(RUNNING)) {
      return List.of();
    }
    throw new ApiException(ErrorCode.STEP_LOG_NOT_FOUND);
  }

  private byte[] screenshot(Run run, Long personaId, int step) {
    if (!inRun(run, personaId)) {
      throw new ApiException(ErrorCode.SCREENSHOT_NOT_FOUND);
    }
    return runLogReader.readScreenshot(run.getId(), personaId, step)
        .orElseThrow(() -> new ApiException(ErrorCode.SCREENSHOT_NOT_FOUND));
  }

  private static boolean inRun(Run run, Long personaId) {
    return run.getPersonaSnapshot().stream().anyMatch(persona -> personaId(persona) == personaId);
  }

  private static long personaId(Map<String, Object> persona) {
    return ((Number) persona.get("persona_id")).longValue();
  }
}
