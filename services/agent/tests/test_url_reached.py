"""GACA-159: 목표 URL 비교 규칙 테스트."""

from uxight_agent.watcher.step_rules import same_url


def test_success_url_reached():
    assert same_url(
        "https://example.com/goal",
        "https://example.com/goal",
    ) is True


def test_success_url_not_reached():
    assert same_url(
        "https://example.com/other",
        "https://example.com/goal",
    ) is False


def test_url_fragment_and_trailing_slash():
    assert same_url(
        "https://example.com/goal/#section",
        "https://example.com/goal",
    ) is True


def test_unknown_url_after_action_is_null():
    """행동 후 URL을 확인할 수 없으면 목표 도달 여부는 null이다."""
    from datetime import datetime

    from uxight_agent.driver.base import ActionResult, Observation
    from uxight_agent.persona.persona_agent import Decision, StepResult
    from uxight_agent.schemas import Action
    from uxight_agent.watcher.step_rules import to_step_log

    now = datetime.now().astimezone()
    step = StepResult(
        observation=Observation(
            url="https://example.com/goal",
            title="Goal",
            dom="",
            element_map={},
        ),
        decision=Decision(
            action=Action(kind="click", element_id=1),
        ),
        result=ActionResult(
            ok=True,
            url_after=None,
        ),
        started_at=now,
        finished_at=now,
        browser_ms=10,
    )

    log = to_step_log(
        run_id=1,
        persona_id=1,
        step_no=1,
        step=step,
        task={"success_url": "https://example.com/goal"},
        mode="dom",
        screenshot=None,
    )

    assert log["task"]["url_reached"] is None
