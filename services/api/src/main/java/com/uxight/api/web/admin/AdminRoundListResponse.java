package com.uxight.api.web.admin;

import com.uxight.api.domain.run.AdminRound;
import com.uxight.api.domain.run.RunMode;
import com.uxight.api.domain.run.RunStatus;

import java.util.List;

/** 관리자 회차 목록. 회차마다 Persona 실행 결과(personaId · 이름 · 상태 · step 수)를 담는다. */
public record AdminRoundListResponse(List<Round> rounds) {

  public static AdminRoundListResponse from(List<AdminRound> rounds) {
    return new AdminRoundListResponse(rounds.stream()
        .map(r -> new Round(r.runId(), r.projectTitle(), r.taskGoal(), r.mode(), r.round(), r.status(),
            r.personas().stream().map(p -> new PersonaRunResult(p.personaId(), p.name(), p.status(), p.steps())).toList()))
        .toList());
  }

  public record Round(long runId, String projectTitle, String taskGoal, RunMode mode, int round, RunStatus status,
      List<PersonaRunResult> personas) {
  }

  /** status · steps 는 AI 모듈이 회차를 접수하기 전이면 null 이다. */
  public record PersonaRunResult(long personaId, String name, String status, Integer steps) {
  }
}
