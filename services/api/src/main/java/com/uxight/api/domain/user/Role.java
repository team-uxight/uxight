package com.uxight.api.domain.user;

/** users.role. 상수명은 DB 값(CHECK 제약)과 같은 소문자다 — @Enumerated(STRING) 은 name() 을 저장한다. */
public enum Role {
  admin,
  researcher
}
