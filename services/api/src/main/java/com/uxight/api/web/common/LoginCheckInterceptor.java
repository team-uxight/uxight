package com.uxight.api.web.common;

import com.uxight.api.common.ApiException;
import com.uxight.api.common.ErrorCode;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import jakarta.servlet.http.HttpSession;
import org.springframework.web.cors.CorsUtils;
import org.springframework.web.servlet.HandlerInterceptor;

public class LoginCheckInterceptor implements HandlerInterceptor {

  @Override
  public boolean preHandle(HttpServletRequest request, HttpServletResponse response, Object handler) {
    // CORS preflight(OPTIONS)에는 쿠키가 실리지 않는다 — 막으면 브라우저가 본 요청을 보내지 못한다.
    if (CorsUtils.isPreFlightRequest(request)) {
      return true;
    }

    HttpSession session = request.getSession(false);
    if (session == null || session.getAttribute(SessionConst.LOGIN_USER_ID) == null) {
      // 미인증은 302 가 아니라 401 (design-decision §8). GlobalExceptionHandler 가 본문을 만든다.
      throw new ApiException(ErrorCode.UNAUTHORIZED);
    }

    return true;
  }
}
