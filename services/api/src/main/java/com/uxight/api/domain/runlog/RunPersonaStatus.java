package com.uxight.api.domain.runlog;

import java.time.LocalDateTime;

/** run_personas 한 행 중 화면에 필요한 값. 행은 AI 모듈이 회차를 접수할 때 Persona 마다 만들고 갱신한다(Python 소유). */
public record RunPersonaStatus(long personaId, String status, Integer steps, LocalDateTime finishedAt) {
}
