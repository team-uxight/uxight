package com.uxight.api.domain.user;

/** 검증을 마친 Google ID 토큰의 계정 정보. sub 는 Google 계정 고유 식별자(users.google_sub)다. */
public record GoogleAccount(String sub, String email, String name) {
}
