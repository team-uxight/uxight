package com.uxight.api.domain.result;

import com.uxight.api.domain.improvement.PatchKind;
import com.uxight.api.domain.run.RunMetrics;

import java.util.List;

/**
 * 결과 조회 — 실험의 최초 회차(Before)와 마지막 done 회차(After)의 지표 · 스크린샷과 회차별 적용 패치 (design-decision 2.4).
 *
 * @param after   done 인 회차가 최초 회차 하나뿐이면 null
 * @param patches 회차 순 · 기록 순. AI 모듈은 이전 회차들의 패치까지 누적해 주입하므로 한 회차에 여러 줄일 수 있다
 */
public record Comparison(Experiment experiment, Before before, After after, List<AppliedPatch> patches) {

  /** 실험 정보. state 는 실험 목록과 같은 계산이다. */
  public record Experiment(String projectTitle, String taskGoal, String mode, String state) {
  }

  /** 최초 회차. metrics 는 회차 종료 시 확정된 값(run_metrics) — 행이 없으면 칸마다 null. */
  public record Before(long runId, RunMetrics metrics, List<ScreenshotRef> screenshots) {
  }

  /** 마지막 done 회차와 그 회차가 몇 번째 회차인지. */
  public record After(long runId, int round, RunMetrics metrics, List<ScreenshotRef> screenshots) {
  }

  /** 회차에 실제로 주입된 패치(patch_versions) — 주입은 대상 사이트의 화면 구조가 바뀌면 실패한다. */
  public record AppliedPatch(int round, PatchKind patchKind, boolean applied) {
  }

  /** 결과 스크린샷 조회에 넘길 값. */
  public record ScreenshotRef(long personaId, int step) {
  }
}
