package com.uxight.api.web.common;

import com.uxight.api.common.ApiException;
import com.uxight.api.common.ErrorCode;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.ResponseEntity;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.web.HttpRequestMethodNotSupportedException;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.MissingServletRequestParameterException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.method.annotation.MethodArgumentTypeMismatchException;
import org.springframework.web.servlet.resource.NoResourceFoundException;

import java.util.List;

/** 예외를 공통 실패 본문으로 바꾼다. 화면 이동은 FE 가 정하므로 리다이렉트하지 않는다 (design-decision §8). */
@RestControllerAdvice
public class GlobalExceptionHandler {

  private static final Logger log = LoggerFactory.getLogger(GlobalExceptionHandler.class);

  @ExceptionHandler(ApiException.class)
  public ResponseEntity<ErrorResponse> handleApi(ApiException e) {
    List<ErrorResponse.FieldError> fieldErrors = e.fieldErrors().entrySet().stream()
        .map(entry -> new ErrorResponse.FieldError(entry.getKey(), entry.getValue()))
        .toList();
    return respond(e.errorCode(), fieldErrors);
  }

  @ExceptionHandler(MethodArgumentNotValidException.class)
  public ResponseEntity<ErrorResponse> handleInvalid(MethodArgumentNotValidException e) {
    List<ErrorResponse.FieldError> fieldErrors = e.getBindingResult().getFieldErrors().stream()
        .map(error -> new ErrorResponse.FieldError(error.getField(), error.getDefaultMessage()))
        .toList();
    return respond(ErrorCode.INVALID_INPUT, fieldErrors);
  }

  @ExceptionHandler({HttpMessageNotReadableException.class, MethodArgumentTypeMismatchException.class,
      MissingServletRequestParameterException.class})
  public ResponseEntity<ErrorResponse> handleBadRequest(Exception e) {
    return respond(ErrorCode.BAD_REQUEST, List.of());
  }

  @ExceptionHandler(NoResourceFoundException.class)
  public ResponseEntity<ErrorResponse> handleNoResource(NoResourceFoundException e) {
    return respond(ErrorCode.API_NOT_FOUND, List.of());
  }

  @ExceptionHandler(HttpRequestMethodNotSupportedException.class)
  public ResponseEntity<ErrorResponse> handleMethod(HttpRequestMethodNotSupportedException e) {
    return respond(ErrorCode.METHOD_NOT_ALLOWED, List.of());
  }

  @ExceptionHandler(Exception.class)
  public ResponseEntity<ErrorResponse> handleUnexpected(Exception e) {
    log.error("Unhandled exception", e);
    return respond(ErrorCode.INTERNAL_ERROR, List.of());
  }

  private ResponseEntity<ErrorResponse> respond(ErrorCode errorCode, List<ErrorResponse.FieldError> fieldErrors) {
    return ResponseEntity.status(errorCode.status()).body(ErrorResponse.of(errorCode, fieldErrors));
  }
}
