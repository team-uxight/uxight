package com.uxight.api.web.auth;

import com.uxight.api.domain.user.AuthService;
import com.uxight.api.domain.user.LoginTokens;
import com.uxight.api.web.common.AuthConst;
import jakarta.validation.Valid;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseCookie;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.CookieValue;
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

  @PostMapping("/login")
  public ResponseEntity<TokenResponse> login(@Valid @RequestBody LoginRequest request) {
    return tokenResponse(authService.login(request.email(), request.password()));
  }

  /** 처음 보는 Google 계정이면 가입 후 로그인 처리한다. */
  @PostMapping("/google")
  public ResponseEntity<TokenResponse> google(@Valid @RequestBody GoogleLoginRequest request) {
    return tokenResponse(authService.googleLogin(request.idToken()));
  }

  /** 쿠키가 없으면 AuthService 가 AUT-ERR-004 로 응답한다. refresh 토큰을 교체하지 않으므로 쿠키는 다시 내려보내지 않는다. */
  @PostMapping("/refresh")
  public TokenResponse refresh(
      @CookieValue(name = AuthConst.REFRESH_TOKEN_COOKIE, required = false) String refreshToken) {
    return new TokenResponse(authService.refresh(refreshToken));
  }

  /**
   * 현재 브라우저의 refresh 토큰을 무효화하고 쿠키를 지운다. 쿠키가 없거나 이미 무효인 토큰이어도 204 — 결과가 같기 때문이다.
   * access 토큰은 상태가 없어 만료 전까지 유효하다 — FE 가 보관하던 토큰을 지운다.
   */
  @PostMapping("/logout")
  public ResponseEntity<Void> logout(
      @CookieValue(name = AuthConst.REFRESH_TOKEN_COOKIE, required = false) String refreshToken) {
    authService.logout(refreshToken);
    return ResponseEntity.noContent()
        .header(HttpHeaders.SET_COOKIE, refreshTokenCookie("", Duration.ZERO).toString())
        .build();
  }

  // access 토큰은 본문으로, refresh 토큰 원문은 HttpOnly 쿠키로만 내보낸다.
  private ResponseEntity<TokenResponse> tokenResponse(LoginTokens tokens) {
    return ResponseEntity.ok()
        .header(HttpHeaders.SET_COOKIE, refreshTokenCookie(tokens.refreshToken(), refreshTokenTtl).toString())
        .body(new TokenResponse(tokens.accessToken()));
  }

  // 발급과 삭제가 같은 속성(특히 Path)이어야 브라우저가 같은 쿠키로 보고 지운다. maxAge 0 = 삭제.
  private static ResponseCookie refreshTokenCookie(String value, Duration maxAge) {
    return ResponseCookie.from(AuthConst.REFRESH_TOKEN_COOKIE, value)
        .httpOnly(true)
        .secure(true)
        .sameSite("Strict")
        .path(REFRESH_TOKEN_COOKIE_PATH)
        .maxAge(maxAge)
        .build();
  }
}
