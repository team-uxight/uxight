package com.uxight.api.web.run;

import com.uxight.api.domain.run.ExperimentRounds;
import com.uxight.api.domain.run.RoundSummary;

import java.util.List;

/** awaitingApproval 은 회차가 아니라 실험에 붙는다 — 실험이 다음 회차 승인을 기다리는 중이면 true. */
public record RoundListResponse(List<RoundSummary> rounds, boolean awaitingApproval) {

  public static RoundListResponse from(ExperimentRounds experimentRounds) {
    return new RoundListResponse(experimentRounds.rounds(), experimentRounds.awaitingApproval());
  }
}
