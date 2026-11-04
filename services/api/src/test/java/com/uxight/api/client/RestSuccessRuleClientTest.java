package com.uxight.api.client;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.sun.net.httpserver.HttpServer;
import com.uxight.api.common.ApiException;
import com.uxight.api.common.ErrorCode;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;
import org.springframework.boot.test.system.CapturedOutput;
import org.springframework.boot.test.system.OutputCaptureExtension;

import java.io.IOException;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.Map;
import java.util.concurrent.atomic.AtomicReference;

/**
 * POST /success-rules 요청 형식(X-Internal-Token · snake_case 본문), 응답 → 성공 기준 · 502 · 504 변환을 본다 (GACA-216).
 * 로컬 HTTP 서버를 AI 모듈 대역으로 띄운다. Spring 없이 직접 만든다.
 */
@ExtendWith(OutputCaptureExtension.class)
class RestSuccessRuleClientTest {

  private static final String TOKEN = "test-internal-token";
  private static final String GOAL = "학사일정을 확인한다";

  private HttpServer server;
  private final AtomicReference<String> receivedToken = new AtomicReference<>();
  private final AtomicReference<String> receivedBody = new AtomicReference<>();
  private int responseStatus;
  private String responseBody;
  private long responseDelayMillis;

  @BeforeEach
  void setUp() throws IOException {
    server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
    server.createContext("/success-rules", exchange -> {
      receivedToken.set(exchange.getRequestHeaders().getFirst(RestAgentClient.INTERNAL_TOKEN_HEADER));
      receivedBody.set(new String(exchange.getRequestBody().readAllBytes(), StandardCharsets.UTF_8));
      if (responseDelayMillis > 0) {
        try {
          Thread.sleep(responseDelayMillis);
        } catch (InterruptedException e) {
          Thread.currentThread().interrupt();
        }
      }
      byte[] body = responseBody == null ? new byte[0] : responseBody.getBytes(StandardCharsets.UTF_8);
      exchange.getResponseHeaders().set("Content-Type", "application/json");
      exchange.sendResponseHeaders(responseStatus, body.length == 0 ? -1 : body.length);
      if (body.length > 0) {
        exchange.getResponseBody().write(body);
      }
      exchange.close();
    });
    server.start();
  }

  @AfterEach
  void tearDown() {
    server.stop(0);
  }

  @Test
  void returnsSuccessRule_andSendsTokenAndSnakeCaseBody(CapturedOutput output) throws Exception {
    responseStatus = 200;
    responseBody = "{\"success_rule\":\"학사일정 페이지에 도달한다.\"}";

    String rule = client().createSuccessRule("https://www.gachon.ac.kr", GOAL, "https://www.gachon.ac.kr/kor/1075");

    assertThat(rule).isEqualTo("학사일정 페이지에 도달한다.");
    assertThat(receivedToken.get()).isEqualTo(TOKEN);
    assertThat(new ObjectMapper().readValue(receivedBody.get(), Map.class)).isEqualTo(Map.of(
        "target_url", "https://www.gachon.ac.kr",
        "goal", GOAL,
        "success_url", "https://www.gachon.ac.kr/kor/1075"));
    // 목표 문장 · 생성된 문장 · 토큰은 로그에 남기지 않는다
    assertThat(output).doesNotContain(GOAL).doesNotContain("학사일정 페이지에 도달한다.").doesNotContain(TOKEN);
  }

  @ParameterizedTest(name = "{0} {1} → 502")
  @CsvSource({
      "500, '{\"detail\":\"success rule generation failed\"}'",
      "502, '{\"detail\":\"success rule generation failed\"}'",
      "422, '{\"detail\":[]}'",
      "401, '{\"detail\":\"invalid internal token\"}'",
      "200, '{\"success_rule\":\"  \"}'",     // 빈 문장
      "200, '{}'",                             // 칸 없음
      "200, not json"                          // 읽을 수 없는 본문
  })
  void failureResponseOrEmptyRule_is502(int status, String body, CapturedOutput output) {
    responseStatus = status;
    responseBody = body;

    assertFailsWith(client(), ErrorCode.SUCCESS_RULE_FAILED);
    assertThat(output).contains("EXP-ERR-007").doesNotContain(TOKEN);
  }

  @Test
  void whenAgentIsDown_is502() {
    int port = server.getAddress().getPort();
    server.stop(0);   // 아무도 듣지 않는 포트

    assertFailsWith(new RestSuccessRuleClient("http://127.0.0.1:" + port, TOKEN, 1000),
        ErrorCode.SUCCESS_RULE_FAILED);
  }

  @Test
  void whenAgentDoesNotAnswerInTime_is504(CapturedOutput output) {
    responseStatus = 200;
    responseBody = "{\"success_rule\":\"학사일정 페이지에 도달한다.\"}";
    responseDelayMillis = 1500;   // 응답 대기 시간(1초)보다 늦게

    assertFailsWith(client(), ErrorCode.SUCCESS_RULE_TIMEOUT);
    assertThat(output).contains("EXP-ERR-008");
  }

  private void assertFailsWith(RestSuccessRuleClient client, ErrorCode code) {
    assertThatThrownBy(() -> client.createSuccessRule("https://a.example.com", GOAL, "https://a.example.com/done"))
        .isInstanceOfSatisfying(ApiException.class, e -> assertThat(e.errorCode()).isEqualTo(code));
  }

  private RestSuccessRuleClient client() {
    return new RestSuccessRuleClient("http://127.0.0.1:" + server.getAddress().getPort(), TOKEN, 1000);
  }
}
