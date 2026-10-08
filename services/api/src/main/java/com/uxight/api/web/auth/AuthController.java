package com.uxight.api.web.auth;

import com.uxight.api.domain.user.LoginService;
import com.uxight.api.domain.user.User;
import com.uxight.api.web.common.SessionConst;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpSession;
import jakarta.validation.Valid;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * 설계는 200 + accessToken(JWT) 과 refresh 토큰 쿠키다. Walking Skeleton 은 세션 쿠키로 대신하고
 * 본문 없이 204 를 준다 — FE 는 로그인 뒤 GET /api/users/me 로 사용자 정보를 받는다.
 */
@RestController
@RequestMapping("/api/auth")
public class AuthController {

  private final LoginService loginService;

  public AuthController(LoginService loginService) {
    this.loginService = loginService;
  }

  @PostMapping("/login")
  public ResponseEntity<Void> login(@Valid @RequestBody LoginRequest request, HttpServletRequest httpRequest) {
    User user = loginService.login(request.email());
    httpRequest.getSession().setAttribute(SessionConst.LOGIN_USER_ID, user.userId());
    return ResponseEntity.noContent().build();
  }

  @PostMapping("/logout")
  public ResponseEntity<Void> logout(HttpServletRequest httpRequest) {
    HttpSession session = httpRequest.getSession(false);
    if (session != null) {
      session.invalidate();
    }
    return ResponseEntity.noContent().build();
  }
}
