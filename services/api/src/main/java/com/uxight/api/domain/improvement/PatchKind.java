package com.uxight.api.domain.improvement;

/**
 * improvements.patch_kind — 패치 4종(D7). 코드값은 가칭이다.
 * 상수명은 DB 값(CHECK 제약)과 같은 소문자다 — @Enumerated(STRING) 은 name() 을 저장한다.
 */
public enum PatchKind {
  relabel,     // 라벨 변경
  move,        // 요소 이동
  highlight,   // 요소 강조
  help_text    // 도움말 삽입
}
