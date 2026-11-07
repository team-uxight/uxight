package com.uxight.api.domain.user;

/** 관리자가 만든 계정과 초기 비밀번호 원문. 원문은 DB 에 없고 생성 응답에서 한 번만 내보낸다. */
public record CreatedUser(User user, String initialPassword) {
}
