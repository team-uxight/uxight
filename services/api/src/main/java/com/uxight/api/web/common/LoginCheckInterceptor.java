package com.uxight.api.web.common;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import jakarta.servlet.http.HttpSession;
import org.springframework.web.servlet.HandlerInterceptor;

import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;

public class LoginCheckInterceptor implements HandlerInterceptor {

  @Override
  public boolean preHandle(HttpServletRequest request, HttpServletResponse response, Object handler) throws Exception {
    HttpSession session = request.getSession(false);

    if (session == null || session.getAttribute(SessionConst.LOGIN_USER) == null) {
      String redirectURL = URLEncoder.encode(request.getRequestURI(), StandardCharsets.UTF_8);
      response.sendRedirect("/login?redirectURL=" + redirectURL);
      return false;
    }

    return true;
  }
}
