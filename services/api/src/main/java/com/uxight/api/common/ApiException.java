package com.uxight.api.common;

import java.util.Map;

/** 서비스 · 인터셉터가 던지는 예외. GlobalExceptionHandler 가 ErrorCode 의 상태 코드와 공통 본문으로 바꾼다. */
public class ApiException extends RuntimeException {

  private final ErrorCode errorCode;
  private final Map<String, String> fieldErrors;   // GLB-ERR-002 일 때만. 필드 이름 → 사유

  public ApiException(ErrorCode errorCode) {
    this(errorCode, Map.of());
  }

  private ApiException(ErrorCode errorCode, Map<String, String> fieldErrors) {
    super(errorCode.code());
    this.errorCode = errorCode;
    this.fieldErrors = fieldErrors;
  }

  /** Bean Validation 으로 표현하기 어려운 필드 간 검증 (예: mode=loop 이면 loopMax 필수). */
  public static ApiException invalidField(String field, String message) {
    return new ApiException(ErrorCode.INVALID_INPUT, Map.of(field, message));
  }

  public ErrorCode errorCode() {
    return errorCode;
  }

  public Map<String, String> fieldErrors() {
    return fieldErrors;
  }
}
