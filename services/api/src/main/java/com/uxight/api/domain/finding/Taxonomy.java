package com.uxight.api.domain.finding;

/**
 * findings.taxonomy — Friction 유형. 전체 7종 중 4종 우선 구현이며 코드값은 가칭이다 (D11').
 * 상수명은 DB 값(CHECK 제약)과 같은 소문자다 — @Enumerated(STRING) 은 name() 을 저장한다.
 */
public enum Taxonomy {
  navigation_confusion,
  interaction_failure,
  task_failure,
  excessive_steps
}
