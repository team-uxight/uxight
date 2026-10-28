package com.uxight.api.repository.result;

import com.uxight.api.domain.improvement.PatchKind;
import com.uxight.api.domain.result.Comparison;
import com.uxight.api.domain.result.PatchVersionQueryRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public class JdbcTemplatePatchVersionQueryRepository implements PatchVersionQueryRepository {

  // 다음 회차는 이전 회차가 끝나고 승인된 뒤에만 생기므로 run_id 순서가 회차 순서와 같다 (회차 목록 SQL 과 같은 규칙)
  private static final String SQL = """
      SELECT r.round_no, pv.patch_kind, pv.applied
        FROM patch_versions pv
        JOIN (SELECT run_id, ROW_NUMBER() OVER (ORDER BY run_id) AS round_no
                FROM runs
               WHERE first_run_id = ?) r ON r.run_id = pv.run_id
       ORDER BY pv.run_id, pv.patch_version_id
      """;

  private final JdbcTemplate jdbcTemplate;

  @Autowired
  public JdbcTemplatePatchVersionQueryRepository(JdbcTemplate jdbcTemplate) {
    this.jdbcTemplate = jdbcTemplate;
  }

  @Override
  public List<Comparison.AppliedPatch> findByFirstRunId(long firstRunId) {
    return jdbcTemplate.query(SQL, (rs, rowNum) -> new Comparison.AppliedPatch(
        rs.getInt("round_no"), PatchKind.valueOf(rs.getString("patch_kind")), rs.getBoolean("applied")), firstRunId);
  }
}
