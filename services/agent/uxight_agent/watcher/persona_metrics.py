"""Persona별 steps.jsonl에서 UX 행동 지표를 계산한다."""

import json
from pathlib import Path

BROWSER_ERROR_CODES = {
    "ELEMENT_NOT_FOUND",
    "ELEMENT_NOT_INTERACTABLE",
    "NAVIGATION_TIMEOUT",
    "BROWSER_ACTION_FAILED",
}


def calculate_metrics(steps: list[dict]) -> dict:
    """한 Persona의 Step 로그에서 지표 5개를 계산한다."""
    visited_urls = set()
    seen_screens = set()

    metrics = {
        "backtrack_count": 0,
        "repeat_screen_count": 0,
        "execution_error_count": 0,
        "blocked_count": 0,
        "step_count": len(steps),
    }

    for step in steps:
        url = step.get("url")
        screen_hash = step.get("observation", {}).get("elements_hash")
        result = step.get("result", {})
        action = step.get("action")
        blocked = step.get("blocked", {})

        if screen_hash is not None:
            if screen_hash in seen_screens:
                metrics["repeat_screen_count"] += 1
            seen_screens.add(screen_hash)

        if result.get("error_code") in BROWSER_ERROR_CODES:
            metrics["execution_error_count"] += 1

        if blocked.get("is") is True:
            metrics["blocked_count"] += 1

        if url:
            visited_urls.add(url)

        url_after = result.get("url_after")
        if (
            action is not None
            and result.get("ok") is True
            and url_after
            and url_after != url
            and url_after in visited_urls
        ):
            metrics["backtrack_count"] += 1

    return metrics


def read_persona_metrics(steps_path: str | Path) -> dict:
    """Persona의 steps.jsonl 파일을 읽어 지표를 반환한다."""
    path = Path(steps_path)

    with path.open(encoding="utf-8") as file:
        steps = [json.loads(line) for line in file if line.strip()]

    return calculate_metrics(steps)


def read_run_metrics(run_dir: str | Path) -> dict[str, dict]:
    """회차 폴더 아래 Persona별 steps.jsonl을 읽어 지표를 모은다."""
    run_dir = Path(run_dir)
    metrics_by_persona = {}

    for steps_path in sorted(run_dir.glob("*/steps.jsonl")):
        persona_id = steps_path.parent.name
        metrics_by_persona[persona_id] = read_persona_metrics(steps_path)

    return metrics_by_persona


def format_metrics_table(metrics_by_persona: dict[str, dict]) -> str:
    """Persona별 지표를 읽기 쉬운 텍스트 표로 만든다."""
    headers = ("Persona", "Backtrack", "Repeat", "Error", "Blocked", "Steps")
    rows = [headers]

    for persona_id, metrics in sorted(metrics_by_persona.items()):
        rows.append(
            (
                str(persona_id),
                str(metrics["backtrack_count"]),
                str(metrics["repeat_screen_count"]),
                str(metrics["execution_error_count"]),
                str(metrics["blocked_count"]),
                str(metrics["step_count"]),
            )
        )

    widths = [max(len(row[index]) for row in rows) for index in range(len(headers))]

    return "\n".join(
        "  ".join(value.ljust(widths[index]) for index, value in enumerate(row)) for row in rows
    )
