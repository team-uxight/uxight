"""GACA-162: Persona별 행동 지표 계산 테스트."""

import json

from uxight_agent.watcher.persona_metrics import (
    calculate_metrics,
    read_run_metrics,
)


def make_step(number, url, url_after, screen, *, error_code=None, blocked=False):
    return {
        "step": number,
        "url": url,
        "observation": {"elements_hash": screen},
        "action": {"kind": "click"},
        "result": {
            "ok": error_code is None,
            "url_after": url_after,
            "error_code": error_code,
        },
        "blocked": {"is": blocked},
    }


def test_calculate_persona_metrics():
    steps = [
        make_step(1, "/a", "/b", "screen-a"),
        make_step(2, "/b", "/a", "screen-b"),
        make_step(3, "/a", "/a", "screen-a"),
        make_step(
            4,
            "/a",
            "/a",
            "screen-a",
            error_code="ELEMENT_NOT_FOUND",
        ),
        make_step(
            5,
            "/a",
            "/a",
            "screen-a",
            error_code="PARSE_FAILED",
            blocked=True,
        ),
    ]

    assert calculate_metrics(steps) == {
        "backtrack_count": 1,
        "repeat_screen_count": 3,
        "execution_error_count": 1,
        "blocked_count": 1,
        "step_count": 5,
    }


def test_read_run_metrics(tmp_path):
    run_dir = tmp_path / "101"

    for persona_id, count in [("1", 2), ("2", 3)]:
        folder = run_dir / persona_id
        folder.mkdir(parents=True)

        with (folder / "steps.jsonl").open("w", encoding="utf-8") as file:
            for number in range(1, count + 1):
                step = make_step(
                    number,
                    f"/page-{number}",
                    f"/page-{number + 1}",
                    f"screen-{number}",
                )
                file.write(json.dumps(step) + "\n")

    result = read_run_metrics(run_dir)

    assert set(result) == {"1", "2"}
    assert result["1"]["step_count"] == 2
    assert result["2"]["step_count"] == 3
    assert result["1"]["repeat_screen_count"] == 0
    assert result["2"]["blocked_count"] == 0


def test_format_metrics_table():
    """Persona 2명의 지표가 하나의 표로 정리되는지 확인한다."""
    from uxight_agent.watcher.persona_metrics import format_metrics_table

    metrics = {
        "1": {
            "backtrack_count": 2,
            "repeat_screen_count": 3,
            "execution_error_count": 1,
            "blocked_count": 0,
            "step_count": 12,
        },
        "2": {
            "backtrack_count": 0,
            "repeat_screen_count": 1,
            "execution_error_count": 0,
            "blocked_count": 2,
            "step_count": 8,
        },
    }

    table = format_metrics_table(metrics)
    lines = table.splitlines()

    assert len(lines) == 3
    assert all(
        header in lines[0]
        for header in ("Persona", "Backtrack", "Repeat", "Error", "Blocked", "Steps")
    )
    assert lines[1].split() == ["1", "2", "3", "1", "0", "12"]
    assert lines[2].split() == ["2", "0", "1", "0", "2", "8"]

    print("\nPersona별 UX 행동 지표")
    print(table)


def test_steps_jsonl_to_metrics_table(tmp_path):
    """실제 JSONL 파일을 읽어 Persona별 지표 표까지 생성한다."""
    from uxight_agent.watcher.persona_metrics import format_metrics_table

    run_dir = tmp_path / "101"

    scenarios = {
        "1": [
            make_step(1, "/home", "/menu", "home"),
            make_step(2, "/menu", "/home", "menu"),
            make_step(3, "/home", "/home", "home"),
        ],
        "2": [
            make_step(1, "/home", "/home", "home"),
            make_step(
                2,
                "/home",
                "/home",
                "home",
                error_code="PARSE_FAILED",
                blocked=True,
            ),
        ],
    }

    for persona_id, steps in scenarios.items():
        folder = run_dir / persona_id
        folder.mkdir(parents=True)

        with (folder / "steps.jsonl").open("w", encoding="utf-8") as file:
            for step in steps:
                file.write(json.dumps(step) + "\n")

    metrics = read_run_metrics(run_dir)
    table = format_metrics_table(metrics)

    assert metrics["1"] == {
        "backtrack_count": 1,
        "repeat_screen_count": 1,
        "execution_error_count": 0,
        "blocked_count": 0,
        "step_count": 3,
    }
    assert metrics["2"] == {
        "backtrack_count": 0,
        "repeat_screen_count": 1,
        "execution_error_count": 0,
        "blocked_count": 1,
        "step_count": 2,
    }

    lines = table.splitlines()
    assert len(lines) == 3
    assert lines[1].split() == ["1", "1", "1", "0", "0", "3"]
    assert lines[2].split() == ["2", "0", "1", "0", "1", "2"]

    print("\n실제 steps.jsonl 기반 Persona별 지표")
    print(table)
