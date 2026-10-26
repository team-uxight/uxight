package com.uxight.api.domain.run;

import java.time.LocalDateTime;

/**
 * 관리자 전체 실험 목록의 한 줄. round · status · finishedAt 은 실험의 마지막 회차 기준이다.
 *
 * @param projectDeleted 리서처가 삭제한 프로젝트의 실험. 리서처 목록에서는 보이지 않지만 운영자는 본다
 * @param ownerEmail     프로젝트 소유 리서처의 이메일
 * @param round          회차 수(= 마지막 회차 번호)
 * @param createdAt      실험 요청 시각(최초 회차)
 */
public record AdminExperimentSummary(long firstRunId, String projectTitle, boolean projectDeleted, String ownerEmail,
    String taskGoal, RunMode mode, int round, RunStatus status, LocalDateTime createdAt, LocalDateTime finishedAt) {
}
