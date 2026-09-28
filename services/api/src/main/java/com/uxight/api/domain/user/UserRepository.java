package com.uxight.api.domain.user;

import java.util.Optional;

public interface UserRepository {

  Optional<User> findByEmail(String email);
}
