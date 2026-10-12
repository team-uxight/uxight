package com.uxight.api.domain.run;

/**
 * runs.dispatch_state — Spring 이 POST /runs 를 부른 결과. null 이면 아직 호출 전이다. 상수명은 DB 값(CHECK 제약)과 같은 소문자다.
 * 회차의 status 는 바꾸지 않는다 — 응답을 못 받았어도 Python 이 이미 접수했을 수 있다.
 */
public enum DispatchState {
  sent,          // 202 — 새로 접수됨
  unreachable,   // 연결 실패 · 401 · 404 · 5xx
  timeout        // 응답 시간 초과
}
