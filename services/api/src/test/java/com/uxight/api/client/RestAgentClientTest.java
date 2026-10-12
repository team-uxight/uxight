package com.uxight.api.client;

import static org.assertj.core.api.Assertions.assertThat;

import com.sun.net.httpserver.HttpServer;
import com.uxight.api.domain.run.DispatchState;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;

import java.io.IOException;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.Optional;
import java.util.concurrent.atomic.AtomicReference;

/**
 * POST /runs 요청 형식(X-Internal-Token · {run_id})과 응답 → dispatch_state 변환을 본다.
 * 로컬 HTTP 서버를 AI 모듈 대역으로 띄운다. Spring 없이 직접 만들어 @Async 를 거치지 않는다.
 */
class RestAgentClientTest {

  private static final String TOKEN = "test-internal-token";

  private HttpServer server;
  private final AtomicReference<String> receivedToken = new AtomicReference<>();
  private final AtomicReference<String> receivedBody = new AtomicReference<>();
  private int responseStatus;

  @BeforeEach
  void setUp() throws IOException {
    server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
    server.createContext("/runs", exchange -> {
      receivedToken.set(exchange.getRequestHeaders().getFirst(RestAgentClient.INTERNAL_TOKEN_HEADER));
      receivedBody.set(new String(exchange.getRequestBody().readAllBytes(), StandardCharsets.UTF_8));
      exchange.sendResponseHeaders(responseStatus, -1);
      exchange.close();
    });
    server.start();
  }

  @AfterEach
  void tearDown() {
    server.stop(0);
  }

  @ParameterizedTest(name = "{0} → {1}")
  @CsvSource({
      "202, sent",          // 새로 접수
      "200, ",              // 이미 받은 회차 — dispatch_state 를 건드리지 않는다
      "401, unreachable",   // 토큰이 다름
      "404, unreachable",
      "500, unreachable"
  })
  void dispatch_sendsInternalTokenAndRunId_andMapsStatus(int status, DispatchState expected) throws Exception {
    responseStatus = status;
    RestAgentClient client = new RestAgentClient("http://127.0.0.1:" + server.getAddress().getPort(), TOKEN);

    Optional<DispatchState> result = client.dispatch(42L).get();

    assertThat(receivedToken.get()).isEqualTo(TOKEN);
    assertThat(receivedBody.get()).isEqualTo("{\"run_id\":42}");
    assertThat(result).isEqualTo(Optional.ofNullable(expected));
  }

  @Test
  void dispatch_whenAgentIsDown_returnsUnreachable() throws Exception {
    int port = server.getAddress().getPort();
    server.stop(0);   // 아무도 듣지 않는 포트
    RestAgentClient client = new RestAgentClient("http://127.0.0.1:" + port, TOKEN);

    assertThat(client.dispatch(42L).get()).contains(DispatchState.unreachable);
  }
}
