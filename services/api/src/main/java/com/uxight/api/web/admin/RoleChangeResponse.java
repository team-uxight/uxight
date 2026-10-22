package com.uxight.api.web.admin;

import com.uxight.api.domain.user.Role;

public record RoleChangeResponse(Long userId, Role role) {
}
