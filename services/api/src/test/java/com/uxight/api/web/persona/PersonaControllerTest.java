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

import com.fasterxml.jackson.databind.ObjectMapper;
import com.jayway.jsonpath.JsonPath;
import com.uxight.api.domain.user.JwtProvider;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.Arguments;
import org.junit.jupiter.params.provider.MethodSource;
import org.junit.jupiter.params.provider.ValueSource;
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
import java.util.Map;
import java.util.stream.Stream;

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

  @Autowired
  private ObjectMapper objectMapper;

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

  // ───────── POST /api/personas ─────────

  @Test
  void create_savesWithRequesterAsOwner_andKeepsExtraKeys() throws Exception {
    String body = create("{\"name\":\"쇼핑 초보\",\"profile\":{\"webSkill\":\"low\",\"device\":\"mobile\","
        + "\"domainKnowledge\":\"low\",\"background\":\"온라인 쇼핑 경험이 적음\",\"ageGroup\":20}}")
        .andExpect(status().isCreated())
        .andExpect(jsonPath("$.*", hasSize(1)))
        .andExpect(jsonPath("$.personaId").isNumber())
        .andReturn().getResponse().getContentAsString();
    long personaId = objectMapper.readTree(body).get("personaId").asLong();

    Map<String, Object> row = jdbcTemplate.queryForMap(
        "SELECT user_id, name, deleted_at, profile FROM personas WHERE persona_id = ?", personaId);
    assertThat(row.get("user_id")).isEqualTo(userId);
    assertThat(row.get("name")).isEqualTo("쇼핑 초보");
    assertThat(row.get("deleted_at")).isNull();
    assertThat(objectMapper.readValue(row.get("profile").toString(), Map.class))
        .containsEntry("background", "온라인 쇼핑 경험이 적음")
        .containsEntry("ageGroup", 20);   // 필수 속성 밖의 키도 그대로 저장한다

    personas()
        .andExpect(jsonPath("$.personas[?(@.personaId == %d)].isCommon", personaId).value(contains(false)));
  }

  @Test
  void create_sameNameAndProfileTwice_createsTwoPersonas() throws Exception {
    String json = "{\"name\":\"같은 이름\",\"profile\":" + PROFILE + "}";

    create(json).andExpect(status().isCreated());
    create(json).andExpect(status().isCreated());

    assertThat(jdbcTemplate.queryForObject(
        "SELECT COUNT(*) FROM personas WHERE user_id = ? AND name = '같은 이름'", Integer.class, userId)).isEqualTo(2);
  }

  @ParameterizedTest(name = "[{index}] {1}")
  @MethodSource("invalidCreateRequests")
  void create_invalidInput_returnsInvalidInput_andSavesNothing(String json, List<String> fields) throws Exception {
    create(json)
        .andExpect(status().isBadRequest())
        .andExpect(jsonPath("$.code").value("GLB-ERR-002"))
        .andExpect(jsonPath("$.fieldErrors[*].field").value(contains(fields.toArray())));
    assertThat(jdbcTemplate.queryForObject("SELECT COUNT(*) FROM personas WHERE user_id = ?", Integer.class, userId))
        .isZero();
  }

  static Stream<Arguments> invalidCreateRequests() {
    String profile = "\"profile\":" + PROFILE;
    return Stream.of(
        Arguments.of("{" + profile + "}", List.of("name")),
        Arguments.of("{\"name\":\"\"," + profile + "}", List.of("name")),
        Arguments.of("{\"name\":\"   \"," + profile + "}", List.of("name")),
        Arguments.of("{\"name\":\" 앞 공백\"," + profile + "}", List.of("name")),
        Arguments.of("{\"name\":\"" + "가".repeat(101) + "\"," + profile + "}", List.of("name")),
        Arguments.of("{\"name\":\"n\"}", List.of("profile")),
        // 필수 속성은 빠진 것을 모두 한 번에 알린다
        Arguments.of("{\"name\":\"n\",\"profile\":{}}",
            List.of("profile.webSkill", "profile.device", "profile.domainKnowledge", "profile.background")),
        Arguments.of("{\"name\":\"n\",\"profile\":{\"webSkill\":\"low\",\"device\":null,\"domainKnowledge\":\"low\","
            + "\"background\":\"  \"}}", List.of("profile.device", "profile.background")));
  }

  @ParameterizedTest
  @ValueSource(strings = {"{\"name\":", "{\"name\":\"n\",\"profile\":\"문자열\"}", "{\"name\":\"n\",\"profile\":[]}"})
  void create_unreadableBody_returnsBadRequest(String json) throws Exception {
    create(json)
        .andExpect(status().isBadRequest())
        .andExpect(jsonPath("$.code").value("GLB-ERR-001"));
  }

  @Test
  void create_withoutTokenOrByInactiveUser_returnsUnauthorized() throws Exception {
    String json = "{\"name\":\"n\",\"profile\":" + PROFILE + "}";
    mvc.perform(post("/api/personas").contentType(MediaType.APPLICATION_JSON).content(json))
        .andExpect(status().isUnauthorized())
        .andExpect(jsonPath("$.code").value("AUT-ERR-001"));

    jdbcTemplate.update("UPDATE users SET is_active = FALSE WHERE user_id = ?", userId);
    create(json)
        .andExpect(status().isUnauthorized())
        .andExpect(jsonPath("$.code").value("AUT-ERR-005"));
  }

  private ResultActions create(String json) throws Exception {
    return mvc.perform(post("/api/personas").header(HttpHeaders.AUTHORIZATION, bearer)
        .contentType(MediaType.APPLICATION_JSON)
        .content(json));
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
