package com.uxight.api.domain.finding;

import java.util.List;

/** 진단 목록 — 회차 정보와 그 회차의 진단 전체(검출 순). 검출된 Friction 이 없으면 findings 가 비어 있다. */
public record FindingList(RoundInfo run, List<Summary> findings) {

  /**
   * 회차 정보. 진단 결과 메뉴로 다시 들어온 화면을 runId 하나로 다시 그리는 데 쓴다.
   *
   * @param round            실험 안에서 몇 번째 회차인지
   * @param improvementCount 이 회차의 개선안 수. '개선안 확인' 버튼을 켤지 정한다
   */
  public record RoundInfo(long firstRunId, int round, String projectTitle, String taskGoal, int improvementCount) {
  }

  public record Summary(long findingId, Taxonomy taxonomy, String severity, String summary) {
  }
}
