package com.uxight.api.client;

import com.uxight.api.common.ErrorCode;
import com.uxight.api.domain.run.AgentClient;
import com.uxight.api.domain.run.DispatchState;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Component;
import org.springframework.web.client.ResourceAccessException;
import org.springframework.web.client.RestClientResponseException;
import org.springframework.web.client.RestClient;

import java.net.SocketTimeoutException;
import java.util.Map;
import java.util.Optional;
import java.util.concurrent.CompletableFuture;

@Component
@Slf4j
public class RestAgentClient implements AgentClient {

  /** 내부 API 공유 토큰 헤더. AI 모듈은 자기 환경 변수 값과 다르면 401 을 응답한다 (design-decision 9). */
  public static final String INTERNAL_TOKEN_HEADER = "X-Internal-Token";

  // 실패 응답 원문은 한 줄로 줄여 이 길이까지만 남긴다 — 로그 한 줄이 한 건이 되게
  private static final int DETAIL_MAX_LENGTH = 500;

  // 연결 · 응답 대기 시간(ms). 재전송 기준 시간(uxight.redispatch.stale-after, 30초)보다 짧아야 한다
  private static final int TIMEOUT_MILLIS = 5000;

  // HttpURLConnection 은 연결 시간 초과도 SocketTimeoutException 으로 알린다 — 메시지로 응답 대기 시간 초과와 가른다
  private static final String CONNECT_TIMED_OUT = "Connect timed out";

  private final String agentBaseUrl;
  private final RestClient restClient;

  @Autowired
  public RestAgentClient(@Value("${uxight.agent-base-url}") String agentBaseUrl,
      @Value("${uxight.internal-token}") String internalToken) {
    this.agentBaseUrl = agentBaseUrl;

    // HttpURLConnection. 주소 찾기(DNS)가 시간 제한 밖에서 끝나 AI 모듈이 꺼져 있으면 unreachable 로 정확히 드러난다.
    // 대신 401 은 인증 재시도 신호로 다뤄 응답 본문을 버린다 — 401 은 http_status 만 남는다 (내부 API 에서 401 은 토큰 다름뿐).
    // JDK HttpClient 는 401 본문을 주지만 응답 대기 시간이 주소 찾기부터 재여서, 꺼진 AI 모듈을 timeout 으로 잘못 기록한다.
    SimpleClientHttpRequestFactory requestFactory = new SimpleClientHttpRequestFactory();
    requestFactory.setConnectTimeout(TIMEOUT_MILLIS);
    requestFactory.setReadTimeout(TIMEOUT_MILLIS);

    this.restClient = RestClient.builder()
        .baseUrl(agentBaseUrl)
        .requestFactory(requestFactory)
        .defaultHeader(INTERNAL_TOKEN_HEADER, internalToken)   // 토큰 값은 로그에 남기지 않는다
        .build();
  }

  // 요청 스레드 밖에서 돈다 — 실험 요청은 Python 응답을 기다리지 않는다.
  @Async
  @Override
  public CompletableFuture<Optional<DispatchState>> dispatch(Long runId) {
    return CompletableFuture.completedFuture(send(runId));
  }

  private Optional<DispatchState> send(Long runId) {
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
      // 202(새로 접수) · 200(이미 받은 회차, 멱등) 모두 AI 모듈이 회차를 갖고 있다 — sent (내부 API 명세).
      // 200 도 기록한다: 첫 호출이 timeout 이었다가 재전송에서 200 을 받으면 실제로는 전달된 것이다.
      return Optional.of(DispatchState.sent);
    } catch (RestClientResponseException e) {
      // 실패 응답(401 토큰 다름 · 404 회차 없음 · 5xx) — AI 모듈의 응답 원문(detail, 401 은 비어 있다)은 기록만 하고 프론트엔드에는 보내지 않는다
      return Optional.of(logDispatchFailure(runId, DispatchState.unreachable, e.getStatusCode().value(),
          e.getResponseBodyAsString(), e));
    } catch (ResourceAccessException e) {
      // 연결 실패 · 응답 대기 시간 초과 — 응답이 없으므로 http_status 도 없다.
      // 응답 대기 시간 초과만 timeout(받았을 수도 있다). 연결 시간 초과는 요청이 닿지 않은 것이라 unreachable 이다.
      Throwable cause = e.getCause() != null ? e.getCause() : e;
      boolean isTimeout = cause instanceof SocketTimeoutException && !CONNECT_TIMED_OUT.equals(cause.getMessage());
      return Optional.of(logDispatchFailure(runId, isTimeout ? DispatchState.timeout : DispatchState.unreachable,
          null, e.getMessage(), cause));
    } catch (Exception e) {
      return Optional.of(logDispatchFailure(runId, DispatchState.unreachable, null, e.getMessage(), e));
    }
  }

  /**
   * INT-ERR-004 — 회차 실행 요청을 전달하지 못했거나 전달됐는지 확인하지 못했다. 이미 201 을 응답한 뒤라 HTTP 응답은 없고,
   * dispatch_state 와 이 로그에만 남는다. 한 줄에 오류 파일(8.4.2)의 필드를 담아 두어, 오류 파일을 만들 때 그대로 옮긴다.
   * 요청 헤더(X-Internal-Token)는 남기지 않는다.
   */
  private DispatchState logDispatchFailure(Long runId, DispatchState state, Integer httpStatus, String detail,
      Throwable e) {
    ErrorCode code = ErrorCode.AGENT_DISPATCH_FAILED;
    log.warn("{} {} run_id={} dispatch_state={} http_status={} detail={} exception={}", code.code(), code.message(),
        runId, state, httpStatus, abbreviate(detail), e.getClass().getName());
    return state;
  }

  private static String abbreviate(String text) {
    if (text == null) {
      return null;
    }
    String oneLine = text.replaceAll("\\s+", " ").strip();
    return oneLine.length() <= DETAIL_MAX_LENGTH ? oneLine : oneLine.substring(0, DETAIL_MAX_LENGTH) + "…";
  }
}
