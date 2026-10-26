package com.uxight.api.web.admin;

import static org.hamcrest.Matchers.contains;
import static org.hamcrest.Matchers.hasItem;
import static org.hamcrest.Matchers.hasSize;
import static org.hamcrest.Matchers.nullValue;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.patch;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.uxight.api.domain.user.JwtProvider;
import jakarta.persistence.EntityManager;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.ResultActions;
import org.springframework.transaction.annotation.Transactional;

import java.time.OffsetDateTime;

/**
 * 감사 로그 조회(GET /api/admin/audit-logs) — admin · maintainer 만. 기간 [from, to) 의 기록을 최근 기록 순으로 돌려준다.
 * 실제 MySQL, 테스트마다 롤백. 다른 기록과 섞이지 않게 2001년 시각으로 넣은 행을 2001년 기간으로 조회한다.
 */
@SpringBootTest
@AutoConfigureMockMvc
@Transactional
class AuditLogControllerTest {

  private static final String FROM_2001 = "2001-01-01T00:00:00+09:00";
  private static final String TO_2002 = "2002-01-01T00:00:00+09:00";

  @Autowired
  private MockMvc mvc;

  @Autowired
  private JwtProvider jwtProvider;

  @Autowired
  private JdbcTemplate jdbcTemplate;

  @Autowired
  private EntityManager entityManager;

  private Long adminId;

  @BeforeEach
  void setUp() {
    adminId = insertUser("audit-admin@uxight.com", "admin", true);
  }

  @Test
  void admin_getsLogsOfPeriod_newestFirst_withSixFields_includingAgentGuardBlock() throws Exception {
    Long policy = insertLog("user:" + adminId, "policy.update", "policy:1",
        "{\"changes\":{\"maxSteps\":{\"before\":10,\"after\":20}}}", "2001-03-01 10:00:00");
    Long guard = insertLog("agent:42", "guard.blocked", "https://evil.example.com",
        "{\"reason\":\"허용 도메인 밖\"}", "2001-03-02 10:00:00");   // AI 모듈이 남기는 가드 차단
    Long noTarget = insertLog("user:" + adminId, "run.cancel_all", null, null, "2001-03-03 10:00:00");

    audit(adminId, "from", FROM_2001, "to", TO_2002)
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.*", hasSize(5)))
        .andExpect(jsonPath("$.page").value(0))
        .andExpect(jsonPath("$.size").value(20))
        .andExpect(jsonPath("$.totalElements").value(3))
        .andExpect(jsonPath("$.totalPages").value(1))
        .andExpect(jsonPath("$.content[*].auditLogId").value(contains(noTarget.intValue(), guard.intValue(),
            policy.intValue())))
        .andExpect(jsonPath("$.content[2].*", hasSize(6)))
        .andExpect(jsonPath("$.content[2].actor").value("user:" + adminId))
        .andExpect(jsonPath("$.content[2].action").value("policy.update"))
        .andExpect(jsonPath("$.content[2].target").value("policy:1"))
        .andExpect(jsonPath("$.content[2].detail.changes.maxSteps.after").value(20))   // 객체 그대로
        .andExpect(jsonPath("$.content[2].ts").value("2001-03-01T10:00:00"))
        .andExpect(jsonPath("$.content[1].actor").value("agent:42"))
        .andExpect(jsonPath("$.content[1].action").value("guard.blocked"))
        .andExpect(jsonPath("$.content[0].target").value(nullValue()))
        .andExpect(jsonPath("$.content[0].detail").value(nullValue()));
  }

  @Test
  void fromIsInclusive_toIsExclusive_andOffsetIsConvertedToKst() throws Exception {
    Long atFrom = insertLog("user:1", "a", null, null, "2001-05-01 09:00:00");
    Long beforeTo = insertLog("user:1", "b", null, null, "2001-05-01 09:59:59");
    insertLog("user:1", "c", null, null, "2001-05-01 10:00:00");   // to 와 같은 시각 — 빠진다
    insertLog("user:1", "d", null, null, "2001-05-01 08:59:59");   // from 전

    // UTC 00:00 = KST 09:00, UTC 01:00 = KST 10:00
    audit(adminId, "from", "2001-05-01T00:00:00Z", "to", "2001-05-01T01:00:00Z")
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.content[*].auditLogId").value(contains(beforeTo.intValue(), atFrom.intValue())));
  }

  @Test
  void fromOnly_toOnly_andNeither() throws Exception {
    Long early = insertLog("user:1", "early", null, null, "2001-01-10 00:00:00");
    Long late = insertLog("user:1", "late", null, null, "2001-12-10 00:00:00");

    audit(adminId, "from", "2001-06-01T00:00:00+09:00", "to", TO_2002)
        .andExpect(jsonPath("$.content[*].auditLogId").value(contains(late.intValue())));
    audit(adminId, "from", FROM_2001, "to", "2001-06-01T00:00:00+09:00")
        .andExpect(jsonPath("$.content[*].auditLogId").value(contains(early.intValue())));
    // from 만: 2001-06 이후 전부(다른 테스트 · 실제 기록 포함) — 2001-01 기록은 없다
    audit(adminId, "from", "2001-06-01T00:00:00+09:00", "size", "1000")
        .andExpect(jsonPath("$.content[*].auditLogId").value(hasItem(late.intValue())))
        .andExpect(jsonPath("$.content[?(@.auditLogId == " + early + ")]").isEmpty());
    // to 만: 2001-06 이전 전부
    audit(adminId, "to", "2001-06-01T00:00:00+09:00", "size", "1000")
        .andExpect(jsonPath("$.content[*].auditLogId").value(hasItem(early.intValue())))
        .andExpect(jsonPath("$.content[?(@.auditLogId == " + late + ")]").isEmpty());
    // 둘 다 없으면 전체
    long total = jdbcTemplate.queryForObject("SELECT COUNT(*) FROM audit_log", Long.class);
    audit(adminId).andExpect(jsonPath("$.totalElements").value(total));
  }

  @Test
  void pagesBySize_sameTimestampOrderedByIdDesc() throws Exception {
    Long first = insertLog("user:1", "x", null, null, "2001-07-01 12:00:00");
    Long second = insertLog("user:1", "x", null, null, "2001-07-01 12:00:00");
    Long third = insertLog("user:1", "x", null, null, "2001-07-01 12:00:00");

    audit(adminId, "from", FROM_2001, "to", TO_2002, "page", "0", "size", "2")
        .andExpect(jsonPath("$.content[*].auditLogId").value(contains(third.intValue(), second.intValue())))
        .andExpect(jsonPath("$.totalElements").value(3))
        .andExpect(jsonPath("$.totalPages").value(2));
    audit(adminId, "from", FROM_2001, "to", TO_2002, "page", "1", "size", "2")
        .andExpect(jsonPath("$.page").value(1))
        .andExpect(jsonPath("$.content[*].auditLogId").value(contains(first.intValue())));
  }

  @Test
  void fromEqualToTo_isEmpty_butFromAfterTo_isBadRequest() throws Exception {
    insertLog("user:1", "x", null, null, "2001-08-01 00:00:00");
    audit(adminId, "from", "2001-08-01T00:00:00+09:00", "to", "2001-08-01T00:00:00+09:00")
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.content", hasSize(0)));
    audit(adminId, "from", TO_2002, "to", FROM_2001)
        .andExpect(status().isBadRequest())
        .andExpect(jsonPath("$.code").value("GLB-ERR-002"))
        .andExpect(jsonPath("$.fieldErrors[0].field").value("to"));
  }

  @ParameterizedTest(name = "[{index}] {0}={1} → {2}")
  @CsvSource({
      "from, 2001-01-01, GLB-ERR-001",              // 날짜만
      "to, 2001-01-01T00:00:00, GLB-ERR-001",       // 시간대 없음
      "from, yesterday, GLB-ERR-001",
      "page, abc, GLB-ERR-001",
      "page, -1, GLB-ERR-002",
      "size, 0, GLB-ERR-002"
  })
  void invalidParameter_isBadRequest(String name, String value, String code) throws Exception {
    ResultActions result = audit(adminId, name, value)
        .andExpect(status().isBadRequest())
        .andExpect(jsonPath("$.code").value(code));
    if (code.equals("GLB-ERR-002")) {
      result.andExpect(jsonPath("$.fieldErrors[0].field").value(name));
    }
  }

  @Test
  void maintainer_canRead_researcherIsForbidden() throws Exception {
    Long maintainer = insertUser("audit-maintainer@uxight.com", "maintainer", true);
    Long researcher = insertUser("audit-researcher@uxight.com", "researcher", true);
    insertLog("user:1", "x", null, null, "2001-09-01 00:00:00");

    audit(maintainer, "from", FROM_2001, "to", TO_2002)
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.totalElements").value(1));
    audit(researcher)
        .andExpect(status().isForbidden())
        .andExpect(jsonPath("$.code").value("AUT-ERR-006"));
  }

  @Test
  void withoutTokenOrByInactiveAdmin_isUnauthorized() throws Exception {
    mvc.perform(get("/api/admin/audit-logs"))
        .andExpect(status().isUnauthorized())
        .andExpect(jsonPath("$.code").value("AUT-ERR-001"));
    jdbcTemplate.update("UPDATE users SET is_active = FALSE WHERE user_id = ?", adminId);
    audit(adminId)
        .andExpect(status().isUnauthorized())
        .andExpect(jsonPath("$.code").value("AUT-ERR-005"));
  }

  /** 완료 기준: 운영 행위(정책 수정 · 역할 변경 · 활성 상태 변경)가 기록되고 관리자가 바로 조회한다. */
  @Test
  void operationsDoneThroughApi_areRecorded_andListedNewestFirst() throws Exception {
    Long researcher = insertUser("audit-target@uxight.com", "researcher", true);
    String from = OffsetDateTime.now().minusMinutes(1).toString();

    adminCall(patch("/api/admin/policy"), "{\"maxSteps\":11}").andExpect(status().isOk());
    adminCall(patch("/api/admin/users/{userId}/role", researcher), "{\"role\":\"maintainer\"}").andExpect(status().isOk());
    adminCall(patch("/api/admin/users/{userId}/role", researcher), "{\"role\":\"researcher\"}").andExpect(status().isOk());
    adminCall(patch("/api/admin/users/{userId}/active", researcher), "{\"isActive\":false}").andExpect(status().isOk());
    // 같은 트랜잭션에서 JPA 로 저장한 행은 ts(DB 기본값)가 비어 있다 — DB 에서 다시 읽게 한다
    entityManager.flush();
    entityManager.clear();

    audit(adminId, "from", from, "size", "4")
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.content[*].action").value(contains("user.active_update", "user.role_update",
            "user.role_update", "policy.update")))
        .andExpect(jsonPath("$.content[*].actor").value(contains("user:" + adminId, "user:" + adminId,
            "user:" + adminId, "user:" + adminId)))
        .andExpect(jsonPath("$.content[0].target").value("user:" + researcher))
        .andExpect(jsonPath("$.content[0].detail.before").value(true))
        .andExpect(jsonPath("$.content[0].detail.after").value(false))
        .andExpect(jsonPath("$.content[1].detail.after").value("researcher"))
        .andExpect(jsonPath("$.content[3].target").value("policy:1"))
        .andExpect(jsonPath("$.content[0].ts").isNotEmpty());
  }

  private ResultActions audit(Long userId, String... params) throws Exception {
    var request = get("/api/admin/audit-logs")
        .header(HttpHeaders.AUTHORIZATION, "Bearer " + jwtProvider.createAccessToken(userId));
    for (int i = 0; i < params.length; i += 2) {
      request.param(params[i], params[i + 1]);
    }
    return mvc.perform(request);
  }

  private ResultActions adminCall(
      org.springframework.test.web.servlet.request.MockHttpServletRequestBuilder request, String json) throws Exception {
    return mvc.perform(request.header(HttpHeaders.AUTHORIZATION, "Bearer " + jwtProvider.createAccessToken(adminId))
        .contentType(MediaType.APPLICATION_JSON).content(json));
  }

  private Long insertUser(String email, String role, boolean active) {
    jdbcTemplate.update("INSERT INTO users (email, password_hash, auth_provider, name, role, is_active) "
        + "VALUES (?, 'hash', 'local', '감사', ?, ?)", email, role, active);
    return jdbcTemplate.queryForObject("SELECT user_id FROM users WHERE email = ?", Long.class, email);
  }

  private Long insertLog(String actor, String action, String target, String detailJson, String ts) {
    jdbcTemplate.update("INSERT INTO audit_log (actor, action, target, detail, ts) VALUES (?, ?, ?, ?, ?)",
        actor, action, target, detailJson, ts);
    return jdbcTemplate.queryForObject("SELECT LAST_INSERT_ID()", Long.class);
  }
}
