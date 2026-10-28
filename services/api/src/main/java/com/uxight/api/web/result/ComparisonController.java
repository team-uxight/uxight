package com.uxight.api.web.result;

import com.uxight.api.domain.result.Comparison;
import com.uxight.api.domain.result.ComparisonService;
import com.uxight.api.web.common.AuthConst;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.CacheControl;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestAttribute;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.time.Duration;

/**
 * 리서처의 결과 — 실험 모니터링의 '결과'(최초 회차가 done 인 실험에서만 켜진다) → 최초 회차와 마지막 done 회차 비교.
 * 본인 프로젝트의 실험만 — 남의 실험 · 삭제한 프로젝트는 없는 실험과 같은 404 EXP-ERR-001.
 */
@RestController
@RequestMapping("/api/runs/{firstRunId}/comparison")
public class ComparisonController {

  private static final CacheControl SCREENSHOT_CACHE = CacheControl.maxAge(Duration.ofDays(1)).cachePrivate();

  private final ComparisonService comparisonService;

  @Autowired
  public ComparisonController(ComparisonService comparisonService) {
    this.comparisonService = comparisonService;
  }

  /** 실험 정보 · Before · After(done 회차가 하나뿐이면 null) · 회차별 적용 패치. 최초 회차가 done 아니면 409 CMP-ERR-001. */
  @GetMapping
  public Comparison comparison(@PathVariable Long firstRunId, @RequestAttribute(AuthConst.LOGIN_USER_ID) Long userId) {
    return comparisonService.getComparison(userId, firstRunId);
  }

  /**
   * 결과 스크린샷(PNG). runId · personaId · step 이 Before 또는 After 의 screenshots 안일 때만 — 범위 밖이거나 파일이 없으면
   * 404 LOG-ERR-002. step 스크린샷과 같은 파일이라 본인 브라우저에 하루 캐시한다.
   */
  @GetMapping("/screenshots")
  public ResponseEntity<byte[]> screenshot(@PathVariable Long firstRunId, @RequestParam long runId,
      @RequestParam long personaId, @RequestParam int step, @RequestAttribute(AuthConst.LOGIN_USER_ID) Long userId) {
    return ResponseEntity.ok()
        .contentType(MediaType.IMAGE_PNG)
        .cacheControl(SCREENSHOT_CACHE)
        .body(comparisonService.getScreenshot(userId, firstRunId, runId, personaId, step));
  }
}
