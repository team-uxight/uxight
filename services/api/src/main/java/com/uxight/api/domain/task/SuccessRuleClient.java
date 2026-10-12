package com.uxight.api.domain.task;

/**
 * 성공 기준 생성 Agent 호출 POST /success-rules (내부 API 0). 실험 요청 처리 중 트랜잭션 밖에서 동기로 부른다.
 * AI 모듈은 DB 에 쓰지 않고 성공 기준만 돌려준다 — tasks.success_rule 저장은 Spring 이 한다.
 * 실패 응답 · 연결 실패는 ApiException(SUCCESS_RULE_FAILED, 502), 응답 시간 초과는 ApiException(SUCCESS_RULE_TIMEOUT, 504).
 * AI 모듈이 돌려준 오류 본문(detail)은 프론트엔드에 전달하지 않는다 (design-decision 9).
 */
public interface SuccessRuleClient {

  String createSuccessRule(String targetUrl, String goal, String successUrl);
}
