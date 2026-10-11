package com.uxight.api.web.common;

import com.uxight.api.common.ErrorCode;

import java.util.List;

/** 모든 API 의 실패 응답 본문 (code, message, fieldErrors). fieldErrors 는 GLB-ERR-002 가 아니면 빈 목록. */
public record ErrorResponse(String code, String message, List<FieldError> fieldErrors) {

  public record FieldError(String field, String message) {
  }

  public static ErrorResponse of(ErrorCode errorCode) {
    return of(errorCode, List.of());
  }

  public static ErrorResponse of(ErrorCode errorCode, List<FieldError> fieldErrors) {
    return new ErrorResponse(errorCode.code(), errorCode.message(), fieldErrors);
  }
}
