package com.uxight.api.domain.improvement;

import java.util.List;

/** 개선안 목록 — 회차 정보와 그 회차의 개선안(안 번호 순). diagnose 실험의 회차 · 개선 대상 진단이 없는 회차는 비어 있다. */
public record ImprovementList(RoundInfo run, List<Summary> improvements) {

  /**
   * 회차 정보. 개선안 메뉴로 다시 들어온 화면을 runId 하나로 다시 그리는 데 쓴다.
   *
   * @param awaitingApproval 이 회차가 다음 회차 승인을 기다리는 중인지 — 회차 단위 값이라 목록과 상세에 모두 싣는다
   */
  public record RoundInfo(long firstRunId, int round, String projectTitle, String taskGoal, boolean awaitingApproval) {
  }

  /** @param decision 이 개선안의 결정. 결정 전이면 null */
  public record Summary(long improvementId, int optionNo, PatchKind patchKind, String fixCost, Decision decision) {
  }
}
