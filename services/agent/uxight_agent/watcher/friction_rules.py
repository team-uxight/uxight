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


@dataclass(frozen=True)
class FrictionResult:
    """Friction 판정 결과와 근거 Step 번호."""

    type: FrictionType
    severity: Severity
    steps: tuple[int, ...]
    reason: str


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


def detect_task_failure(
    steps: list[dict],
    status: str | None = None,
) -> FrictionResult | None:
    """실행 종료 후 과제 실패 여부를 판정한다."""
    if not steps:
        return None

    last = steps[-1]
    last_step = last["step"]
    reached = any((step.get("task") or {}).get("url_reached") is True for step in steps)
    action_kind = (last.get("action") or {}).get("kind")

    if status in {"fail", "max_steps"}:
        error_code = (last.get("result") or {}).get("error_code")

        if error_code == "PARSE_FAILED":
            reason = "LLM 응답 파싱 오류로 과제 실행이 실패함 (웹사이트 UX 문제로 단정할 수 없음)"
        else:
            reason = f"과제 실행이 {status} 상태로 종료됨"

        return FrictionResult(
            type="task_failure",
            severity="high",
            steps=(last_step,),
            reason=reason,
        )

    if reached is False and (status == "done" or (status is None and action_kind == "done")):
        return FrictionResult(
            type="task_failure",
            severity="medium",
            steps=(last_step,),
            reason=(
                "에이전트는 완료를 선언했으나 목표 URL에 도달하지 못함 "
                "(Agent 판단과 URL 보조 판정 불일치, 사람 검토 필요)"
            ),
        )

    return None


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
    status: str | None = None,
    threshold: int = 10,
) -> FrictionResult | None:
    """목표 URL에 처음 도달하기까지 사용한 단계 수를 기준으로 판정한다."""
    if not steps or status in {"fail", "max_steps", "timeout", "cancelled"}:
        return None

    first_reached_index = next(
        (
            index
            for index, step in enumerate(steps)
            if (step.get("task") or {}).get("url_reached") is True
        ),
        None,
    )

    if first_reached_index is None:
        return None

    step_count = first_reached_index + 1
    if step_count <= threshold:
        return None

    severity: Severity = "medium" if step_count >= 16 else "low"
    reached_step = steps[first_reached_index]["step"]

    return FrictionResult(
        type="excessive_steps",
        severity=severity,
        steps=(reached_step,),
        reason=f"목표 최초 도달까지 {step_count}단계 사용 (기준: {threshold}단계)",
    )


def detect_frictions(
    steps: list[dict],
    status: str | None = None,
    excessive_steps_threshold: int = 10,
) -> list[FrictionResult]:
    """행동 로그에서 모든 Friction을 탐지하고 심각도순으로 반환한다."""
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
