package com.uxight.api.domain.user;

import com.uxight.api.common.ApiException;
import com.uxight.api.common.ErrorCode;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Duration;

@Service
public class AuthService {

  private final UserRepository userRepository;
  private final RefreshTokenRepository refreshTokenRepository;
  private final PasswordEncoder passwordEncoder;
  private final JwtProvider jwtProvider;
  private final GoogleIdTokenVerifier googleIdTokenVerifier;
  private final Duration refreshTokenTtl;

  @Autowired
  public AuthService(UserRepository userRepository, RefreshTokenRepository refreshTokenRepository,
      PasswordEncoder passwordEncoder, JwtProvider jwtProvider, GoogleIdTokenVerifier googleIdTokenVerifier,
      @Value("${uxight.auth.refresh-token-ttl}") Duration refreshTokenTtl) {
    this.userRepository = userRepository;
    this.refreshTokenRepository = refreshTokenRepository;
    this.passwordEncoder = passwordEncoder;
    this.jwtProvider = jwtProvider;
    this.googleIdTokenVerifier = googleIdTokenVerifier;
    this.refreshTokenTtl = refreshTokenTtl;
  }

  /** 이메일 가입. 생성된 userId 를 돌려준다. 비밀번호 형식은 SignupRequest 가 검증한다. */
  public Long signup(String email, String password, String name) {
    if (userRepository.findByEmail(email).isPresent()) {
      throw new ApiException(ErrorCode.EMAIL_DUPLICATED);
    }

    try {
      return userRepository.save(User.signUp(email, passwordEncoder.encode(password), name)).getId();
    } catch (DataIntegrityViolationException e) {
      // 조회 뒤 같은 이메일이 먼저 가입한 경우 — uk_users_email 이 최종 판정이다.
      throw new ApiException(ErrorCode.EMAIL_DUPLICATED);
    }
  }

  /**
   * 이메일 로그인. 계정 없음 · 비밀번호 불일치 · 비밀번호 없는(Google 전용) 계정은 구분하지 않고 AUT-ERR-002.
   * 비활성 여부는 비밀번호를 확인한 뒤에 알린다 — 비밀번호를 모르는 사람에게 계정이 있다는 것을 알리지 않기 위해서다.
   */
  @Transactional
  public LoginTokens login(String email, String password) {
    User user = userRepository.findByEmail(email)
        .filter(found -> found.matchesPassword(password, passwordEncoder))
        .orElseThrow(() -> new ApiException(ErrorCode.LOGIN_FAILED));
    return issueTokens(user);
  }

  /**
   * Google 회원가입 · 로그인. ID 토큰의 Google 계정 고유 식별자(sub)로 계정을 찾고, 없으면 리서처로 가입시킨다.
   * 같은 이메일의 이메일 가입 계정이 있으면 연결하지 않고 AUT-ERR-008 — 이메일 가입은 이메일 소유를 확인하지 않았기 때문이다.
   */
  @Transactional
  public LoginTokens googleLogin(String idToken) {
    GoogleAccount account = googleIdTokenVerifier.verify(idToken)
        .orElseThrow(() -> new ApiException(ErrorCode.GOOGLE_AUTH_FAILED));
    User user = userRepository.findByGoogleSub(account.sub())
        .orElseGet(() -> signUpWithGoogle(account));
    return issueTokens(user);
  }

  private User signUpWithGoogle(GoogleAccount account) {
    if (userRepository.findByEmail(account.email()).isPresent()) {
      throw new ApiException(ErrorCode.EMAIL_ACCOUNT_EXISTS);
    }

    try {
      return userRepository.save(User.signUpWithGoogle(account.email(), account.sub(), account.name()));
    } catch (DataIntegrityViolationException e) {
      // 조회 뒤 같은 이메일이 먼저 가입한 경우 — uk_users_email 이 최종 판정이다.
      throw new ApiException(ErrorCode.EMAIL_ACCOUNT_EXISTS);
    }
  }

  // 인증을 마친 계정의 활성 여부를 확인하고 access · refresh 토큰을 발급한다. 이메일 · Google 로그인 공통.
  private LoginTokens issueTokens(User user) {
    if (!user.isActive()) {
      throw new ApiException(ErrorCode.ACCOUNT_DISABLED);
    }

    String rawRefreshToken = RefreshToken.newRawToken();
    refreshTokenRepository.save(RefreshToken.issue(user, rawRefreshToken, refreshTokenTtl));
    return new LoginTokens(jwtProvider.createAccessToken(user.getId()), rawRefreshToken);
  }

  /**
   * access 토큰 재발급. 쿠키의 refresh 토큰 원문을 해시해 찾고, 만료 · 무효화 여부와 계정 활성 여부를 확인한다.
   * refresh 토큰은 교체(rotation)하지 않는다 — 로그아웃 또는 만료 때만 무효가 된다 (design-decision 6.1).
   */
  @Transactional(readOnly = true)
  public String refresh(String rawRefreshToken) {
    if (rawRefreshToken == null || rawRefreshToken.isBlank()) {
      throw new ApiException(ErrorCode.REFRESH_TOKEN_INVALID);
    }
    RefreshToken refreshToken = refreshTokenRepository.findByTokenHash(RefreshToken.hash(rawRefreshToken))
        .filter(RefreshToken::isUsable)
        .orElseThrow(() -> new ApiException(ErrorCode.REFRESH_TOKEN_INVALID));
    User user = refreshToken.getUser();
    if (!user.isActive()) {
      throw new ApiException(ErrorCode.ACCOUNT_DISABLED);
    }
    return jwtProvider.createAccessToken(user.getId());
  }

  /** 로그아웃. 쿠키의 refresh 토큰을 무효화한다. 쿠키가 없거나 모르는 토큰이면 할 일이 없다 — 같은 결과이므로 실패로 보지 않는다. */
  @Transactional
  public void logout(String rawRefreshToken) {
    if (rawRefreshToken == null || rawRefreshToken.isBlank()) {
      return;
    }
    refreshTokenRepository.findByTokenHash(RefreshToken.hash(rawRefreshToken))
        .ifPresent(RefreshToken::revoke);
  }
}
