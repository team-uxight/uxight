package com.uxight.api.web.run;

import com.uxight.api.domain.runlog.RunLogService;
import com.uxight.api.domain.runlog.RunPersonaList;
import com.uxight.api.web.common.AuthConst;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.CacheControl;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestAttribute;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.time.Duration;

/**
 * 리서처의 회차 Persona 진행 · step 로그 · 스크린샷 — 실시간 모니터 화면이 1.5초마다 부른다.
 * 본인 프로젝트의 회차만. 남의 회차 · 삭제한 프로젝트의 회차는 없는 회차와 같은 404 EXP-ERR-002.
 */
@RestController
@RequestMapping("/api/runs/{runId}/personas")
public class RunLogController {

  /** 스크린샷은 한 번 쓰면 바뀌지 않는다 — 본인 브라우저에만 하루 캐시 */
  private static final CacheControl SCREENSHOT_CACHE = CacheControl.maxAge(Duration.ofDays(1)).cachePrivate();

  private final RunLogService runLogService;

  @Autowired
  public RunLogController(RunLogService runLogService) {
    this.runLogService = runLogService;
  }

  /** 회차 상태와 Persona 별 상태 · step 수 · 끝난 시각. AI 모듈이 접수하기 전이면 Persona 이름만 있다. */
  @GetMapping
  public RunPersonaList personas(@PathVariable Long runId, @RequestAttribute(AuthConst.LOGIN_USER_ID) Long userId) {
    return runLogService.getPersonas(userId, runId);
  }

  /** step 로그 전체. 실행 중이거나 시작 전이라 기록이 없으면 빈 목록. 회차에 없는 Persona 면 404 LOG-ERR-001. */
  @GetMapping("/{personaId}/steps")
  public StepLogListResponse steps(@PathVariable Long runId, @PathVariable Long personaId,
      @RequestAttribute(AuthConst.LOGIN_USER_ID) Long userId) {
    return new StepLogListResponse(runLogService.getStepsForResearcher(userId, runId, personaId));
  }

  /** step 스크린샷(PNG). 프론트엔드는 Authorization 헤더를 붙여 fetch 로 받는다. 없으면 404 LOG-ERR-002. */
  @GetMapping("/{personaId}/steps/{step}/screenshot")
  public ResponseEntity<byte[]> screenshot(@PathVariable Long runId, @PathVariable Long personaId,
      @PathVariable int step, @RequestAttribute(AuthConst.LOGIN_USER_ID) Long userId) {
    return ResponseEntity.ok()
        .contentType(MediaType.IMAGE_PNG)
        .cacheControl(SCREENSHOT_CACHE)
        .body(runLogService.getScreenshotForResearcher(userId, runId, personaId, step));
  }
}
