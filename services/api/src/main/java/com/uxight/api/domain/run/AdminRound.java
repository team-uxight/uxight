package com.uxight.api.domain.run;

import com.uxight.api.domain.runlog.RunPersonaList;

import java.util.List;

/** 관리자 회차 목록의 한 회차와 그 회차의 Persona 별 진행. personas 는 회차의 Persona 스냅샷 순서다. */
public record AdminRound(long runId, String projectTitle, String taskGoal, RunMode mode, int round, RunStatus status,
    List<RunPersonaList.Item> personas) {
}
