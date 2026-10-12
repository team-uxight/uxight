package com.uxight.api.domain.run;

import java.time.OffsetDateTime;

/**
 * 실험 목록 조건. 값이 null 인 조건은 적용하지 않는다.
 *
 * @param state        in_progress · awaiting_approval · completed · stopped
 * @param keyword      프로젝트 제목 · Task 목표에서 찾는 문자열
 * @param finishedFrom 마지막 회차의 종료 시각이 이 시각 이후인 실험만
 */
public record ExperimentFilter(String state, String keyword, OffsetDateTime finishedFrom) {

  public static ExperimentFilter none() {
    return new ExperimentFilter(null, null, null);
  }
}
