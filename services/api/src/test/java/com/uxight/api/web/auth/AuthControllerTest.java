package com.uxight.api.web.auth;

import static org.hamcrest.Matchers.containsInAnyOrder;
import static org.hamcrest.Matchers.empty;
import static org.hamcrest.Matchers.notNullValue;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.ResultActions;
import org.springframework.transaction.annotation.Transactional;

/** POST /api/auth/signup 의 요청 · 응답이 설계(7.3 · 8.4)와 같은지 본다. 실제 MySQL, 테스트마다 롤백. */
@SpringBootTest
@AutoConfigureMockMvc
@Transactional
class AuthControllerTest {

  @Autowired
  private MockMvc mvc;

  @Test
  void signup_created() throws Exception {
    signup("""
        {"email": "researcher@uxight.com", "password": "password12", "name": "홍길동"}
        """)
        .andExpect(status().isCreated())
        .andExpect(jsonPath("$.userId").value(notNullValue()));
  }

  @Test
  void signup_invalidInput_returnsFieldErrors() throws Exception {
    signup("""
        {"email": "not-an-email", "password": "", "name": "홍길동"}
        """)
        .andExpect(status().isBadRequest())
        .andExpect(jsonPath("$.code").value("GLB-ERR-002"))
        .andExpect(jsonPath("$.message").value("입력값이 올바르지 않습니다."))
        .andExpect(jsonPath("$.fieldErrors[*].field").value(containsInAnyOrder("email", "password")));
  }

  // 8~12자 · 영어 소문자 포함 · 숫자 포함 중 하나라도 어기면 거절한다
  @ParameterizedTest
  @ValueSource(strings = {"pass123", "password12345", "passwordab", "12345678", "PASSWORD12"})
  void signup_passwordRuleViolation_returnsFieldError(String password) throws Exception {
    signup("""
        {"email": "researcher@uxight.com", "password": "%s", "name": "홍길동"}
        """.formatted(password))
        .andExpect(status().isBadRequest())
        .andExpect(jsonPath("$.code").value("GLB-ERR-002"))
        .andExpect(jsonPath("$.fieldErrors[0].field").value("password"))
        .andExpect(jsonPath("$.fieldErrors[0].message").value("비밀번호는 영어 소문자와 숫자를 포함한 8~12자여야 합니다"));
  }

  @ParameterizedTest
  @ValueSource(strings = {"abcdefg1", "Password1234"})   // 경계값 8자 · 12자(대문자 허용)
  void signup_passwordRuleBoundary_created(String password) throws Exception {
    signup("""
        {"email": "researcher@uxight.com", "password": "%s", "name": "홍길동"}
        """.formatted(password))
        .andExpect(status().isCreated());
  }

  @Test
  void signup_malformedBody_returnsBadRequest() throws Exception {
    signup("{\"email\": ")
        .andExpect(status().isBadRequest())
        .andExpect(jsonPath("$.code").value("GLB-ERR-001"))
        .andExpect(jsonPath("$.message").value("잘못된 요청입니다."))
        .andExpect(jsonPath("$.fieldErrors").value(empty()));
  }

  @Test
  void signup_duplicateEmail_returnsConflict() throws Exception {
    signup("""
        {"email": "test@uxight.com", "password": "password12", "name": "중복"}
        """)
        .andExpect(status().isConflict())
        .andExpect(jsonPath("$.code").value("AUT-ERR-007"))
        .andExpect(jsonPath("$.message").value("이미 가입된 이메일입니다."))
        .andExpect(jsonPath("$.fieldErrors").value(empty()));
  }

  private ResultActions signup(String body) throws Exception {
    return mvc.perform(post("/api/auth/signup").contentType(MediaType.APPLICATION_JSON).content(body));
  }
}
