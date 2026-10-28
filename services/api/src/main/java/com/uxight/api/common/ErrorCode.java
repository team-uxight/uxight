package com.uxight.api.common;

import org.springframework.http.HttpStatus;

/** 오류 코드 (설계 8.4.1). 지금 구현된 API 가 내는 코드만 둔다 — 기능을 추가할 때 표에서 옮겨 온다. */
public enum ErrorCode {

  BAD_REQUEST(HttpStatus.BAD_REQUEST, "GLB-ERR-001", "잘못된 요청입니다."),
  INVALID_INPUT(HttpStatus.BAD_REQUEST, "GLB-ERR-002", "입력값이 올바르지 않습니다."),
  API_NOT_FOUND(HttpStatus.NOT_FOUND, "GLB-ERR-003", "존재하지 않는 API입니다."),
  METHOD_NOT_ALLOWED(HttpStatus.METHOD_NOT_ALLOWED, "GLB-ERR-004", "허용되지 않은 메서드입니다."),
  INTERNAL_ERROR(HttpStatus.INTERNAL_SERVER_ERROR, "GLB-ERR-005", "내부 서버 오류입니다."),

  UNAUTHORIZED(HttpStatus.UNAUTHORIZED, "AUT-ERR-001", "인증이 필요합니다."),
  LOGIN_FAILED(HttpStatus.UNAUTHORIZED, "AUT-ERR-002", "이메일 또는 비밀번호가 올바르지 않습니다."),
  GOOGLE_AUTH_FAILED(HttpStatus.UNAUTHORIZED, "AUT-ERR-003", "Google 인증에 실패했습니다."),
  REFRESH_TOKEN_INVALID(HttpStatus.UNAUTHORIZED, "AUT-ERR-004", "로그인이 만료되었습니다."),
  ACCOUNT_DISABLED(HttpStatus.UNAUTHORIZED, "AUT-ERR-005", "비활성화된 계정입니다."),
  FORBIDDEN(HttpStatus.FORBIDDEN, "AUT-ERR-006", "권한이 없습니다."),
  EMAIL_DUPLICATED(HttpStatus.CONFLICT, "AUT-ERR-007", "이미 가입된 이메일입니다."),
  EMAIL_ACCOUNT_EXISTS(HttpStatus.CONFLICT, "AUT-ERR-008", "이메일로 가입된 계정입니다. 이메일로 로그인해 주세요."),

  USER_NOT_FOUND(HttpStatus.NOT_FOUND, "ACC-ERR-001", "계정을 찾을 수 없습니다."),
  LAST_ADMIN(HttpStatus.CONFLICT, "ACC-ERR-002", "마지막 관리자의 역할은 변경할 수 없습니다."),
  NOT_CHANGE_TARGET(HttpStatus.CONFLICT, "ACC-ERR-003", "해당 계정은 변경 대상이 아닙니다."),

  PROJECT_NOT_FOUND(HttpStatus.NOT_FOUND, "PRJ-ERR-001", "프로젝트를 찾을 수 없습니다."),

  EXPERIMENT_NOT_FOUND(HttpStatus.NOT_FOUND, "EXP-ERR-001", "실험을 찾을 수 없습니다."),
  RUN_NOT_FOUND(HttpStatus.NOT_FOUND, "EXP-ERR-002", "회차를 찾을 수 없습니다."),
  PERSONA_NOT_FOUND(HttpStatus.NOT_FOUND, "EXP-ERR-003", "Persona를 찾을 수 없습니다."),
  EXPERIMENT_IN_PROGRESS(HttpStatus.CONFLICT, "EXP-ERR-004", "프로젝트에 진행 중인 실험이 있습니다."),
  NOT_CANCELLABLE(HttpStatus.CONFLICT, "EXP-ERR-006", "취소할 수 있는 실험이 아닙니다."),
  SUCCESS_RULE_FAILED(HttpStatus.BAD_GATEWAY, "EXP-ERR-007", "성공 기준 생성에 실패했습니다."),
  SUCCESS_RULE_TIMEOUT(HttpStatus.GATEWAY_TIMEOUT, "EXP-ERR-008", "성공 기준 생성 시간이 초과되었습니다."),

  FINDING_NOT_FOUND(HttpStatus.NOT_FOUND, "FND-ERR-001", "진단을 찾을 수 없습니다."),

  IMPROVEMENT_NOT_FOUND(HttpStatus.NOT_FOUND, "IMP-ERR-001", "개선안을 찾을 수 없습니다."),
  NOT_DECIDABLE(HttpStatus.CONFLICT, "IMP-ERR-002", "다음 회차를 승인하거나 반려할 수 없는 상태입니다."),

  STEP_LOG_NOT_FOUND(HttpStatus.NOT_FOUND, "LOG-ERR-001", "step 로그를 찾을 수 없습니다."),
  SCREENSHOT_NOT_FOUND(HttpStatus.NOT_FOUND, "LOG-ERR-002", "스크린샷을 찾을 수 없습니다."),

  // HTTP 응답이 없는 오류 — 실험 요청 · 다음 회차 승인에 이미 201 을 응답한 뒤 생긴다. 예외로 던지지 않고 로그와
  // runs.dispatch_state 에만 남긴다(오류 파일은 추후). 전달하지 못한 회차는 재전송 스케줄러가 다시 보낸다 (8.4.1).
  AGENT_DISPATCH_FAILED(null, "INT-ERR-004", "AI 모듈에 회차 실행 요청을 전달하지 못했습니다.");

  private final HttpStatus status;
  private final String code;
  private final String message;

  ErrorCode(HttpStatus status, String code, String message) {
    this.status = status;
    this.code = code;
    this.message = message;
  }

  /** HTTP 로 응답하는 오류만 값이 있다. INT-ERR-004 처럼 응답 없이 기록만 하는 오류는 null. */
  public HttpStatus status() {
    return status;
  }

  public String code() {
    return code;
  }

  public String message() {
    return message;
  }
}
