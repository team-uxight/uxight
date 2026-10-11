package com.uxight.api.domain.user;

/** 로그인 결과. refreshToken 은 원문이다 — 쿠키로만 내보내고 로그 · 응답 본문에 싣지 않는다. */
public record LoginTokens(String accessToken, String refreshToken) {
}
