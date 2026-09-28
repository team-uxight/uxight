package com.uxight.api.domain.run;

import java.util.Optional;
import java.util.concurrent.CompletableFuture;

public interface AgentClient {

  /**
   * Python에 런 시작을 통보한다 (fire-and-forget). 요청 스레드 밖(@Async)에서 돌고, 결과와 무관하게 예외를 던지지 않는다.
   * 완료값은 runs.dispatch_state에 그대로 기록할 값이다:
   * - 202(최초 수락): "sent"
   * - 200(동일 run_id의 중복 요청, 멱등): 이미 최초 수락 시점에 "sent"로 기록되어 있을 것이므로
   *   빈 Optional을 반환해 dispatch_state를 다시 건드리지 않도록 한다.
   * - 통신 불가: "unreachable" / 타임아웃: "timeout"
   */
  CompletableFuture<Optional<String>> dispatch(Long runId, Object taskSnapshot, Object personaSnapshot, Object policySnapshot, Object allowedDomains);
}
