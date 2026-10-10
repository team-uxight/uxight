package com.uxight.api.web.common;

import com.uxight.api.common.ApiException;
import com.uxight.api.common.ErrorCode;
import com.uxight.api.domain.user.Role;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.web.cors.CorsUtils;
import org.springframework.web.servlet.HandlerInterceptor;

/**
 * 관리자 전용 API(/api/admin/**) 권한 확인. 경로만으로 권한을 나눈다 (design-decision 6.2).
 * LoginCheckInterceptor 뒤에 돌고, 그쪽이 매 요청 DB 에서 읽은 역할을 쓴다. 리서처는 403 AUT-ERR-006.
 * 경로 판정은 WebConfig 의 패턴 등록에 맡긴다 — 컨트롤러 매핑과 같은 방식으로 경로를 해석하므로,
 * 관리자 컨트롤러에 닿는 요청은 표기(//, 인코딩 등)와 무관하게 이 검사를 거친다.
 */
public class AdminCheckInterceptor implements HandlerInterceptor {

  @Override
  public boolean preHandle(HttpServletRequest request, HttpServletResponse response, Object handler) {
    if (CorsUtils.isPreFlightRequest(request)) {
      return true;
    }
    if (request.getAttribute(AuthConst.LOGIN_USER_ROLE) != Role.admin) {
      throw new ApiException(ErrorCode.FORBIDDEN);
    }
    return true;
  }
}
