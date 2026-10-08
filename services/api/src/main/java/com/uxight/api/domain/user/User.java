package com.uxight.api.domain.user;

import java.time.LocalDateTime;

public record User (
        Long userId,
        String email,
        String passwordHash,
        String authProvider,
        String googleSub,
        String name,
        String role,
        boolean isActive,
        LocalDateTime createdAt,
        LocalDateTime updatedAt
) {
}
