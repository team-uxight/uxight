"""GACA-162 + GACA-68: Persona 행동 지표와 UX 문제 진단 통합."""

from dataclasses import asdict

from uxight_agent.watcher.friction_rules import detect_frictions
from uxight_agent.watcher.persona_metrics import calculate_metrics


def diagnose_persona(
    steps: list[dict],
    status: str | None = None,
) -> dict:
    """한 Persona의 행동 지표와 Friction 진단 결과를 반환한다."""
    metrics = calculate_metrics(steps)
    frictions = detect_frictions(steps, status=status)

    step_lookup = {
        step["step"]: step
        for step in steps
        if isinstance(step.get("step"), int)
    }

    diagnoses = []
    for friction in frictions:
        evidence = []
        for step_number in friction.steps:
            step = step_lookup.get(step_number)
            if step is None:
                continue

            evidence.append(
                {
                    "step": step_number,
                    "url": step.get("url"),
                    "screenshot": (
                        (step.get("observation") or {}).get("screenshot")
                    ),
                }
            )

        diagnoses.append(
            {
                **asdict(friction),
                "evidence": evidence,
            }
        )

    return {
        "run_id": steps[0].get("run_id") if steps else None,
        "persona_id": steps[0].get("persona_id") if steps else None,
        "metrics": metrics,
        "frictions": diagnoses,
    }
