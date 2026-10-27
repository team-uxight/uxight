package com.uxight.api.domain.finding;

import java.util.List;

/** 진단 상세 — 유형 · 심각도 · 요약과 근거 위치. 근거 스크린샷은 진단 근거 스크린샷 조회(GACA-208)로 받는다. */
public record FindingDetail(long findingId, long runId, Taxonomy taxonomy, String severity, String summary,
    List<Finding.Evidence> evidence) {

  public static FindingDetail from(Finding finding) {
    return new FindingDetail(finding.getId(), finding.getRun().getId(), finding.getTaxonomy(), finding.getSeverity(),
        finding.getSummary(), finding.evidenceList());
  }
}
