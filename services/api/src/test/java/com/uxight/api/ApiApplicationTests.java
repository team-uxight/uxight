package com.uxight.api;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.servlet.http.Cookie;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MvcResult;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.request.MockHttpServletRequestBuilder;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
class ApiApplicationTests {
  @Autowired MockMvc mvc;
  @Autowired ObjectMapper objectMapper;

  @Test
  void health() throws Exception {
    mvc.perform(get("/api/health")).andExpect(status().isOk()).andExpect(jsonPath("$.status").value("ok"));
  }

  @Test
  void createRun_persistsEvenWhenAgentIsDown() throws Exception {
    AuthSession session = createAuthSession();
    mvc.perform(withBearer(post("/api/runs").contentType(MediaType.APPLICATION_JSON)
            .content("{\"targetUrl\":\"https://example.com\",\"task\":\"t\"}"), session.accessToken()))
        .andExpect(status().isAccepted())
        .andExpect(jsonPath("$.status").value("QUEUED"));
    mvc.perform(withBearer(get("/api/runs/1"), session.accessToken()))
        .andExpect(status().isOk()).andExpect(jsonPath("$.task").value("t"));
  }

  @Test
  void createRun_rejectsNonHttpScheme() throws Exception {
    AuthSession session = createAuthSession();
    mvc.perform(withBearer(post("/api/runs").contentType(MediaType.APPLICATION_JSON)
            .content("{\"targetUrl\":\"file:///etc/passwd\",\"task\":\"t\"}"), session.accessToken()))
        .andExpect(status().isBadRequest());
    mvc.perform(withBearer(post("/api/runs").contentType(MediaType.APPLICATION_JSON)
            .content("{\"targetUrl\":\"not-a-url\",\"task\":\"t\"}"), session.accessToken()))
        .andExpect(status().isBadRequest());
  }

  @Test
  void signupLoginMeAndLogout() throws Exception {
    AuthSession session = createAuthSession();

    mvc.perform(withBearer(get("/api/users/me"), session.accessToken()))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.name").value("Test User"))
        .andExpect(jsonPath("$.role").value("researcher"));
    mvc.perform(get("/api/users/me")).andExpect(status().isUnauthorized());

    mvc.perform(post("/api/auth/logout").cookie(session.refreshCookie()))
        .andExpect(status().isNoContent());

    mvc.perform(post("/api/auth/refresh").cookie(session.refreshCookie()))
        .andExpect(status().isUnauthorized());
  }

  private AuthSession createAuthSession() throws Exception {
    String email = UUID.randomUUID() + "@example.com";
    mvc.perform(post("/api/auth/signup").contentType(MediaType.APPLICATION_JSON)
            .content(objectMapper.writeValueAsString(
                new SignupBody(email, "password1", "Test User"))))
        .andExpect(status().isCreated());

    MvcResult result = mvc.perform(post("/api/auth/login").contentType(MediaType.APPLICATION_JSON)
            .content(objectMapper.writeValueAsString(
                new LoginBody(email, "password1"))))
        .andExpect(status().isOk())
        .andReturn();

    String accessToken = objectMapper.readTree(result.getResponse().getContentAsString())
        .get("accessToken").asText();
    Cookie refreshCookie = result.getResponse().getCookie("refreshToken");
    if (refreshCookie == null) {
      throw new AssertionError("Login did not set a refresh-token cookie");
    }
    return new AuthSession(accessToken, refreshCookie);
  }

  private static MockHttpServletRequestBuilder withBearer(
      MockHttpServletRequestBuilder request, String accessToken) {
    return request.header(HttpHeaders.AUTHORIZATION, "Bearer " + accessToken);
  }

  private record SignupBody(String email, String password, String name) {}

  private record LoginBody(String email, String password) {}

  private record AuthSession(String accessToken, Cookie refreshCookie) {}
}
