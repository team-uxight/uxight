package com.uxight.api.domain.runlog;

import com.uxight.api.domain.run.RunStatus;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.function.Function;
import java.util.stream.Collectors;

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

    /**
     * 회차의 Persona 스냅샷(persona_id · name) 순서대로 run_personas 의 진행을 붙인다. 리서처용 Persona 목록과
     * 관리자용 회차 목록이 함께 쓴다. run_personas 행이 아직 없는 Persona(접수 전)는 이름만 있다.
     */
    public static List<Item> of(List<Map<String, Object>> personaSnapshot, List<RunPersonaStatus> statuses) {
      Map<Long, RunPersonaStatus> byPersona = statuses.stream()
          .collect(Collectors.toMap(RunPersonaStatus::personaId, Function.identity()));
      return personaSnapshot.stream()
          .map(persona -> {
            long personaId = ((Number) persona.get("persona_id")).longValue();
            Optional<RunPersonaStatus> status = Optional.ofNullable(byPersona.get(personaId));
            return new Item(personaId, (String) persona.get("name"), status.map(RunPersonaStatus::status).orElse(null),
                status.map(RunPersonaStatus::steps).orElse(null), status.map(RunPersonaStatus::finishedAt).orElse(null));
          })
          .toList();
    }
  }
}
