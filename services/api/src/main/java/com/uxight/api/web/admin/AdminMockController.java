package com.uxight.api.web.admin;

import com.uxight.api.web.common.AuthConst;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestAttribute;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

/**
 * 관리자 경로 권한 확인용 Mock — AdminCheckInterceptor 를 통과해야만 닿는다.
 * TODO: 실제 관리자 API(계정 · 정책 · 감사 로그 등)가 생기면 지운다.
 */
@RestController
public class AdminMockController {

  @GetMapping("/api/admin/mock")
  public Map<String, Object> mock(@RequestAttribute(AuthConst.LOGIN_USER_ID) Long userId) {
    return Map.of("message", "admin only", "userId", userId);
  }
}
