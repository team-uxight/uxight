package com.uxight.api.domain.user;

import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;

/** save · findById 는 JpaRepository 가 제공한다. */
public interface UserRepository extends JpaRepository<User, Long> {

  Optional<User> findByEmail(String email);

  Optional<User> findByGoogleSub(String googleSub);
}
