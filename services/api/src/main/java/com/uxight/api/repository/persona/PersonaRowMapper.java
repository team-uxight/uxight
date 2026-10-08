package com.uxight.api.repository.persona;

import com.uxight.api.domain.persona.Persona;
import org.springframework.jdbc.core.RowMapper;

import java.sql.ResultSet;
import java.sql.SQLException;

public class PersonaRowMapper implements RowMapper<Persona> {

  @Override
  public Persona mapRow(ResultSet rs, int rowNum) throws SQLException {
    return new Persona(
        rs.getLong("persona_id"),
        (Long) rs.getObject("user_id"),
        rs.getString("name"),
        rs.getString("profile"),
        rs.getTimestamp("created_at").toLocalDateTime(),
        rs.getTimestamp("updated_at").toLocalDateTime()
    );
  }
}
