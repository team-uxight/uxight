package com.uxight.api.domain.user;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.transaction.annotation.Transactional;

import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;

/** 실제 MySQL 에 붙는다. 테스트마다 롤백한다. */
@SpringBootTest
@Transactional
class UserRepositoryTest {

  @Autowired
  private UserRepository userRepository;

  @Test
  void save_signUpUser_startsAsActiveLocalResearcher() {
    Long id = userRepository.save(User.signUp("new-user@uxight.com", "hashed", "새 사용자")).getId();

    User found = userRepository.findById(id).orElseThrow();
    assertThat(found.getEmail()).isEqualTo("new-user@uxight.com");
    assertThat(found.getPasswordHash()).isEqualTo("hashed");
    assertThat(found.getName()).isEqualTo("새 사용자");
    assertThat(found.getRole()).isEqualTo(Role.researcher);
    assertThat(found.getAuthProvider()).isEqualTo(AuthProvider.local);
    assertThat(found.isActive()).isTrue();
  }

  @Test
  void findByEmail_returnsSeedUser() {
    Optional<User> found = userRepository.findByEmail("test@uxight.com");

    assertThat(found).isPresent();
    assertThat(found.get().getEmail()).isEqualTo("test@uxight.com");
    assertThat(found.get().getName()).isEqualTo("재완");
    assertThat(found.get().getRole()).isEqualTo(Role.researcher);
  }

  @Test
  void findByEmail_returnsEmpty_whenNotFound() {
    Optional<User> found = userRepository.findByEmail("no-such-user@uxight.com");

    assertThat(found).isEmpty();
  }
}
