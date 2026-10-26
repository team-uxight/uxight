package com.uxight.api.domain.runlog;

import com.uxight.api.domain.run.RunStatus;

import java.time.LocalDateTime;
import java.util.List;

/**
 * 회차 상태와 Persona 별 진행. personas 는 회차의 Persona 스냅샷 순서다.
 * AI 모듈이 회차를 접수하기 전(queued · accepted)이면 Persona 의 status · steps · finishedAt 이 null 이다.
 */
public record RunPersonaList(long runId, RunStatus status, List<Item> personas) {

  /**
   * @param status running · done · max_steps · fail · timeout · cancelled (run_personas.status). 실행 전이면 null
   * @param steps  지금까지 기록된 step 수
   */
  public record Item(long personaId, String name, String status, Integer steps, LocalDateTime finishedAt) {
  }
}
