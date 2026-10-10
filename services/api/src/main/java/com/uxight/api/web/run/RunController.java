package com.uxight.api.web.run;

import com.uxight.api.common.ApiException;
import com.uxight.api.common.ErrorCode;
import com.uxight.api.domain.run.ExperimentCreateRequest;
import com.uxight.api.domain.run.ExperimentSummary;
import com.uxight.api.domain.run.RunService;
import com.uxight.api.web.common.PageResponse;
import com.uxight.api.web.common.AuthConst;
import jakarta.validation.Valid;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.bind.annotation.RequestAttribute;

import java.util.List;
import java.util.Map;

/** 실험 관리. 경로 변수가 실험을 가리키면 firstRunId, 회차를 가리키면 runId. */
@RestController
@Slf4j
public class RunController {

  private final RunService runService;

  public RunController(RunService runService) {
    this.runService = runService;
  }

  @PostMapping("/api/projects/{projectId}/runs")
  @ResponseStatus(HttpStatus.CREATED)
  public Map<String, Long> createExperiment(@PathVariable Long projectId,
      @Valid @RequestBody ExperimentCreateRequest request,
      @RequestAttribute(AuthConst.LOGIN_USER_ID) Long userId) {
    log.info("POST /api/projects/{}/runs mode={} personaIds={}", projectId, request.mode(), request.personaIds());
    return Map.of("runId", runService.createExperiment(userId, projectId, request));
  }

  /** TODO: keyword · finishedFrom 필터는 실험 이력 화면 구현 때. */
  @GetMapping("/api/runs")
  public PageResponse<ExperimentSummary> experiments(@RequestParam(required = false) String state,
      @RequestParam(defaultValue = "0") int page, @RequestParam(defaultValue = "20") int size,
      @RequestAttribute(AuthConst.LOGIN_USER_ID) Long userId) {
    if (page < 0 || size < 1) {
      throw new ApiException(ErrorCode.INVALID_INPUT);
    }
    List<ExperimentSummary> content = runService.getExperiments(userId, state, page, size);
    return PageResponse.of(content, page, size, runService.countExperiments(userId, state));
  }

  @PostMapping("/api/runs/{firstRunId}/cancel")
  @ResponseStatus(HttpStatus.ACCEPTED)
  public void cancelExperiment(@PathVariable Long firstRunId,
      @RequestAttribute(AuthConst.LOGIN_USER_ID) Long userId) {
    log.info("POST /api/runs/{}/cancel", firstRunId);
    runService.cancelExperiment(userId, firstRunId);
  }
}
