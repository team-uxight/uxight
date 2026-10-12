package com.uxight.api.client;

import static org.assertj.core.api.Assertions.assertThat;

import com.sun.net.httpserver.HttpServer;
import com.uxight.api.domain.run.DispatchState;
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
import java.util.Optional;
import java.util.concurrent.atomic.AtomicReference;

/**
 * POST /runs 요청 형식(X-Internal-Token · {run_id}), 응답 → dispatch_state 변환, 전달 실패 기록(INT-ERR-004)을 본다.
 * 로컬 HTTP 서버를 AI 모듈 대역으로 띄운다. Spring 없이 직접 만들어 @Async 를 거치지 않는다.
 */
@ExtendWith(OutputCaptureExtension.class)
class RestAgentClientTest {

  private static final String TOKEN = "test-internal-token";

  private HttpServer server;
  private final AtomicReference<String> receivedToken = new AtomicReference<>();
  private final AtomicReference<String> receivedBody = new AtomicReference<>();
  private int responseStatus;
  private String responseBody;
  private long responseDelayMillis;

  @BeforeEach
  void setUp() throws IOException {
    server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
    server.createContext("/runs", exchange -> {
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

  @ParameterizedTest(name = "{0} → sent")
  @CsvSource({
      "202",   // 새로 접수
      "200"    // 이미 받은 회차(멱등) — 첫 호출이 timeout 이었어도 전달은 된 것이다
  })
  void dispatch_acceptedOrAlreadyAccepted_isSent_andLogsNoError(int status, CapturedOutput output) throws Exception {
    responseStatus = status;

    Optional<DispatchState> result = client().dispatch(42L).get();

    assertThat(receivedToken.get()).isEqualTo(TOKEN);
    assertThat(receivedBody.get()).isEqualTo("{\"run_id\":42}");
    assertThat(result).contains(DispatchState.sent);
    assertThat(output).doesNotContain("INT-ERR-004");
  }

  @Test
  void dispatch_tokenRejected_isUnreachable_andLogsStatusWithoutBody(CapturedOutput output) throws Exception {
    responseStatus = 401;   // 토큰이 다름
    responseBody = "{\"detail\":\"invalid internal token\"}";

    assertThat(client().dispatch(42L).get()).contains(DispatchState.unreachable);

    // HttpURLConnection 은 401 을 인증 재시도 신호로 다뤄 본문을 버린다 — 상태 코드만 남는다
    assertThat(output)
        .contains("INT-ERR-004 AI 모듈에 회차 실행 요청을 전달하지 못했습니다. run_id=42 dispatch_state=unreachable http_status=401")
        .doesNotContain(TOKEN);
  }

  @ParameterizedTest(name = "{0} → unreachable")
  @CsvSource({
      "404, '{\"detail\":\"run not found\"}'",
      "500, Internal Server Error"                         // 처리되지 않은 예외는 평문이 올 수 있다
  })
  void dispatch_failureResponse_isUnreachable_andLogsIntErr004WithDetail(int status, String body, CapturedOutput output)
      throws Exception {
    responseStatus = status;
    responseBody = body;

    assertThat(client().dispatch(42L).get()).contains(DispatchState.unreachable);

    assertThat(output)
        .contains("INT-ERR-004 AI 모듈에 회차 실행 요청을 전달하지 못했습니다. run_id=42 dispatch_state=unreachable")
        .contains("http_status=" + status)
        .contains("detail=" + body)
        .doesNotContain(TOKEN);   // 요청 헤더(X-Internal-Token) 값은 남기지 않는다
  }

  @Test
  void dispatch_whenAgentIsDown_isUnreachable_andLogsIntErr004(CapturedOutput output) throws Exception {
    int port = server.getAddress().getPort();
    server.stop(0);   // 아무도 듣지 않는 포트

    assertThat(new RestAgentClient("http://127.0.0.1:" + port, TOKEN).dispatch(42L).get())
        .contains(DispatchState.unreachable);
    assertThat(output)
        .contains("INT-ERR-004")
        .contains("run_id=42 dispatch_state=unreachable http_status=null")
        .doesNotContain(TOKEN);
  }

  @Test
  void dispatch_whenConnectionCannotBeMade_isUnreachable_notTimeout(CapturedOutput output) throws Exception {
    // 응답하지 않는 주소(라우팅되지 않는 사설 IP) — 연결 시간 초과든 즉시 연결 실패든 요청은 닿지 않았다.
    // 연결 시간 초과(HttpConnectTimeoutException)는 HttpTimeoutException 의 하위 타입이라 timeout 으로 잘못 분류하기 쉽다.
    assertThat(new RestAgentClient("http://10.255.255.1:8000", TOKEN).dispatch(42L).get())
        .contains(DispatchState.unreachable);
    assertThat(output).contains("run_id=42 dispatch_state=unreachable http_status=null");
  }

  @Test
  void dispatch_whenAgentDoesNotAnswerInTime_isTimeout_andLogsIntErr004(CapturedOutput output) throws Exception {
    responseStatus = 202;
    responseDelayMillis = 6000;   // 응답 대기 시간(5초)보다 늦게 — 받았을 수도 있지만 확인하지 못했다

    assertThat(client().dispatch(42L).get()).contains(DispatchState.timeout);
    assertThat(output).contains("INT-ERR-004").contains("run_id=42 dispatch_state=timeout http_status=null");
  }

  private RestAgentClient client() {
    return new RestAgentClient("http://127.0.0.1:" + server.getAddress().getPort(), TOKEN);
  }
}
