package com.uxight.api.domain.run;

/** runs.mode — 회차가 파이프라인을 어디까지 진행하는가. 상수명은 DB 값(CHECK 제약)과 같은 소문자다. */
public enum RunMode {
  diagnose,   // 최초 회차의 진단까지
  improve,    // 최초 회차의 개선안까지
  loop        // 개선안 → 패치 → 다음 회차를 loop_max 까지 반복
}
