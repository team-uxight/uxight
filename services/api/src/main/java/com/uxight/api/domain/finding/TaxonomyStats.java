package com.uxight.api.domain.finding;

import java.util.List;

/** Friction Taxonomy 분포 — 4종 모두 정의 순서로, 진단이 없는 유형은 0. 실험 이력의 분포 그래프에 쓴다. */
public record TaxonomyStats(List<TaxonomyCount> stats) {

  public record TaxonomyCount(Taxonomy taxonomy, long count) {
  }
}
