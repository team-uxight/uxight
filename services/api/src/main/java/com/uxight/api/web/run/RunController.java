package com.uxight.api.web.run;

import com.uxight.api.common.ApiException;
import com.uxight.api.domain.run.ExperimentCreateRequest;
import com.uxight.api.domain.run.ExperimentFilter;
import com.uxight.api.domain.run.ExperimentStats;
import com.uxight.api.domain.run.ExperimentSummary;
import com.uxight.api.domain.run.RunService;
import com.uxight.api.web.common.PageResponse;
import com.uxight.api.web.common.AuthConst;
import jakarta.validation.Valid;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.bind.annotation.RequestAttribute;

import java.time.OffsetDateTime;
import java.util.List;

/** 실험 관리. 경로 변수가 실험을 가리키면 firstRunId, 회차를 가리키면 runId. */
@RestController
@Slf4j
public class RunController {

  private final RunService runService;

  @Autowired
  public RunController(RunService runService) {
    this.runService = runService;
  }

  /**
   * 실험 요청. 회차를 저장한 뒤 AI 모듈에 실행을 요청하고, 그 결과와 관계없이 201 을 돌려준다 — 진행 상황은 실험 모니터링 화면에서 본다.
   * 404 PRJ-ERR-001 · EXP-ERR-003, 409 EXP-ERR-004, 502 EXP-ERR-007, 504 EXP-ERR-008 (RunService.createExperiment).
   */
  @PostMapping("/api/projects/{projectId}/runs")
  @ResponseStatus(HttpStatus.CREATED)
  public ExperimentCreateResponse createExperiment(@PathVariable Long projectId,
      @Valid @RequestBody ExperimentCreateRequest request,
      @RequestAttribute(AuthConst.LOGIN_USER_ID) Long userId) {
    log.info("POST /api/projects/{}/runs mode={} personaIds={}", projectId, request.mode(), request.personaIds());
    return new ExperimentCreateResponse(runService.createExperiment(userId, projectId, request));
  }

  /**
   * 본인 실험 목록 — 최근 요청 순. 조건을 생략하면 적용하지 않는다. 마지막 회차가 queued · accepted · running 인 실험이
   * 화면에 있으면 프론트엔드가 같은 조건으로 3초마다 다시 부른다.
   * finishedFrom 은 시간대가 붙은 ISO-8601 시각이다(예: GET /api/runs/stats 의 thisWeekFrom). 쿼리 문자열에서 + 는 %2B 로 보낸다.
   * 형식이 틀린 값(숫자 아님 · 시각 아님)은 400 GLB-ERR-001, 범위 밖 값은 400 GLB-ERR-002.
   */
  @GetMapping("/api/runs")
  public PageResponse<ExperimentSummary> experiments(@RequestParam(required = false) String state,
      @RequestParam(required = false) String keyword,
      @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE_TIME) OffsetDateTime finishedFrom,
      @RequestParam(defaultValue = "0") int page, @RequestParam(defaultValue = "20") int size,
      @RequestAttribute(AuthConst.LOGIN_USER_ID) Long userId) {
    if (page < 0) {
      throw ApiException.invalidField("page", "0 이상이어야 합니다");
    }
    if (size < 1) {
      throw ApiException.invalidField("size", "1 이상이어야 합니다");
    }
    // 빈 검색어는 조건 없음으로 본다 — 검색창을 비우고 보낸 요청이 아무것도 못 찾지 않게
    String trimmedKeyword = keyword == null || keyword.isBlank() ? null : keyword.strip();
    ExperimentFilter filter = new ExperimentFilter(state, trimmedKeyword, finishedFrom);
    List<ExperimentSummary> content = runService.getRuns(userId, filter, page, size);
    return PageResponse.of(content, page, size, runService.countRuns(userId, filter));
  }

  /** 실험 모니터링 · 실험 이력의 건수와 총 소요 토큰. 실험 목록과 같은 상태 계산을 쓴다. */
  @GetMapping("/api/runs/stats")
  public ExperimentStats stats(@RequestAttribute(AuthConst.LOGIN_USER_ID) Long userId) {
    return runService.getStats(userId);
  }

  @PostMapping("/api/runs/{firstRunId}/cancel")
  @ResponseStatus(HttpStatus.ACCEPTED)
  public void cancelExperiment(@PathVariable Long firstRunId,
      @RequestAttribute(AuthConst.LOGIN_USER_ID) Long userId) {
    log.info("POST /api/runs/{}/cancel", firstRunId);
    runService.cancelExperiment(userId, firstRunId);
  }
}
