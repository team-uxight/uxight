package com.uxight.api.run;

import java.time.Duration;
import java.util.Map;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

/**
 * Spring → Python 은 호출 하나: "실행 시작" (fire-and-forget).
 * 이후 상태는 agent 가 MySQL 에 쓰고 api 는 읽기만 한다 (tech-stack §4, T17).
 */
@Component
public class AgentClient {
  private static final Logger log = LoggerFactory.getLogger(AgentClient.class);

  /** agent 가 죽어 있어도 요청 스레드가 묶이지 않도록 짧게 — 어차피 202 만 받는다. */
  private static final Duration CONNECT_TIMEOUT = Duration.ofSeconds(2);
  private static final Duration READ_TIMEOUT = Duration.ofSeconds(3);

  private final RestClient http;

  public AgentClient(@Value("${uxight.agent-base-url}") String agentBaseUrl) {
    SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
    factory.setConnectTimeout(CONNECT_TIMEOUT);
    factory.setReadTimeout(READ_TIMEOUT);
    this.http = RestClient.builder().baseUrl(agentBaseUrl).requestFactory(factory).build();
  }

  /**
   * 요청 스레드 밖(@Async)에서 돈다 — POST /api/runs 는 agent 응답을 기다리지 않는다.
   * 실패해도 예외를 밖으로 내지 않는다: run 은 QUEUED 로 남고 운영자가 본다.
   */
  @Async
  public void startRun(Run run) {
    try {
      http.post()
          .uri("/runs")
          .body(Map.of("run_id", run.getId(), "target_url", run.getTargetUrl(), "task", run.getTask()))
          .retrieve()
          .toBodilessEntity();
      log.info("agent 호출 성공 run={}", run.getId());
    } catch (RuntimeException e) {
      log.warn("agent 호출 실패 run={} : {}", run.getId(), e.getMessage());
    }
  }
}
