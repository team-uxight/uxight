package com.uxight.api.domain.user;

import org.springframework.stereotype.Service;

@Service
public class LoginService {

  private final UserRepository userRepository;

  public LoginService(UserRepository userRepository) {
    this.userRepository = userRepository;
  }

  public User login(String email) {
    return userRepository.findByEmail(email).orElse(null);
  }
}
