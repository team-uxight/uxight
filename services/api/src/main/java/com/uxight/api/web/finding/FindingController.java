package com.uxight.api.web.finding;

import com.uxight.api.domain.finding.FindingDetail;
import com.uxight.api.domain.finding.FindingList;
import com.uxight.api.domain.finding.FindingService;
import com.uxight.api.domain.finding.TaxonomyStats;
import com.uxight.api.web.common.AuthConst;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.CacheControl;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestAttribute;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.time.Duration;

/**
 * 리서처의 진단 결과. 회차 목록에서 done 회차의 '진단 결과' → 진단 목록, 진단의 '근거 보기' → 진단 상세 · 근거 스크린샷,
 * 실험 이력 → Taxonomy 분포.
 * 본인 프로젝트의 done 회차만 — 남의 회차 · 삭제한 프로젝트 · 아직 끝나지 않은 회차는 없는 것과 같은 404.
 */
@RestController
public class FindingController {

  private static final CacheControl SCREENSHOT_CACHE = CacheControl.maxAge(Duration.ofDays(1)).cachePrivate();

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

  /** 실험 이력의 Friction Taxonomy 분포 — 최초 회차가 done 인 실험의 진단 수. 4종 모두, 없는 유형은 0. */
  @GetMapping("/api/findings/stats")
  public TaxonomyStats stats(@RequestAttribute(AuthConst.LOGIN_USER_ID) Long userId) {
    return findingService.getTaxonomyStats(userId);
  }

  /**
   * 진단 근거의 스크린샷(PNG). personaId · step 이 이 진단의 근거 범위 안일 때만 — 범위 밖이거나 파일이 없으면 404 LOG-ERR-002.
   * 프론트엔드는 Authorization 헤더를 붙여 fetch 로 받는다. step 스크린샷과 같은 파일이라 본인 브라우저에 하루 캐시한다.
   */
  @GetMapping("/api/findings/{findingId}/screenshots")
  public ResponseEntity<byte[]> screenshot(@PathVariable Long findingId, @RequestParam long personaId,
      @RequestParam int step, @RequestAttribute(AuthConst.LOGIN_USER_ID) Long userId) {
    return ResponseEntity.ok()
        .contentType(MediaType.IMAGE_PNG)
        .cacheControl(SCREENSHOT_CACHE)
        .body(findingService.getEvidenceScreenshot(userId, findingId, personaId, step));
  }
}
