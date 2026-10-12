package com.uxight.api.domain.run;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.time.Duration;

/**
 * queued 로 갇힌 회차 재전송을 주기적으로 돌린다 (design-decision 4.6). 기준 시간 · 주기는 uxight.redispatch.
 * 프로젝트는 최대 (기준 시간 + 주기) 동안만 갇힌 회차에 점유된다. 테스트에서는 꺼 둔다 (src/test/resources/application.properties).
 */
@Component
@ConditionalOnProperty(name = "uxight.redispatch.enabled", havingValue = "true", matchIfMissing = true)
public class RedispatchScheduler {

  private final RunService runService;
  private final Duration staleAfter;

  @Autowired
  public RedispatchScheduler(RunService runService, @Value("${uxight.redispatch.stale-after}") Duration staleAfter) {
    this.runService = runService;
    this.staleAfter = staleAfter;
  }

  @Scheduled(initialDelayString = "${uxight.redispatch.interval}", fixedDelayString = "${uxight.redispatch.interval}")
  public void redispatchStaleQueuedRuns() {
    runService.redispatchStaleQueuedRuns(staleAfter);
  }
}
