package com.uxight.api.domain.run;

import java.util.Set;

/**
 * runs.status. 상수명은 DB 값(CHECK 제약)과 같은 소문자다 — @Enumerated(STRING) 은 name() 을 저장한다.
 * Spring 은 INSERT 때 queued 만 쓰고, 그 뒤로는 Python 만 바꾼다 (Run.status 는 updatable = false).
 */
public enum RunStatus {
  queued,
  accepted,
  running,
  done,
  failed,
  cancelled;

  /** 진행 중 = 프로젝트의 실험 자리를 점유한다 (design-decision 5.2). 취소 요청된 회차도 실제로 멈추기 전까지는 진행 중이다. */
  public static final Set<RunStatus> IN_PROGRESS = Set.of(queued, accepted, running);

  public boolean isInProgress() {
    return IN_PROGRESS.contains(this);
  }
}
