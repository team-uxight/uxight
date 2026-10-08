package com.uxight.api.web.auth;

import jakarta.validation.constraints.NotBlank;

public record LoginRequest(
    @NotBlank String email,
    String password
) {
}
