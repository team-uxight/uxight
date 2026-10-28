package com.uxight.api.domain.improvement;

import com.uxight.api.domain.finding.FindingList;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

/**
 * 개선안 상세. 프론트엔드는 awaitingApproval 이 true 이고 approval 이 null 일 때만 승인 · 반려 버튼을 켠다.
 *
 * @param findings 이 개선안이 다루는 진단 — finding_ids 중 개선안과 같은 회차의 진단만
 * @param approval 결정. 결정 전이면 null
 */
public record ImprovementDetail(long improvementId, long runId, int optionNo, PatchKind patchKind, Map<String, Object> patch,
    String rationale, String expectedEffect, String fixCost, List<FindingList.Summary> findings, ApprovalInfo approval,
    boolean awaitingApproval) {

  public record ApprovalInfo(Decision decision, String note, LocalDateTime decidedAt) {

    public static ApprovalInfo from(Approval approval) {
      return new ApprovalInfo(approval.getDecision(), approval.getNote(), approval.getDecidedAt());
    }
  }
}
