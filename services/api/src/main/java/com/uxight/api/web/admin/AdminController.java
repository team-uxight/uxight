package com.uxight.api.web.admin;

import com.uxight.api.common.ApiException;
import com.uxight.api.domain.user.ActiveChangeRequest;
import com.uxight.api.domain.user.Role;
import com.uxight.api.domain.user.RoleChangeRequest;
import com.uxight.api.domain.user.User;
import com.uxight.api.domain.user.UserRepository;
import com.uxight.api.domain.user.UserService;
import com.uxight.api.web.common.AuthConst;
import com.uxight.api.web.common.PageResponse;
import jakarta.validation.Valid;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Sort;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestAttribute;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/** 계정 관리(관리자). /api/admin/** 는 AdminCheckInterceptor 가 admin · maintainer 만 통과시킨다 — 리서처는 403 AUT-ERR-006. */
@RestController
@RequestMapping("/api/admin")
public class AdminController {

  private final UserRepository userRepository;
  private final UserService userService;

  @Autowired
  public AdminController(UserRepository userRepository, UserService userService) {
    this.userRepository = userRepository;
    this.userService = userService;
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

  /**
   * 계정 역할 변경. admin 은 모든 계정을 세 역할 중 하나로, maintainer 는 리서처 계정만 리서처로 둘 수 있다(그 밖은 403).
   * 마지막 활성 관리자를 내리면 409 ACC-ERR-002. 토큰에 역할이 없어 대상 계정의 다음 요청부터 바로 적용된다.
   */
  @PatchMapping("/users/{userId}/role")
  public RoleChangeResponse changeRole(@PathVariable Long userId, @Valid @RequestBody RoleChangeRequest request,
      @RequestAttribute(AuthConst.LOGIN_USER_ID) Long actorId) {
    User user = userService.changeRole(actorId, userId, Role.valueOf(request.role()));
    return new RoleChangeResponse(user.getId(), user.getRole());
  }

  /**
   * 리서처 계정 비활성화 · 다시 활성화. admin · maintainer 모두 호출할 수 있고, 대상이 관리자 · 메인테이너 계정이면 403.
   * 같은 요청을 여러 번 보내도 결과가 같다. 비활성화된 계정은 다음 요청 · 로그인 · 토큰 재발급부터 401 AUT-ERR-005.
   */
  @PatchMapping("/users/{userId}/active")
  public ActiveChangeResponse changeActive(@PathVariable Long userId, @Valid @RequestBody ActiveChangeRequest request,
      @RequestAttribute(AuthConst.LOGIN_USER_ID) Long actorId) {
    User user = userService.changeActive(actorId, userId, request.isActive());
    return new ActiveChangeResponse(user.getId(), user.isActive());
  }
}
