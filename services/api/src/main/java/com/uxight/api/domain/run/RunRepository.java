package com.uxight.api.domain.run;

import java.util.List;

public interface RunRepository {

  Long save(Run run);

  void updateDispatchState(Long runId, String dispatchState);

  List<Run> findActiveByUserId(Long userId);

  List<Run> findEndedByUserId(Long userId);

  void requestCancel(Long runId);
}
