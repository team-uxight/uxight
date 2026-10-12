package com.uxight.api.client;

import com.uxight.api.domain.task.SuccessRuleClient;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

/**
 * 성공 기준 생성 Agent 대역. AI 모듈의 POST /success-rules 가 구현되기 전까지 쓴다 (GACA-102 결정: mock).
 * 입력으로 정해진 문장을 만들어 돌려주고 실패하지 않는다. 실제 호출로 바꿀 때 X-Internal-Token · 타임아웃 · 502/504 변환을 넣는다.
 */
@Component
@Slf4j
public class MockSuccessRuleClient implements SuccessRuleClient {

  @Override
  public String createSuccessRule(String targetUrl, String goal, String successUrl) {
    log.info("POST /success-rules (mock) targetUrl={} successUrl={}", targetUrl, successUrl);
    return "[mock] " + successUrl + " 에 도달하면 목표(" + goal + ")를 이룬 것으로 본다.";
  }
}
