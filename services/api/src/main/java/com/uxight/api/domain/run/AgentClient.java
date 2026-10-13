package com.uxight.api.domain.run;

import java.util.Optional;
import java.util.concurrent.CompletableFuture;

public interface AgentClient {

  /**
   * 회차 실행 요청 POST /runs {run_id} (내부 API 1). Python 은 run_id 로 runs 행의 스냅샷을 직접 읽는다.
   * 요청 스레드 밖(@Async)에서 돌고, 결과와 무관하게 예외를 던지지 않는다.
   * 완료값은 runs.dispatch_state에 그대로 기록할 값이다:
   * - 202(최초 수락) · 200(이미 받은 회차, 멱등): sent — 첫 호출이 timeout 이었어도 재전송의 200 은 전달됐다는 뜻이다
   * - 통신 불가 · 그 밖의 실패: unreachable / 타임아웃: timeout
   * 지금은 항상 값이 있다. 빈 Optional 은 dispatch_state 를 건드리지 않는다는 뜻으로 남겨 둔 형식이다.
   */
  CompletableFuture<Optional<DispatchState>> dispatch(Long runId);
}
