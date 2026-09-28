package com.uxight.api.domain.user;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;

@SpringBootTest
class UserRepositoryTest {

  @Autowired
  private UserRepository userRepository;

  @Test
  void findByEmail_returnsSeedUser() {
    Optional<User> found = userRepository.findByEmail("test@uxight.com");

    assertThat(found).isPresent();
    assertThat(found.get().email()).isEqualTo("test@uxight.com");
    assertThat(found.get().name()).isEqualTo("재완");
  }

  @Test
  void findByEmail_returnsEmpty_whenNotFound() {
    Optional<User> found = userRepository.findByEmail("no-such-user@uxight.com");

    assertThat(found).isEmpty();
  }
}
