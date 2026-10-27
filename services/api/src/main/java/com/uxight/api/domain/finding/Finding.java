package com.uxight.api.domain.finding;

import com.uxight.api.domain.run.Run;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.FetchType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;
import org.hibernate.annotations.Immutable;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

/**
 * 진단 — 회차의 행동 로그에서 검출된 Friction 1건과 그 요약. 행은 AI 모듈이 만들고(검출) 요약을 채운다(진단).
 * Spring 은 읽기만 하므로 @Immutable — JPA 가 INSERT · UPDATE 를 만들지 않는다.
 */
@Entity
@Table(name = "findings")
@Immutable
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class Finding {

  @Id
  @Column(name = "finding_id")
  private Long id;

  @ManyToOne(fetch = FetchType.LAZY)
  @JoinColumn(name = "run_id")
  private Run run;

  @Enumerated(EnumType.STRING)
  private Taxonomy taxonomy;

  private String severity;      // 값과 산정 기준 미확정 (GACA-68) — 저장된 문자열을 그대로 전달한다

  // [{"persona_id", "step_from", "step_to", "url"}] — 위치만 담는다. 로그 원문은 steps.jsonl 에 있다
  @JdbcTypeCode(SqlTypes.JSON)
  private List<Map<String, Object>> evidence;

  private String summary;       // 진단(요약) 단계 전이면 null

  private LocalDateTime createdAt;

  /** 근거 위치들을 camelCase 응답 형태로. agent 가 snake_case 로 쓴다(V7__findings.sql). */
  public List<Evidence> evidenceList() {
    return evidence.stream()
        .map(e -> new Evidence(((Number) e.get("persona_id")).longValue(), ((Number) e.get("step_from")).intValue(),
            ((Number) e.get("step_to")).intValue(), (String) e.get("url")))
        .toList();
  }

  /** 근거 위치 하나 — 어느 Persona 의 어느 step 구간, 어느 URL 에서 검출됐는지. */
  public record Evidence(long personaId, int stepFrom, int stepTo, String url) {
  }
}
