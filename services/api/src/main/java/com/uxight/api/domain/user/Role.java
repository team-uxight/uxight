package com.uxight.api.domain.user;

/** users.role. 상수명은 DB 값(CHECK 제약)과 같은 소문자다 — @Enumerated(STRING) 은 name() 을 저장한다. */
public enum Role {
  admin,
  maintainer,
  researcher;

  /** 관리자 화면(/api/admin/**) 접근 가능 여부. admin · maintainer 만 들어간다. */
  public boolean canAccessAdmin() {
    return this == admin || this == maintainer;
  }

  /** 이 역할의 요청자가 targetRole 계정의 역할을 바꿀 수 있는지. admin 은 모든 계정, maintainer 는 리서처 계정만 관리한다. */
  public boolean canManage(Role targetRole) {
    return this == admin || (this == maintainer && targetRole == researcher);
  }

  /** 이 역할의 요청자가 newRole 을 부여할 수 있는지. maintainer 는 메인테이너 · 관리자를 부여하지 못한다. */
  public boolean canGrant(Role newRole) {
    return this == admin || (this == maintainer && newRole == researcher);
  }
}
