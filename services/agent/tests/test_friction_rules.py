"""GACA-68: 행동 로그 기반 Friction 판정 테스트."""

import json
from pathlib import Path

import pytest

from uxight_agent.watcher.friction_rules import detect_frictions


FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "runs" / "9001"

EXPECTED = {
    1: [("none", "none")],
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
    5: [("task_failure", "high")],
}


@pytest.mark.parametrize("persona_id", [1, 2, 3, 4, 5])
def test_sample_persona_frictions(persona_id):
    """샘플 행동 로그의 Friction 유형과 심각도를 검증한다."""
    if not (FIXTURE_ROOT / "run.json").exists():
        pytest.skip("GACA-46 샘플 로그가 아직 제공되지 않음")

    run = json.loads(
        (FIXTURE_ROOT / "run.json").read_text(encoding="utf-8")
    )
    persona = next(
        p for p in run["personas"]
        if p["persona_id"] == persona_id
    )

    path = FIXTURE_ROOT / str(persona_id) / "steps.jsonl"
    steps = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    results = detect_frictions(steps, status=persona["status"])
    actual = [(r.type, r.severity) for r in results]

    if not actual:
        actual = [("none", "none")]

    assert actual == EXPECTED[persona_id]

    if persona_id == 5:
        assert "LLM 응답 파싱 오류" in results[0].reason
        assert "웹사이트 UX 문제로 단정할 수 없음" in results[0].reason


def test_successful_task_has_no_failure():
    """목표에 도달한 정상 종료는 과제 실패가 아니다."""
    from uxight_agent.watcher.friction_rules import detect_task_failure

    steps = [
        {
            "step": 1,
            "action": {"kind": "done"},
            "task": {"url_reached": True},
        }
    ]

    assert detect_task_failure(steps, status="done") is None


def test_done_without_goal_is_task_failure():
    """Agent 완료 선언과 URL 보조 판정의 불일치를 탐지한다."""
    from uxight_agent.watcher.friction_rules import detect_task_failure

    steps = [
        {
            "step": 1,
            "action": {"kind": "done"},
            "task": {"url_reached": False},
        }
    ]

    result = detect_task_failure(steps, status="done")

    assert result is not None
    assert result.type == "task_failure"
    assert result.severity == "medium"
    assert result.steps == (1,)


def test_repeated_page_revisits_are_navigation_confusion():
    """이전 페이지를 두 번 이상 재방문하면 탐색 혼란이다."""
    from uxight_agent.watcher.friction_rules import detect_navigation_confusion

    urls = ["A", "B", "A", "B", "A"]
    steps = [
        {
            "step": index,
            "url": url,
            "action": {"kind": "click"},
        }
        for index, url in enumerate(urls, start=1)
    ]

    result = detect_navigation_confusion(steps)

    assert result is not None
    assert result.type == "navigation_confusion"
    assert result.severity == "medium"
    assert result.steps == (3, 4, 5)


def test_same_page_actions_are_not_navigation_confusion():
    """같은 페이지에서 반복 행동하는 것만으로 탐색 혼란이라 판단하지 않는다."""
    from uxight_agent.watcher.friction_rules import detect_navigation_confusion

    steps = [
        {
            "step": index,
            "url": "A",
            "action": {"kind": "scroll"},
        }
        for index in range(1, 6)
    ]

    assert detect_navigation_confusion(steps) is None


def test_repeated_clicks_are_interaction_failure():
    """같은 화면에서 동일 요소를 3회 클릭하면 조작 실패로 판정한다."""
    from uxight_agent.watcher.friction_rules import detect_interaction_failure

    steps = [
        {
            "step": index,
            "url": "https://example.com/page",
            "action": {"kind": "click", "target": 14},
            "observation": {"elements_hash": "same-screen"},
            "result": {"ok": True, "error_code": None},
        }
        for index in range(1, 4)
    ]

    result = detect_interaction_failure(steps)

    assert result is not None
    assert result.type == "interaction_failure"
    assert result.severity == "medium"
    assert result.steps == (1, 2, 3)


def test_screen_changes_are_not_interaction_failure():
    """화면이 변경되었다면 동일 요소 클릭만으로 실패 판정하지 않는다."""
    from uxight_agent.watcher.friction_rules import detect_interaction_failure

    steps = [
        {
            "step": index,
            "url": "https://example.com/page",
            "action": {"kind": "click", "target": 14},
            "observation": {"elements_hash": f"screen-{index}"},
            "result": {"ok": True, "error_code": None},
        }
        for index in range(1, 4)
    ]

    assert detect_interaction_failure(steps) is None


@pytest.mark.parametrize("error_code", ["PARSE_FAILED", "DOMAIN_BLOCKED"])
def test_non_browser_errors_are_not_interaction_failure(error_code):
    """LLM 파싱 오류와 도메인 차단은 브라우저 조작 실패가 아니다."""
    from uxight_agent.watcher.friction_rules import detect_interaction_failure

    steps = [
        {
            "step": 1,
            "action": None,
            "result": {"ok": False, "error_code": error_code},
            "blocked": {"is": True},
        }
    ]

    assert detect_interaction_failure(steps) is None


@pytest.mark.parametrize(
    "step_count, expected_severity",
    [
        (10, None),
        (11, "low"),
        (15, "low"),
        (16, "medium"),
    ],
)
def test_excessive_steps_boundaries(step_count, expected_severity):
    """성공한 과제의 단계 수 경계값을 검증한다."""
    from uxight_agent.watcher.friction_rules import detect_excessive_steps

    steps = [
        {
            "step": index,
            "task": {"url_reached": index == step_count},
        }
        for index in range(1, step_count + 1)
    ]

    result = detect_excessive_steps(steps, status="done")

    if expected_severity is None:
        assert result is None
    else:
        assert result is not None
        assert result.type == "excessive_steps"
        assert result.severity == expected_severity


def test_failed_task_is_not_excessive_steps():
    """과제 실패는 과도한 단계로 중복 판정하지 않는다."""
    from uxight_agent.watcher.friction_rules import detect_excessive_steps

    steps = [
        {
            "step": index,
            "task": {"url_reached": False},
        }
        for index in range(1, 21)
    ]

    assert detect_excessive_steps(steps, status="max_steps") is None
