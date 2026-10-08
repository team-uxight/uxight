package com.uxight.api.repository.user;

import com.uxight.api.domain.user.User;
import org.springframework.jdbc.core.RowMapper;

import java.sql.ResultSet;
import java.sql.SQLException;

public class UserRowMapper implements RowMapper<User> {

  @Override
  public User mapRow(ResultSet rs, int rowNum) throws SQLException {
    return new User(
      rs.getLong("user_id"),
      rs.getString("email"),
      rs.getString("password_hash"),
      rs.getString("auth_provider"),
      rs.getString("google_sub"),
      rs.getString("name"),
      rs.getString("role"),
      rs.getBoolean("is_active"),
      rs.getTimestamp("created_at").toLocalDateTime(),
      rs.getTimestamp("updated_at").toLocalDateTime()
    );
  }
}
