package com.uxight.api.web.admin;

/** 계정 생성 응답. 초기 비밀번호 원문은 이 응답에서만 볼 수 있다 — DB 에는 해시만 있어 다시 조회할 수 없다. */
public record UserCreateResponse(Long userId, String initialPassword) {
}
