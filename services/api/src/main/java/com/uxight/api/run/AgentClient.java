package com.uxight.api.run;

import java.util.Map;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

/**
 * Spring → Python 은 호출 하나: "실행 시작" (fire-and-forget).
 * 이후 상태는 agent 가 MySQL 에 쓰고 api 는 읽기만 한다 (tech-stack §4, T17).
 */
@Component
public class AgentClient {
  private static final Logger log = LoggerFactory.getLogger(AgentClient.class);
  private final RestClient http;

  public AgentClient(@Value("${uxight.agent-base-url}") String agentBaseUrl) {
    this.http = RestClient.builder().baseUrl(agentBaseUrl).build();
  }

  /** 실패해도 예외를 밖으로 내지 않는다 — run 은 QUEUED 로 남고 운영자가 본다. */
  public boolean startRun(Run run) {
    try {
      http.post()
          .uri("/runs")
          .body(Map.of("run_id", run.getId(), "target_url", run.getTargetUrl(), "task", run.getTask()))
          .retrieve()
          .toBodilessEntity();
      return true;
    } catch (RuntimeException e) {
      log.warn("agent 호출 실패 run={} : {}", run.getId(), e.getMessage());
      return false;
    }
  }
}
