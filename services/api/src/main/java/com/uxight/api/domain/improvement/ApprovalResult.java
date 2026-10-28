package com.uxight.api.domain.improvement;

/** 결정 결과. runId 는 승인이면 새로 만든 다음 회차, 반려면 null — 경로의 runId(결정한 회차)와 다른 회차다. */
public record ApprovalResult(long approvalId, Long runId) {
}
