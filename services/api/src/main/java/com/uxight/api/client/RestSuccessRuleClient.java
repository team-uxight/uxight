package com.uxight.api.client;

import com.uxight.api.common.ApiException;
import com.uxight.api.common.ErrorCode;
import com.uxight.api.domain.task.SuccessRuleClient;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.MediaType;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientResponseException;

import java.net.SocketTimeoutException;
import java.util.Map;

/**
 * 성공 기준 생성 Agent 호출 POST /success-rules (내부 API 0, GACA-216). 실험 요청 처리 중 트랜잭션 밖에서 동기로 부른다.
 * 실패 응답 · 연결 실패 · 빈 문장은 502(EXP-ERR-007), 응답 대기 시간 초과는 504(EXP-ERR-008).
 * AI 모듈의 오류 본문(detail)은 로그에만 남기고 프론트엔드에는 보내지 않는다 (design-decision 9).
 */
@Component
@Slf4j
public class RestSuccessRuleClient implements SuccessRuleClient {

  // 연결 대기(ms). AI 모듈이 꺼져 있으면 빨리 502 로 끝낸다
  private static final int CONNECT_TIMEOUT_MILLIS = 5000;

  // 응답 대기(ms). AI 모듈은 LLM 호출 하나를 20초로 끊고 한 번 다시 보낸다(최대 약 40초) — 그보다 조금 길게.
  // 프론트엔드가 먼저 끊으면 리서처는 실패로 보는데 실험은 생기므로, 프론트엔드 요청 타임아웃보다 짧아야 한다
  private static final int READ_TIMEOUT_MILLIS = 45000;

  // 실패 응답 원문은 한 줄로 줄여 이 길이까지만 남긴다
  private static final int DETAIL_MAX_LENGTH = 500;

  // HttpURLConnection 은 연결 시간 초과도 SocketTimeoutException 으로 알린다 — 메시지로 응답 대기 시간 초과와 가른다
  private static final String CONNECT_TIMED_OUT = "Connect timed out";

  private final String agentBaseUrl;
  private final RestClient restClient;

  @Autowired
  public RestSuccessRuleClient(@Value("${uxight.agent-base-url}") String agentBaseUrl,
      @Value("${uxight.internal-token}") String internalToken) {
    this(agentBaseUrl, internalToken, READ_TIMEOUT_MILLIS);
  }

  // 테스트가 응답 대기 시간을 짧게 준다
  RestSuccessRuleClient(String agentBaseUrl, String internalToken, int readTimeoutMillis) {
    this.agentBaseUrl = agentBaseUrl;

    // RestAgentClient 와 같은 HttpURLConnection — 꺼진 AI 모듈을 연결 실패(502)로 정확히 가른다
    SimpleClientHttpRequestFactory requestFactory = new SimpleClientHttpRequestFactory();
    requestFactory.setConnectTimeout(CONNECT_TIMEOUT_MILLIS);
    requestFactory.setReadTimeout(readTimeoutMillis);

    this.restClient = RestClient.builder()
        .baseUrl(agentBaseUrl)
        .requestFactory(requestFactory)
        .defaultHeader(RestAgentClient.INTERNAL_TOKEN_HEADER, internalToken)   // 토큰 값은 로그에 남기지 않는다
        .build();
  }

  @Override
  public String createSuccessRule(String targetUrl, String goal, String successUrl) {
    // 내부 API JSON 은 snake_case. 목표 문장 · 생성된 문장은 로그에 남기지 않는다
    Map<String, String> requestBody = Map.of(
        "target_url", targetUrl,
        "goal", goal,
        "success_url", successUrl);

    log.info("POST {}/success-rules targetUrl={} successUrl={}", agentBaseUrl, targetUrl, successUrl);
    SuccessRuleResponse response;
    try {
      response = restClient.post()
          .uri("/success-rules")
          .contentType(MediaType.APPLICATION_JSON)
          .body(requestBody)
          .retrieve()
          .body(SuccessRuleResponse.class);
    } catch (RestClientResponseException e) {
      // 실패 응답(401 토큰 다름 · 422 · 5xx)
      throw failure(ErrorCode.SUCCESS_RULE_FAILED, e.getStatusCode().value(), e.getResponseBodyAsString(), e);
    } catch (Exception e) {
      // 응답 대기 시간 초과만 504. 연결 시간 초과 · 연결 거부 · 읽을 수 없는 본문은 502.
      // 시간 초과는 ResourceAccessException 으로도, 본문을 읽다가 난 RestClientException 으로도 온다 — 원인을 따라가 본다
      throw failure(isReadTimeout(e) ? ErrorCode.SUCCESS_RULE_TIMEOUT : ErrorCode.SUCCESS_RULE_FAILED, null,
          e.getMessage(), e);
    }

    if (response == null || response.success_rule() == null || response.success_rule().isBlank()) {
      throw failure(ErrorCode.SUCCESS_RULE_FAILED, null, "empty success_rule", null);
    }
    log.info("AI module returned a success rule ({} chars)", response.success_rule().length());
    return response.success_rule().strip();
  }

  private static boolean isReadTimeout(Throwable e) {
    for (Throwable t = e; t != null; t = t.getCause()) {
      if (t instanceof SocketTimeoutException) {
        return !CONNECT_TIMED_OUT.equals(t.getMessage());
      }
    }
    return false;
  }

  private ApiException failure(ErrorCode code, Integer httpStatus, String detail, Throwable e) {
    log.warn("{} {} http_status={} detail={} exception={}", code.code(), code.message(), httpStatus,
        abbreviate(detail), e == null ? null : e.getClass().getName());
    return new ApiException(code);
  }

  private static String abbreviate(String text) {
    if (text == null) {
      return null;
    }
    String oneLine = text.replaceAll("\\s+", " ").strip();
    return oneLine.length() <= DETAIL_MAX_LENGTH ? oneLine : oneLine.substring(0, DETAIL_MAX_LENGTH) + "…";
  }

  /** AI 모듈 응답 본문. 내부 API JSON 은 snake_case 라 칸 이름을 그대로 둔다. */
  record SuccessRuleResponse(String success_rule) {
  }
}
