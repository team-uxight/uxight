package com.uxight.api.web.admin;

import com.uxight.api.common.ApiException;
import com.uxight.api.domain.run.AdminExperimentService;
import com.uxight.api.domain.run.AdminExperimentSummary;
import com.uxight.api.web.common.PageResponse;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

/**
 * 관리자의 전체 실험 · 회차 목록. /api/admin/** 는 AdminCheckInterceptor 가 admin · maintainer 만 통과시킨다 — 리서처는 403.
 * 흐름: 실험 목록(firstRunId) → 회차 목록(회차별 runId · personaId) → 운영자용 step 로그 · 스크린샷.
 */
@RestController
@RequestMapping("/api/admin/runs")
public class AdminExperimentController {

  private final AdminExperimentService adminExperimentService;

  @Autowired
  public AdminExperimentController(AdminExperimentService adminExperimentService) {
    this.adminExperimentService = adminExperimentService;
  }

  /**
   * 모든 사용자의 실험을 최근 요청 순으로. 삭제된 프로젝트의 실험도 projectDeleted 로 표시해 보여준다. page 는 0부터.
   * 숫자가 아닌 값은 400 GLB-ERR-001, 범위 밖 값(page &lt; 0 · size &lt; 1)은 400 GLB-ERR-002.
   */
  @GetMapping
  public PageResponse<AdminExperimentSummary> experiments(@RequestParam(defaultValue = "0") int page,
      @RequestParam(defaultValue = "20") int size) {
    if (page < 0) {
      throw ApiException.invalidField("page", "0 이상이어야 합니다");
    }
    if (size < 1) {
      throw ApiException.invalidField("size", "1 이상이어야 합니다");
    }
    List<AdminExperimentSummary> content = adminExperimentService.getExperiments(page, size);
    return PageResponse.of(content, page, size, adminExperimentService.countExperiments());
  }

  /** 실험의 회차 목록과 회차별 Persona 실행 결과. 없는 실험이거나 최초 회차가 아닌 runId 면 404 EXP-ERR-001. */
  @GetMapping("/{firstRunId}/rounds")
  public AdminRoundListResponse rounds(@PathVariable Long firstRunId) {
    return AdminRoundListResponse.from(adminExperimentService.getRounds(firstRunId));
  }
}
