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
  private final Duration refreshTokenTtl;

  @Autowired
  public AuthService(UserRepository userRepository, RefreshTokenRepository refreshTokenRepository,
      PasswordEncoder passwordEncoder, JwtProvider jwtProvider,
      @Value("${uxight.auth.refresh-token-ttl}") Duration refreshTokenTtl) {
    this.userRepository = userRepository;
    this.refreshTokenRepository = refreshTokenRepository;
    this.passwordEncoder = passwordEncoder;
    this.jwtProvider = jwtProvider;
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
    if (!user.isActive()) {
      throw new ApiException(ErrorCode.ACCOUNT_DISABLED);
    }

    String rawRefreshToken = RefreshToken.newRawToken();
    refreshTokenRepository.save(RefreshToken.issue(user, rawRefreshToken, refreshTokenTtl));
    return new LoginTokens(jwtProvider.createAccessToken(user.getId()), rawRefreshToken);
  }
}
