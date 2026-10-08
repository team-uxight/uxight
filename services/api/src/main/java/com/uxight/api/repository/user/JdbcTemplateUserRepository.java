package com.uxight.api.repository.user;

import com.uxight.api.domain.user.User;
import com.uxight.api.domain.user.UserRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

import java.util.Optional;

@Repository
public class JdbcTemplateUserRepository implements UserRepository {

  private static final UserRowMapper ROW_MAPPER = new UserRowMapper();

  private final JdbcTemplate jdbcTemplate;

  @Autowired
  public JdbcTemplateUserRepository(JdbcTemplate jdbcTemplate) {
    this.jdbcTemplate = jdbcTemplate;
  }

  @Override
  public Optional<User> findById(Long userId) {
    return jdbcTemplate
      .query("SELECT * FROM users WHERE user_id = ?", ROW_MAPPER, userId)
      .stream()
      .findFirst();
  }

  @Override
  public Optional<User> findByEmail(String email) {
    return jdbcTemplate
      .query("SELECT * FROM users WHERE email = ?", ROW_MAPPER, email)
      .stream()
      .findFirst();
  }
}
