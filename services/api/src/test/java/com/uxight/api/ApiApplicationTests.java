package com.uxight.api;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
class ApiApplicationTests {
  @Autowired MockMvc mvc;

  @Test
  void health() throws Exception {
    mvc.perform(get("/api/health")).andExpect(status().isOk()).andExpect(jsonPath("$.status").value("ok"));
  }

  @Test
  void createRun_persistsEvenWhenAgentIsDown() throws Exception {
    mvc.perform(post("/api/runs").contentType(MediaType.APPLICATION_JSON)
            .content("{\"targetUrl\":\"https://example.com\",\"task\":\"t\"}"))
        .andExpect(status().isAccepted())
        .andExpect(jsonPath("$.status").value("QUEUED"));
    mvc.perform(get("/api/runs/1")).andExpect(status().isOk()).andExpect(jsonPath("$.task").value("t"));
  }

  @Test
  void createRun_rejectsNonHttpScheme() throws Exception {
    mvc.perform(post("/api/runs").contentType(MediaType.APPLICATION_JSON)
            .content("{\"targetUrl\":\"file:///etc/passwd\",\"task\":\"t\"}"))
        .andExpect(status().isBadRequest());
    mvc.perform(post("/api/runs").contentType(MediaType.APPLICATION_JSON)
            .content("{\"targetUrl\":\"not-a-url\",\"task\":\"t\"}"))
        .andExpect(status().isBadRequest());
  }
}
