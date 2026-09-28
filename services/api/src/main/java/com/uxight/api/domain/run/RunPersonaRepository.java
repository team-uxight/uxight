package com.uxight.api.domain.run;

import java.util.List;

public interface RunPersonaRepository {

  List<RunPersona> findByRunId(Long runId);
}
