package com.uxight.api.web.persona;

import static org.assertj.core.api.Assertions.assertThat;
import static org.hamcrest.Matchers.contains;
import static org.hamcrest.Matchers.hasItem;
import static org.hamcrest.Matchers.hasItems;
import static org.hamcrest.Matchers.hasSize;
import static org.hamcrest.Matchers.not;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.jayway.jsonpath.JsonPath;
import com.uxight.api.domain.user.JwtProvider;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.ResultActions;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.List;

/**
 * Persona 목록(GET /api/personas) — 본인 소유 + 공용, 삭제된 것 제외. 실제 MySQL, 테스트마다 롤백.
 * 로컬 seed 의 공용 Persona 도 함께 조회되므로, 테스트가 넣은 id 로만 판정한다.
 */
@SpringBootTest
@AutoConfigureMockMvc
@Transactional
class PersonaControllerTest {

  private static final String PROFILE =
      "{\"webSkill\":\"low\",\"device\":\"mobile\",\"domainKnowledge\":\"low\",\"background\":\"온라인 쇼핑 경험이 적음\"}";

  @Autowired
  private MockMvc mvc;

  @Autowired
  private JwtProvider jwtProvider;

  @Autowired
  private JdbcTemplate jdbcTemplate;

  private Long userId;
  private String bearer;

  @BeforeEach
  void setUp() {
    userId = insertUser("persona-owner@uxight.com");
    bearer = "Bearer " + jwtProvider.createAccessToken(userId);
  }

  @Test
  void list_returnsOwnAndCommon_excludesOthersAndDeleted() throws Exception {
    Long own = insertPersona(userId, "내 Persona", false);
    Long common = insertPersona(null, "공용 Persona", false);
    Long ownDeleted = insertPersona(userId, "삭제한 내 Persona", true);
    Long commonDeleted = insertPersona(null, "삭제된 공용 Persona", true);
    Long others = insertPersona(insertUser("other@uxight.com"), "남의 Persona", false);

    personas()
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.personas[*].personaId").value(hasItems(own.intValue(), common.intValue())))
        .andExpect(jsonPath("$.personas[*].personaId").value(not(hasItem(ownDeleted.intValue()))))
        .andExpect(jsonPath("$.personas[*].personaId").value(not(hasItem(commonDeleted.intValue()))))
        .andExpect(jsonPath("$.personas[*].personaId").value(not(hasItem(others.intValue()))));
  }

  @Test
  void list_returnsFieldsAndCommonFlag() throws Exception {
    Long own = insertPersona(userId, "내 Persona", false);
    Long common = insertPersona(null, "공용 Persona", false);

    personas()
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.personas[?(@.personaId == %d)].*", own).value(hasSize(4)))   // 4필드만
        .andExpect(jsonPath("$.personas[?(@.personaId == %d)].name", own).value(contains("내 Persona")))
        .andExpect(jsonPath("$.personas[?(@.personaId == %d)].isCommon", own).value(contains(false)))
        .andExpect(jsonPath("$.personas[?(@.personaId == %d)].isCommon", common).value(contains(true)))
        // profile 은 문자열이 아니라 JSON 객체로 내려간다
        .andExpect(jsonPath("$.personas[?(@.personaId == %d)].profile.webSkill", own).value(contains("low")))
        .andExpect(jsonPath("$.personas[?(@.personaId == %d)].profile.background", own)
            .value(contains("온라인 쇼핑 경험이 적음")));
  }

  @Test
  void list_keepsUnknownProfileKeys() throws Exception {
    // profile 키 구성이 바뀌어도(GACA-66) 저장된 키를 그대로 내려준다
    jdbcTemplate.update("INSERT INTO personas (user_id, name, profile) VALUES (?, '새 키', ?)",
        userId, "{\"ageGroup\":20,\"behaviorInstruction\":[\"메뉴가 모호하면 헤맨다\"]}");
    Long id = jdbcTemplate.queryForObject("SELECT LAST_INSERT_ID()", Long.class);

    personas()
        .andExpect(jsonPath("$.personas[?(@.personaId == %d)].profile.ageGroup", id).value(contains(20)))
        .andExpect(jsonPath("$.personas[?(@.personaId == %d)].profile.behaviorInstruction[0]", id)
            .value(contains("메뉴가 모호하면 헤맨다")));
  }

  @Test
  void list_isOrderedByPersonaId() throws Exception {
    Long first = insertPersona(userId, "먼저", false);
    Long second = insertPersona(null, "나중", false);

    String body = personas().andReturn().getResponse().getContentAsString();
    List<Integer> ids = JsonPath.read(body, "$.personas[*].personaId");
    assertThat(ids).containsSubsequence(first.intValue(), second.intValue());
    assertThat(ids).isSorted();
  }

  @Test
  void list_withoutTokenOrByInactiveUser_returnsUnauthorized() throws Exception {
    mvc.perform(get("/api/personas"))
        .andExpect(status().isUnauthorized())
        .andExpect(jsonPath("$.code").value("AUT-ERR-001"));

    jdbcTemplate.update("UPDATE users SET is_active = FALSE WHERE user_id = ?", userId);
    personas()
        .andExpect(status().isUnauthorized())
        .andExpect(jsonPath("$.code").value("AUT-ERR-005"));
  }

  @Test
  void experimentRequest_withDeletedOrOthersPersona_returnsPersonaNotFound() throws Exception {
    // 실험 요청도 같은 조회(본인 + 공용, 삭제 제외)로 Persona 를 확인한다
    jdbcTemplate.update("INSERT INTO projects (user_id, title, target_url, allowed_domains) "
        + "VALUES (?, 'p', 'https://a.example.com', JSON_ARRAY('a.example.com'))", userId);
    Long projectId = jdbcTemplate.queryForObject("SELECT LAST_INSERT_ID()", Long.class);
    Long deleted = insertPersona(userId, "삭제함", true);
    Long others = insertPersona(insertUser("other@uxight.com"), "남의 것", false);

    for (Long personaId : new Long[] {deleted, others}) {
      mvc.perform(post("/api/projects/{projectId}/runs", projectId).header(HttpHeaders.AUTHORIZATION, bearer)
              .contentType(MediaType.APPLICATION_JSON)
              .content("{\"goal\":\"구매\",\"successUrl\":\"https://a.example.com/done\",\"personaIds\":[" + personaId
                  + "],\"mode\":\"diagnose\"}"))
          .andExpect(status().isNotFound())
          .andExpect(jsonPath("$.code").value("EXP-ERR-003"));
    }
  }

  private ResultActions personas() throws Exception {
    return mvc.perform(get("/api/personas").header(HttpHeaders.AUTHORIZATION, bearer));
  }

  private Long insertUser(String email) {
    jdbcTemplate.update("INSERT INTO users (email, password_hash, auth_provider, name, role, is_active) "
        + "VALUES (?, 'hash', 'local', '홍길동', 'researcher', TRUE)", email);
    return jdbcTemplate.queryForObject("SELECT user_id FROM users WHERE email = ?", Long.class, email);
  }

  private Long insertPersona(Long ownerId, String name, boolean deleted) {
    jdbcTemplate.update("INSERT INTO personas (user_id, name, profile, deleted_at) VALUES (?, ?, ?, ?)",
        ownerId, name, PROFILE, deleted ? LocalDateTime.now() : null);
    return jdbcTemplate.queryForObject("SELECT LAST_INSERT_ID()", Long.class);
  }
}
