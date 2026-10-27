package com.uxight.api.domain.runlog;

/**
 * step 하나의 로그. steps.jsonl 한 줄(snake_case, 행동 로그 명세 3절)에서 화면에 필요한 키만 골라 camelCase 로 바꾼 것이다.
 * 원본에 없는 칸은 null(불리언은 false) — 명세 형식을 다 쓰지 않는 agent 로그도 읽는다.
 *
 * @param blocked       blocked.is — 가드 차단 · Action 파싱 실패 · 허용되지 않은 Action 으로 실행하지 않은 step
 * @param blockedReason blocked.reason
 * @param urlReached    task.url_reached — 행동 뒤 URL 이 성공 URL 과 일치하는지. 판정 못 하면 null
 * @param hasScreenshot observation.screenshot 이 있으면 true. false 인 step 은 스크린샷을 조회하지 않는다
 */
public record StepLog(int step, String ts, String url, String reasoning, StepAction action, StepResult result,
    boolean blocked, String blockedReason, Boolean urlReached, boolean hasScreenshot) {

  /** 수행한 행동. target 은 click · type, text 는 type(마스킹된 값), direction 은 scroll 에서만 값이 있다. */
  public record StepAction(String kind, Integer target, String text, String direction) {
  }

  /** 브라우저 행동의 실행 결과. Task 달성 여부와는 별개다. errorCode 는 AI 모듈이 관리하는 값을 그대로 전달한다. */
  public record StepResult(boolean ok, String urlAfter, String error, String errorCode) {
  }
}
