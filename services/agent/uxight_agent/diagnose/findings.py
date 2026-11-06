"""회차 진단 묶기 (GACA-165). Persona 별 규칙 검출(GACA-68 friction_rules)을 findings 행으로 만든다.

- 한 행 = 회차 × 유형(taxonomy). 같은 유형에 걸린 Persona 를 한 행에 묶는다.
- 심각도는 걸린 Persona 가운데 가장 높은 값이다 (high > medium > low).
- 근거(evidence)는 Persona 별 step 구간이다. 이어진 step 번호는 한 구간으로 합치고,
  url 은 구간 첫 step 의 행동 전 URL 이다. 형식은 V7__findings.sql · Spring
  Finding.evidenceList() 와 같은 snake_case:
  [{"persona_id": 3, "step_from": 4, "step_to": 7, "url": "https://..."}].
  스크린샷은 Spring 이 persona_id · step 으로 찾는다(step-<n>.png).
- 판정 규칙 자체는 friction_rules 를 그대로 쓴다. 이 파일은 묶기만 한다.
"""

from dataclasses import dataclass, field
from typing import Any

from ..watcher.friction_rules import FrictionResult, detect_frictions

# findings.taxonomy 의 4종 (V7 CHECK) — 정의 순서. 같은 심각도끼리는 이 순서로 놓는다.
TAXONOMIES = (
    "navigation_confusion",
    "interaction_failure",
    "task_failure",
    "excessive_steps",
)
SEVERITY_RANK = {"high": 0, "medium": 1, "low": 2}


@dataclass(frozen=True)
class PersonaHit:
    """유형 하나에 걸린 Persona 하나 — 규칙 결과 그대로."""

    persona_id: int
    severity: str
    steps: tuple[int, ...]
    reason: str


@dataclass
class Finding:
    """findings 한 행이 될 진단. summary(설명)는 아직 채우지 않는다 (GACA-166)."""

    taxonomy: str
    severity: str
    evidence: list[dict]
    hits: list[PersonaHit] = field(default_factory=list)
    summary: str | None = None


def build_findings(
    steps_by_persona: dict[Any, list[dict]], statuses: dict[Any, str]
) -> list[Finding]:
    """Persona 별 step 로그 · 종료 상태로 회차의 진단 목록을 만든다. 로그가 빈 Persona 는 건너뛴다.

    순서는 심각도 순, 같으면 유형 정의 순이다.
    """
    hits: dict[str, list[PersonaHit]] = {}
    urls: dict[tuple[int, int], str | None] = {}
    for persona_id, steps in sorted(steps_by_persona.items()):
        if not steps:
            continue
        for step in steps:
            urls[(persona_id, step["step"])] = step.get("url")
        for result in detect_frictions(steps, status=statuses.get(persona_id)):
            if result.type in TAXONOMIES:
                hits.setdefault(result.type, []).append(_hit(persona_id, result))

    findings = [
        Finding(
            taxonomy=taxonomy,
            severity=min((h.severity for h in group), key=SEVERITY_RANK.__getitem__),
            evidence=[e for h in group for e in _evidence(h, urls)],
            hits=group,
        )
        for taxonomy, group in hits.items()
    ]
    return sorted(findings, key=lambda f: (SEVERITY_RANK[f.severity], TAXONOMIES.index(f.taxonomy)))


def _hit(persona_id: int, result: FrictionResult) -> PersonaHit:
    return PersonaHit(persona_id, result.severity, result.steps, result.reason)


def _evidence(hit: PersonaHit, urls: dict[tuple[int, int], str | None]) -> list[dict]:
    """step 번호들을 이어진 구간으로 합친다. 예: (2, 3, 4, 7) → 2~4, 7~7."""
    ranges: list[list[int]] = []
    for step in sorted(set(hit.steps)):
        if ranges and step == ranges[-1][1] + 1:
            ranges[-1][1] = step
        else:
            ranges.append([step, step])
    return [
        {
            "persona_id": hit.persona_id,
            "step_from": start,
            "step_to": end,
            "url": urls.get((hit.persona_id, start)) or "",
        }
        for start, end in ranges
    ]
