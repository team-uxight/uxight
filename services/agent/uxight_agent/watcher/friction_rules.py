"""GACA-68: 행동 로그 기반 Friction 판정 규칙.

Python 규칙으로 UX 문제를 우선 탐지하고,
LLM은 필요한 경우 보조 분석에 사용한다.
"""

from dataclasses import dataclass
from typing import Literal

FrictionType = Literal[
    "navigation_confusion",
    "interaction_failure",
    "task_failure",
    "excessive_steps",
    "none",
]

Severity = Literal["high", "medium", "low", "none"]

# Persona 결과 넷(11/03 결정) 중 '판정 안 함'. 실행 오류 · 취소는 사이트 문제가 아니다.
# 끝난 이유를 모르면 결과를 정할 수 없어 같이 뺀다.
UNJUDGED_STATUSES = frozenset({None, "fail", "cancelled"})
# 못 닿고 끝났을 때 심각도를 높음으로 보는 상태. 상한까지 헤맸거나 같은 화면에서 막혔다.
# done 은 사람이 봐야 하는 불일치, token_limit 은 토큰 상한이 끝낸 것이라 둘은 중간이다.
HIGH_SEVERITY_ENDS = frozenset({"max_steps", "stuck", "timeout"})


@dataclass(frozen=True)
class FrictionResult:
    """Friction 판정 결과와 근거 Step 번호."""

    type: FrictionType
    severity: Severity
    steps: tuple[int, ...]
    reason: str


def _url_reached(step: dict) -> bool | None:
    return (step.get("task") or {}).get("url_reached")


def detect_interaction_failure(steps: list[dict]) -> FrictionResult | None:
    """반복 클릭으로 진행하지 못하거나 브라우저 조작 오류가 발생한 경우 탐지한다."""
    browser_errors = {
        "ELEMENT_NOT_INTERACTABLE",
        "ELEMENT_NOT_FOUND",
        "BROWSER_ACTION_FAILED",
    }

    for index, step in enumerate(steps):
        error_code = (step.get("result") or {}).get("error_code")
        if error_code in browser_errors:
            return FrictionResult(
                type="interaction_failure",
                severity="medium",
                steps=(step["step"],),
                reason=f"브라우저 조작 오류 발생: {error_code}",
            )

        if index < 2:
            continue

        recent = steps[index - 2 : index + 1]
        actions = [s.get("action") or {} for s in recent]
        targets = [a.get("target") for a in actions]
        urls = [s.get("url") for s in recent]
        hashes = [(s.get("observation") or {}).get("elements_hash") for s in recent]

        if (
            all(a.get("kind") == "click" for a in actions)
            and targets[0] is not None
            and len(set(targets)) == 1
            and len(set(urls)) == 1
            and all(h is not None for h in hashes)
            and len(set(hashes)) == 1
        ):
            return FrictionResult(
                type="interaction_failure",
                severity="medium",
                steps=tuple(s["step"] for s in recent),
                reason="동일 화면에서 같은 요소를 3회 연속 클릭함",
            )

    return None


def detect_task_failure(steps: list[dict], status: str) -> FrictionResult | None:
    """한 번도 목표에 못 닿은 Persona 를 과제 실패로 판정한다 (11/03 결정의 '실패').

    붙일지는 닿았는지로 정하고, 끝난 이유(status)는 심각도와 사유에만 쓴다.
    """
    reached = [_url_reached(step) for step in steps]
    if True in reached or False not in reached:
        return None

    if status == "done":
        reason = (
            "에이전트는 완료를 선언했으나 목표 URL에 도달하지 못함 "
            "(Agent 판단과 URL 판정 불일치, 사람 검토 필요)"
        )
    else:
        reason = f"목표 URL에 한 번도 닿지 못하고 {status} 상태로 종료됨"

    return FrictionResult(
        type="task_failure",
        severity="high" if status in HIGH_SEVERITY_ENDS else "medium",
        steps=(steps[-1]["step"],),
        reason=reason,
    )


def detect_navigation_confusion(steps: list[dict]) -> FrictionResult | None:
    """반복적인 뒤로 가기 또는 이전 페이지 재방문을 탐지한다."""
    back_steps = [s["step"] for s in steps if (s.get("action") or {}).get("kind") == "back"]

    visited = []
    revisit_steps = []

    for step in steps:
        url = step.get("url")
        if not url:
            continue

        # 같은 URL에서 연속으로 행동하는 것은 재방문으로 계산하지 않는다.
        if visited and visited[-1] == url:
            continue

        if url in visited:
            revisit_steps.append(step["step"])

        visited.append(url)

    if len(back_steps) >= 2 or len(revisit_steps) >= 2:
        evidence = sorted(set(back_steps + revisit_steps))
        return FrictionResult(
            type="navigation_confusion",
            severity="medium",
            steps=tuple(evidence),
            reason=(
                f"뒤로 가기 {len(back_steps)}회, 이전 페이지 재방문 {len(revisit_steps)}회 발생"
            ),
        )

    return None


def detect_excessive_steps(
    steps: list[dict],
    status: str,
    threshold: int = 10,
) -> FrictionResult | None:
    """목표에 처음 닿기까지의 단계 수로 판정한다.

    어렵게 성공(닿았지만 done 으로 끝내지 못함)이면 처음 닿은 뒤의 step 이 근거다 (11/03 결정).
    닿고도 더 움직인 step 은 기준과 상관없이 과도한 단계다.
    """
    first = next((i for i, step in enumerate(steps) if _url_reached(step) is True), None)
    if first is None:
        return None

    extra = steps[first + 1 :] if status != "done" else []
    step_count = first + 1 + len(extra)
    if not extra and step_count <= threshold:
        return None

    if extra:
        evidence = tuple(step["step"] for step in extra)
        reason = f"목표에 처음 닿은 뒤 {len(extra)}단계를 더 쓰고 {status} 상태로 종료됨"
    else:
        evidence = (steps[first]["step"],)
        reason = f"목표 최초 도달까지 {step_count}단계 사용 (기준: {threshold}단계)"

    return FrictionResult(
        type="excessive_steps",
        severity="medium" if step_count >= 16 else "low",
        steps=evidence,
        reason=reason,
    )


def detect_frictions(
    steps: list[dict],
    status: str | None = None,
    excessive_steps_threshold: int = 10,
) -> list[FrictionResult]:
    """행동 로그에서 모든 Friction을 탐지하고 심각도순으로 반환한다.

    판정 안 함(실행 오류 · 취소 · 도달 기록이 모두 비어 있음)이면 Friction 을 만들지 않는다.
    """
    if status in UNJUDGED_STATUSES or all(_url_reached(step) is None for step in steps):
        return []

    results = [
        detect_navigation_confusion(steps),
        detect_interaction_failure(steps),
        detect_task_failure(steps, status=status),
        detect_excessive_steps(
            steps,
            status=status,
            threshold=excessive_steps_threshold,
        ),
    ]

    severity_order = {
        "high": 0,
        "medium": 1,
        "low": 2,
        "none": 3,
    }

    detected = [result for result in results if result is not None]
    return sorted(
        detected,
        key=lambda result: severity_order[result.severity],
    )
