package com.uxight.api.domain.user;

import com.uxight.api.common.ApiException;
import com.uxight.api.common.ErrorCode;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;

@Service
public class AuthService {

  private final UserRepository userRepository;
  private final PasswordEncoder passwordEncoder;

  @Autowired
  public AuthService(UserRepository userRepository, PasswordEncoder passwordEncoder) {
    this.userRepository = userRepository;
    this.passwordEncoder = passwordEncoder;
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

  // Walking Skeleton: seed 계정의 비밀번호 해시가 mock 이다 — 이메일만 확인한다.
  // 비밀번호 검증 · is_active 확인(AUT-ERR-005)은 JWT 인증을 구현할 때 함께 넣는다.
  public User login(String email) {
    return userRepository.findByEmail(email)
        .orElseThrow(() -> new ApiException(ErrorCode.LOGIN_FAILED));
  }
}
