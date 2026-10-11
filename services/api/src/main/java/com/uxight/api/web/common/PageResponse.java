package com.uxight.api.web.common;

import java.util.List;

/** 페이지 응답. 목록(content)과 페이지 정보를 같은 단계에 담는다. page 는 0부터. */
public record PageResponse<T>(List<T> content, int page, int size, long totalElements, int totalPages) {

  public static <T> PageResponse<T> of(List<T> content, int page, int size, long totalElements) {
    return new PageResponse<>(content, page, size, totalElements, (int) ((totalElements + size - 1) / size));
  }
}
