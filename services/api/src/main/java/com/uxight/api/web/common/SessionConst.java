package com.uxight.api.web.common;

/**
 * Walking Skeleton 인증은 세션 쿠키다. 설계의 JWT(access) + refresh 토큰 쿠키로 바꿀 때 이 세션 속성과
 * LoginCheckInterceptor · AuthController 만 교체한다. 컨트롤러는 userId 하나만 받는다
 * (access 토큰에도 userId 만 담는다 — schema_blueprint users.is_active 주석).
 */
public class SessionConst {

  public static final String LOGIN_USER_ID = "loginUserId";
}
