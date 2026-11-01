"""GACA-162 + GACA-68 통합 진단 테스트."""

import json
from pathlib import Path

import pytest

from uxight_agent.watcher.persona_diagnosis import diagnose_persona

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "runs" / "9001"

EXPECTED = {
    1: [],
    2: [
        ("navigation_confusion", "medium"),
        ("excessive_steps", "low"),
    ],
    3: [
        ("interaction_failure", "medium"),
        ("task_failure", "medium"),
    ],
    4: [
        ("task_failure", "high"),
        ("navigation_confusion", "medium"),
        ("interaction_failure", "medium"),
    ],
    5: [
        ("task_failure", "high"),
    ],
}


@pytest.mark.parametrize("persona_id", [1, 2, 3, 4, 5])
def test_persona_diagnosis_integration(persona_id):
    """행동 지표, Friction, 근거 화면의 통합 결과를 검증한다."""
    run_path = FIXTURE_ROOT / "run.json"
    if not run_path.exists():
        pytest.skip("샘플 실행 로그가 제공되지 않음")

    run = json.loads(run_path.read_text(encoding="utf-8"))
    persona = next(p for p in run["personas"] if p["persona_id"] == persona_id)

    steps_path = FIXTURE_ROOT / str(persona_id) / "steps.jsonl"
    steps = [
        json.loads(line)
        for line in steps_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    result = diagnose_persona(steps, status=persona["status"])

    assert result["run_id"] == 9001
    assert result["persona_id"] == persona_id
    assert result["metrics"]["step_count"] == len(steps)

    actual = [(friction["type"], friction["severity"]) for friction in result["frictions"]]
    assert actual == EXPECTED[persona_id]

    for friction in result["frictions"]:
        assert friction["steps"]
        assert len(friction["evidence"]) == len(friction["steps"])

        for evidence in friction["evidence"]:
            assert evidence["step"] in friction["steps"]
            assert evidence["url"]
            assert evidence["screenshot"]
