package com.uxight.api.web.admin;

import com.uxight.api.domain.runlog.RunLogService;
import com.uxight.api.web.run.StepLogListResponse;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.CacheControl;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.time.Duration;

/**
 * 운영자의 회차 step 로그 · 스크린샷. /api/admin/** 는 AdminCheckInterceptor 가 admin · maintainer 만 통과시키고,
 * 통과하면 모든 회차를 볼 수 있다. 읽는 코드는 리서처용(RunLogController)과 같다.
 */
@RestController
@RequestMapping("/api/admin/runs/{runId}/personas/{personaId}")
public class AdminRunLogController {

  private static final CacheControl SCREENSHOT_CACHE = CacheControl.maxAge(Duration.ofDays(1)).cachePrivate();

  private final RunLogService runLogService;

  @Autowired
  public AdminRunLogController(RunLogService runLogService) {
    this.runLogService = runLogService;
  }

  @GetMapping("/steps")
  public StepLogListResponse steps(@PathVariable Long runId, @PathVariable Long personaId) {
    return new StepLogListResponse(runLogService.getStepsForAdmin(runId, personaId));
  }

  @GetMapping("/steps/{step}/screenshot")
  public ResponseEntity<byte[]> screenshot(@PathVariable Long runId, @PathVariable Long personaId,
      @PathVariable int step) {
    return ResponseEntity.ok()
        .contentType(MediaType.IMAGE_PNG)
        .cacheControl(SCREENSHOT_CACHE)
        .body(runLogService.getScreenshotForAdmin(runId, personaId, step));
  }
}
