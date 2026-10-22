package com.uxight.api.domain.user;

import com.uxight.api.common.ApiException;
import com.uxight.api.common.ErrorCode;
import com.uxight.api.domain.audit.AuditLog;
import com.uxight.api.domain.audit.AuditLogRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.Map;

@Service
public class UserService {

  static final String AUDIT_ACTION_ROLE_UPDATE = "user.role_update";
  static final String AUDIT_ACTION_ACTIVE_UPDATE = "user.active_update";

  private final UserRepository userRepository;
  private final AuditLogRepository auditLogRepository;

  @Autowired
  public UserService(UserRepository userRepository, AuditLogRepository auditLogRepository) {
    this.userRepository = userRepository;
    this.auditLogRepository = auditLogRepository;
  }

  /**
   * 계정 역할 변경. 없는 계정 404 ACC-ERR-001 → 요청자 권한 403 AUT-ERR-006 → 마지막 관리자 409 ACC-ERR-002 순으로 본다.
   * 바뀌었으면 감사 로그(user.role_update, 변경 전 · 후 역할)를 같은 트랜잭션에 남긴다. 같은 역할이면 아무것도 바꾸지 않는다.
   */
  @Transactional
  public User changeRole(Long actorId, Long targetId, Role newRole) {
    // 관리자 행을 먼저, 대상 행을 그다음에 잠근다. 모든 역할 변경이 같은 순서로 잠가 서로 교착하지 않는다.
    List<User> admins = userRepository.findByRoleForUpdate(Role.admin);
    User target = userRepository.findForUpdate(targetId)
        .orElseThrow(() -> new ApiException(ErrorCode.USER_NOT_FOUND));
    // 요청자 역할은 잠근 뒤에 다시 읽는다 — 그사이 강등됐으면 강등된 역할로 판단한다
    Role actorRole = userRepository.findById(actorId).map(User::getRole)
        .orElseThrow(() -> new ApiException(ErrorCode.UNAUTHORIZED));
    if (!actorRole.canChangeRole(target.getRole(), newRole)) {
      throw new ApiException(ErrorCode.FORBIDDEN);
    }

    Role before = target.getRole();
    if (before == newRole) {
      return target;
    }
    // 활성 관리자가 없으면 메인테이너를 부여하거나 관리자를 새로 만들 계정이 없어 되돌릴 수 없다 — 메인테이너가 남아 있어도 같다.
    // 비활성 관리자는 로그인하지 못하므로 세지 않는다
    long activeAdmins = admins.stream().filter(User::isActive).count();
    if (before == Role.admin && target.isActive() && activeAdmins <= 1) {
      throw new ApiException(ErrorCode.LAST_ADMIN);
    }
    target.changeRole(newRole);
    auditLogRepository.save(AuditLog.byUser(actorId, AUDIT_ACTION_ROLE_UPDATE, "user:" + target.getId(),
        Map.of("before", before.name(), "after", newRole.name())));
    return target;
  }

  /**
   * 리서처 계정의 활성 상태 변경. 없는 계정 404 ACC-ERR-001, 관리자 · 메인테이너 계정이면 요청자가 관리자여도 403 AUT-ERR-006.
   * 요청자는 관리자 · 메인테이너뿐이라 자기 계정이나 마지막 관리자를 비활성화하는 경우는 생기지 않는다.
   * 바뀌었으면 감사 로그(user.active_update, 변경 전 · 후)를 남긴다. 같은 상태면 아무것도 바꾸지 않는다.
   */
  @Transactional
  public User changeActive(Long actorId, Long targetId, boolean active) {
    // 대상 행을 잠근다 — 동시에 들어온 역할 변경(리서처 → 관리자)과 차례로 처리돼, 리서처인지 확인한 뒤 역할이 바뀌지 않는다
    User target = userRepository.findForUpdate(targetId)
        .orElseThrow(() -> new ApiException(ErrorCode.USER_NOT_FOUND));
    if (target.getRole() != Role.researcher) {
      throw new ApiException(ErrorCode.FORBIDDEN);
    }

    boolean before = target.isActive();
    if (before == active) {
      return target;
    }
    target.changeActive(active);
    auditLogRepository.save(AuditLog.byUser(actorId, AUDIT_ACTION_ACTIVE_UPDATE, "user:" + target.getId(),
        Map.of("before", before, "after", active)));
    return target;
  }
}
