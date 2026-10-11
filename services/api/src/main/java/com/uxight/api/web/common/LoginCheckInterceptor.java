package com.uxight.api.web.common;

import com.uxight.api.common.ApiException;
import com.uxight.api.common.ErrorCode;
import com.uxight.api.domain.user.JwtProvider;
import com.uxight.api.domain.user.User;
import com.uxight.api.domain.user.UserRepository;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.HttpHeaders;
import org.springframework.stereotype.Component;
import org.springframework.web.cors.CorsUtils;
import org.springframework.web.servlet.HandlerInterceptor;

/**
 * Authorization: Bearer {access 토큰} 을 검증한다. 토큰에는 userId 만 있으므로 계정 활성 여부는 매 요청 DB 에서 확인한다 —
 * 비활성화가 토큰 만료를 기다리지 않고 바로 반영된다 (design-decision 6.1).
 * 같은 행에서 읽은 역할을 요청 속성에 담아 AdminCheckInterceptor 가 쓴다 — 역할 변경도 다음 요청부터 바로 반영된다.
 */
@Component
public class LoginCheckInterceptor implements HandlerInterceptor {

  private static final String BEARER_PREFIX = "Bearer ";

  private final JwtProvider jwtProvider;
  private final UserRepository userRepository;

  @Autowired
  public LoginCheckInterceptor(JwtProvider jwtProvider, UserRepository userRepository) {
    this.jwtProvider = jwtProvider;
    this.userRepository = userRepository;
  }

  @Override
  public boolean preHandle(HttpServletRequest request, HttpServletResponse response, Object handler) {
    // CORS preflight(OPTIONS)에는 Authorization 헤더가 실리지 않는다 — 막으면 브라우저가 본 요청을 보내지 못한다.
    if (CorsUtils.isPreFlightRequest(request)) {
      return true;
    }

    // 미인증은 302 가 아니라 401 (design-decision §8). GlobalExceptionHandler 가 본문을 만든다.
    String header = request.getHeader(HttpHeaders.AUTHORIZATION);
    if (header == null || !header.startsWith(BEARER_PREFIX)) {
      throw new ApiException(ErrorCode.UNAUTHORIZED);
    }
    Long userId = jwtProvider.parseUserId(header.substring(BEARER_PREFIX.length()))
        .orElseThrow(() -> new ApiException(ErrorCode.UNAUTHORIZED));
    User user = userRepository.findById(userId)
        .orElseThrow(() -> new ApiException(ErrorCode.UNAUTHORIZED));
    if (!user.isActive()) {
      throw new ApiException(ErrorCode.ACCOUNT_DISABLED);
    }

    request.setAttribute(AuthConst.LOGIN_USER_ID, userId);
    request.setAttribute(AuthConst.LOGIN_USER_ROLE, user.getRole());
    return true;
  }
}
