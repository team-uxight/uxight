package com.uxight.api.web.finding;

import com.uxight.api.domain.finding.FindingDetail;
import com.uxight.api.domain.finding.FindingList;
import com.uxight.api.domain.finding.FindingService;
import com.uxight.api.web.common.AuthConst;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestAttribute;
import org.springframework.web.bind.annotation.RestController;

/**
 * 리서처의 진단 결과. 회차 목록에서 done 회차의 '진단 결과' → 진단 목록, 진단의 '근거 보기' → 진단 상세.
 * 본인 프로젝트의 done 회차만 — 남의 회차 · 삭제한 프로젝트 · 아직 끝나지 않은 회차는 없는 것과 같은 404.
 */
@RestController
public class FindingController {

  private final FindingService findingService;

  @Autowired
  public FindingController(FindingService findingService) {
    this.findingService = findingService;
  }

  /** 회차 정보(firstRunId · 회차 번호 · 프로젝트 제목 · Task 목표 · 개선안 수)와 진단 목록. 진단이 없으면 빈 목록. */
  @GetMapping("/api/runs/{runId}/findings")
  public FindingList findings(@PathVariable Long runId, @RequestAttribute(AuthConst.LOGIN_USER_ID) Long userId) {
    return findingService.getFindings(userId, runId);
  }

  /** 진단의 유형 · 심각도 · 요약과 근거 위치(Persona · step 구간 · URL). */
  @GetMapping("/api/findings/{findingId}")
  public FindingDetail finding(@PathVariable Long findingId, @RequestAttribute(AuthConst.LOGIN_USER_ID) Long userId) {
    return findingService.getFinding(userId, findingId);
  }
}
