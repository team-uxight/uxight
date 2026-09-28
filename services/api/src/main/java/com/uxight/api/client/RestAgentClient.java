package com.uxight.api.client;

import com.uxight.api.domain.run.AgentClient;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Component;
import org.springframework.web.client.ResourceAccessException;
import org.springframework.web.client.RestClient;

import java.net.SocketTimeoutException;
import java.util.Map;
import java.util.Optional;
import java.util.concurrent.CompletableFuture;

@Component
public class RestAgentClient implements AgentClient {

  private static final Logger log = LoggerFactory.getLogger(RestAgentClient.class);

  private final String agentBaseUrl;
  private final RestClient restClient;

  public RestAgentClient(@Value("${uxight.agent-base-url}") String agentBaseUrl) {
    this.agentBaseUrl = agentBaseUrl;

    SimpleClientHttpRequestFactory requestFactory = new SimpleClientHttpRequestFactory();
    requestFactory.setConnectTimeout(5000);
    requestFactory.setReadTimeout(5000);

    this.restClient = RestClient.builder()
        .baseUrl(agentBaseUrl)
        .requestFactory(requestFactory)
        .build();
  }

  // 요청 스레드 밖에서 돈다 — 런 생성 요청은 Python 응답을 기다리지 않는다.
  @Async
  @Override
  public CompletableFuture<Optional<String>> dispatch(Long runId, Object taskSnapshot, Object personaSnapshot,
      Object policySnapshot, Object allowedDomains) {
    return CompletableFuture.completedFuture(send(runId, taskSnapshot, personaSnapshot, policySnapshot, allowedDomains));
  }

  private Optional<String> send(Long runId, Object taskSnapshot, Object personaSnapshot, Object policySnapshot,
      Object allowedDomains) {
    Map<String, Object> requestBody = Map.of(
        "run_id", runId,
        "task_snapshot", taskSnapshot,
        "persona_snapshot", personaSnapshot,
        "policy_snapshot", policySnapshot,
        "allowed_domains", allowedDomains
    );

    log.info("POST {}/runs run_id={}", agentBaseUrl, runId);
    try {
      ResponseEntity<Void> response = restClient.post()
          .uri("/runs")
          .contentType(MediaType.APPLICATION_JSON)
          .body(requestBody)
          .retrieve()
          .toBodilessEntity();

      log.info("Python responded {} for run_id={}", response.getStatusCode(), runId);
      if (response.getStatusCode().value() == 202) {
        return Optional.of("sent");
      }
      // 200: 이미 처리된 run_id에 대한 멱등 응답 — 최초 수락 때 이미 "sent"로 기록되어 있으므로 건드리지 않는다.
      return Optional.empty();
    } catch (ResourceAccessException e) {
      boolean isTimeout = e.getCause() instanceof SocketTimeoutException;
      log.warn("Python {} for run_id={}: {}", isTimeout ? "timeout" : "unreachable", runId, e.getMessage());
      return Optional.of(isTimeout ? "timeout" : "unreachable");
    } catch (Exception e) {
      log.warn("Unexpected error dispatching run_id={}: {}", runId, e.getMessage());
      return Optional.of("unreachable");
    }
  }
}
