package com.uxight.api.web.auth;

import com.uxight.api.domain.user.AuthService;
import com.uxight.api.domain.user.LoginTokens;
import com.uxight.api.web.common.AuthConst;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpSession;
import jakarta.validation.Valid;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseCookie;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.time.Duration;

@RestController
@RequestMapping("/api/auth")
public class AuthController {

  // refresh 토큰 쿠키는 재발급 · 로그아웃(/api/auth/**)에만 실리면 된다
  private static final String REFRESH_TOKEN_COOKIE_PATH = "/api/auth";

  private final AuthService authService;
  private final Duration refreshTokenTtl;

  @Autowired
  public AuthController(AuthService authService, @Value("${uxight.auth.refresh-token-ttl}") Duration refreshTokenTtl) {
    this.authService = authService;
    this.refreshTokenTtl = refreshTokenTtl;
  }

  /** 인증 메일은 보내지 않고 토큰도 발급하지 않는다 — FE 는 가입 뒤 로그인한다. */
  @PostMapping("/signup")
  public ResponseEntity<SignupResponse> signup(@Valid @RequestBody SignupRequest request) {
    Long userId = authService.signup(request.email(), request.password(), request.name());
    return ResponseEntity.status(HttpStatus.CREATED).body(new SignupResponse(userId));
  }

  /** access 토큰은 본문으로, refresh 토큰 원문은 HttpOnly 쿠키로만 내보낸다. */
  @PostMapping("/login")
  public ResponseEntity<TokenResponse> login(@Valid @RequestBody LoginRequest request) {
    LoginTokens tokens = authService.login(request.email(), request.password());
    ResponseCookie refreshTokenCookie = ResponseCookie.from(AuthConst.REFRESH_TOKEN_COOKIE, tokens.refreshToken())
        .httpOnly(true)
        .secure(true)
        .sameSite("Strict")
        .path(REFRESH_TOKEN_COOKIE_PATH)
        .maxAge(refreshTokenTtl)
        .build();
    return ResponseEntity.ok()
        .header(HttpHeaders.SET_COOKIE, refreshTokenCookie.toString())
        .body(new TokenResponse(tokens.accessToken()));
  }

  // TODO: 세션 기반 Walking Skeleton 의 잔재. 로그아웃 티켓에서 refresh 토큰 무효화 + 쿠키 삭제로 바꾼다 (OpenAPI logout).
  @PostMapping("/logout")
  public ResponseEntity<Void> logout(HttpServletRequest httpRequest) {
    HttpSession session = httpRequest.getSession(false);
    if (session != null) {
      session.invalidate();
    }
    return ResponseEntity.noContent().build();
  }
}
