package com.uxight.api.web.user;

import com.uxight.api.common.ApiException;
import com.uxight.api.common.ErrorCode;
import com.uxight.api.domain.user.User;
import com.uxight.api.domain.user.UserRepository;
import com.uxight.api.web.common.SessionConst;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.bind.annotation.SessionAttribute;

@RestController
public class UserController {

  private final UserRepository userRepository;

  @Autowired
  public UserController(UserRepository userRepository) {
    this.userRepository = userRepository;
  }

  @GetMapping("/api/users/me")
  public UserMe me(@SessionAttribute(SessionConst.LOGIN_USER_ID) Long userId) {
    User user = userRepository.findById(userId)
        .orElseThrow(() -> new ApiException(ErrorCode.UNAUTHORIZED));
    return new UserMe(user.getId(), user.getName(), user.getRole().name());
  }
}
