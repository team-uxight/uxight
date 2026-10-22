package com.uxight.api.web.admin;

import com.uxight.api.common.ApiException;
import com.uxight.api.domain.user.User;
import com.uxight.api.domain.user.UserRepository;
import com.uxight.api.web.common.PageResponse;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Sort;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/** 계정 관리(관리자). /api/admin/** 는 AdminCheckInterceptor 가 admin · maintainer 만 통과시킨다 — 리서처는 403 AUT-ERR-006. */
@RestController
@RequestMapping("/api/admin")
public class AdminController {

  private final UserRepository userRepository;

  @Autowired
  public AdminController(UserRepository userRepository) {
    this.userRepository = userRepository;
  }

  /**
   * 가입한 모든 계정(비활성 포함)을 최근 가입 순으로. page 는 0부터.
   * 숫자가 아닌 값은 400 GLB-ERR-001, 범위 밖 값(page &lt; 0 · size &lt; 1)은 400 GLB-ERR-002.
   */
  @GetMapping("/users")
  public PageResponse<AdminUserResponse> users(@RequestParam(defaultValue = "0") int page,
      @RequestParam(defaultValue = "20") int size) {
    if (page < 0) {
      throw ApiException.invalidField("page", "0 이상이어야 합니다");
    }
    if (size < 1) {
      throw ApiException.invalidField("size", "1 이상이어야 합니다");
    }
    // user_id 는 가입 순으로 늘어난다 — 같은 시각에 가입한 계정도 순서가 흔들리지 않게 created_at 대신 쓴다
    Page<User> users = userRepository.findAll(PageRequest.of(page, size, Sort.by(Sort.Direction.DESC, "id")));
    return PageResponse.of(users.map(AdminUserResponse::from).getContent(), page, size, users.getTotalElements());
  }
}
