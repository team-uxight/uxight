package com.uxight.api;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.web.servlet.MockMvc;

/** 실제 MySQL 에 붙는다 (DB_URL · DB_USER · DB_PASSWORD). 컨텍스트 기동 + 로그인 없이 열린 health 확인. */
@SpringBootTest
@AutoConfigureMockMvc
class ApiApplicationTests {
  @Autowired MockMvc mvc;

  @Test
  void health() throws Exception {
    mvc.perform(get("/api/health")).andExpect(status().isOk()).andExpect(jsonPath("$.status").value("ok"));
  }
}
