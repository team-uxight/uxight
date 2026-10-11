package com.uxight.api.client;

import com.uxight.api.domain.run.AgentClient;
import lombok.extern.slf4j.Slf4j;
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
@Slf4j
public class RestAgentClient implements AgentClient {

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

  // 요청 스레드 밖에서 돈다 — 실험 요청은 Python 응답을 기다리지 않는다.
  @Async
  @Override
  public CompletableFuture<Optional<String>> dispatch(Long runId) {
    return CompletableFuture.completedFuture(send(runId));
  }

  private Optional<String> send(Long runId) {
    // 스냅샷은 runs 행에 있으므로 run_id 만 보낸다 (내부 API 1). 내부 API JSON 은 snake_case.
    Map<String, Object> requestBody = Map.of("run_id", runId);

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
      // 200: 이미 받은 회차에 대한 멱등 응답 — 최초 수락 때 이미 "sent"로 기록되어 있으므로 건드리지 않는다.
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
