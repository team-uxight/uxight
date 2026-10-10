package com.uxight.api.web.common;

/**
 * LoginCheckInterceptor 가 access 토큰을 검증한 뒤 요청 속성에 userId 를 담는다.
 * 컨트롤러는 @RequestAttribute(LOGIN_USER_ID) 로 userId 하나만 받는다.
 */
public class AuthConst {

  public static final String LOGIN_USER_ID = "loginUserId";
  public static final String LOGIN_USER_ROLE = "loginUserRole";   // AdminCheckInterceptor 전용. 컨트롤러는 userId 만 받는다
  public static final String REFRESH_TOKEN_COOKIE = "refreshToken";
}
