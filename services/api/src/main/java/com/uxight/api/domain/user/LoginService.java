package com.uxight.api.domain.user;

import com.uxight.api.common.ApiException;
import com.uxight.api.common.ErrorCode;
import org.springframework.stereotype.Service;

@Service
public class LoginService {

  private final UserRepository userRepository;

  public LoginService(UserRepository userRepository) {
    this.userRepository = userRepository;
  }

  // Walking Skeleton: 회원가입이 없어 seed 계정의 비밀번호 해시가 mock 이다 — 이메일만 확인한다.
  // 비밀번호 검증 · is_active 확인(AUT-ERR-005)은 JWT 인증을 구현할 때 함께 넣는다.
  public User login(String email) {
    return userRepository.findByEmail(email)
        .orElseThrow(() -> new ApiException(ErrorCode.LOGIN_FAILED));
  }
}
