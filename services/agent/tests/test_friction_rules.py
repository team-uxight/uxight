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
    5: [("none", "none")],  # fail 은 판정 안 함이라 Friction 을 만들지 않는다
}


@pytest.mark.parametrize("persona_id", [1, 2, 3, 4, 5])
def test_sample_persona_frictions(persona_id):
    """샘플 행동 로그의 Friction 유형과 심각도를 검증한다."""
    if not (FIXTURE_ROOT / "run.json").exists():
        pytest.skip("GACA-46 샘플 로그가 아직 제공되지 않음")

    run = json.loads((FIXTURE_ROOT / "run.json").read_text(encoding="utf-8"))
    persona = next(p for p in run["personas"] if p["persona_id"] == persona_id)

    path = FIXTURE_ROOT / str(persona_id) / "steps.jsonl"
    steps = [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]

    results = detect_frictions(steps, status=persona["status"])
    actual = [(r.type, r.severity) for r in results]

    if not actual:
        actual = [("none", "none")]

    assert actual == EXPECTED[persona_id]


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


def test_excessive_steps_uses_first_goal_reached():
    """목표 URL에 처음 도달한 시점을 기준으로 단계 수를 계산한다."""
    from uxight_agent.watcher.friction_rules import detect_excessive_steps

    steps = [{"step": index, "task": {"url_reached": index == 8}} for index in range(1, 16)]

    assert detect_excessive_steps(steps, status="done") is None


def test_excessive_steps_detects_late_goal_reached():
    """목표 URL에 늦게 도달하면 이후 이동 여부와 관계없이 탐지한다."""
    from uxight_agent.watcher.friction_rules import detect_excessive_steps

    steps = [{"step": index, "task": {"url_reached": index == 12}} for index in range(1, 16)]

    result = detect_excessive_steps(steps, status="done")

    assert result is not None
    assert result.type == "excessive_steps"
    assert result.severity == "low"
    assert result.steps == (12,)


def test_goal_reached_before_done_is_not_task_failure():
    """목표 URL에 도달한 뒤 다른 페이지로 이동해도 과제 실패로 판정하지 않는다."""
    from uxight_agent.watcher.friction_rules import detect_task_failure

    steps = [
        {
            "step": 1,
            "action": {"kind": "click"},
            "task": {"url_reached": False},
        },
        {
            "step": 2,
            "action": {"kind": "click"},
            "task": {"url_reached": True},
        },
        {
            "step": 3,
            "action": {"kind": "done"},
            "task": {"url_reached": False},
        },
    ]

    assert detect_task_failure(steps, status="done") is None


@pytest.mark.parametrize(
    "error_code",
    [
        "ELEMENT_NOT_FOUND",
        "ELEMENT_NOT_INTERACTABLE",
        "BROWSER_ACTION_FAILED",
    ],
)
def test_browser_action_error_has_evidence_step(error_code):
    """브라우저 조작 오류를 탐지하고 오류 발생 Step을 근거로 기록한다."""
    from uxight_agent.watcher.friction_rules import detect_interaction_failure

    steps = [
        {
            "step": 1,
            "url": "https://example.com/page",
            "action": {"kind": "click", "target": 10},
            "result": {"ok": True, "error_code": None},
        },
        {
            "step": 2,
            "url": "https://example.com/page",
            "action": {"kind": "click", "target": 20},
            "result": {"ok": False, "error_code": error_code},
        },
    ]

    result = detect_interaction_failure(steps)

    assert result is not None
    assert result.type == "interaction_failure"
    assert result.severity == "medium"
    assert result.steps == (2,)
    assert error_code in result.reason


@pytest.mark.parametrize("status", ["max_steps", "stuck", "timeout"])
def test_failed_task_has_evidence_step(status):
    """못 닿고 끝난 Persona 를 탐지하고 마지막 Step을 근거로 기록한다."""
    from uxight_agent.watcher.friction_rules import detect_task_failure

    steps = [
        {
            "step": 1,
            "action": {"kind": "click"},
            "task": {"url_reached": False},
            "result": {"ok": True, "error_code": None},
        },
        {
            "step": 2,
            "action": {"kind": "click"},
            "task": {"url_reached": False},
            "result": {"ok": True, "error_code": None},
        },
        {
            "step": 3,
            "action": {"kind": "click"},
            "task": {"url_reached": False},
            "result": {"ok": False, "error_code": None},
        },
    ]

    result = detect_task_failure(steps, status=status)

    assert result is not None
    assert result.type == "task_failure"
    assert result.severity == "high"
    assert result.steps == (3,)
    assert status in result.reason


def logged(reached: list[bool | None]) -> list[dict]:
    """step 마다 다른 화면으로 움직인 로그. 도달 기록만 인자로 정한다."""
    return [
        {
            "step": index,
            "url": f"https://example.com/{index}",
            "action": {"kind": "click", "target": index},
            "result": {"ok": True, "error_code": None},
            "task": {"url_reached": value},
        }
        for index, value in enumerate(reached, start=1)
    ]


@pytest.mark.parametrize(
    "status, severity",
    [
        ("done", "medium"),
        ("max_steps", "high"),
        ("stuck", "high"),
        ("timeout", "high"),
        ("token_limit", "medium"),
    ],
)
def test_never_reached_is_task_failure(status, severity):
    """11/03 결정의 실패: 한 번도 못 닿으면 끝난 이유와 상관없이 과제 실패다."""
    [result] = detect_frictions(logged([False, False]), status=status)

    assert (result.type, result.severity, result.steps) == ("task_failure", severity, (2,))


@pytest.mark.parametrize("status", ["max_steps", "stuck", "timeout", "token_limit"])
def test_hard_success_uses_steps_after_first_reach(status):
    """11/03 결정의 어렵게 성공: 과제 실패가 아니고, 처음 닿은 뒤 step 이 근거다."""
    [result] = detect_frictions(logged([False, True, False, False]), status=status)

    assert (result.type, result.severity, result.steps) == ("excessive_steps", "low", (3, 4))
    assert status in result.reason


def test_hard_success_counts_steps_after_reach_for_confusion():
    """어렵게 성공의 길 찾기 혼란은 처음 닿은 뒤 step 도 세고, 닿기 전 step 과 함께 근거로 쓴다."""
    steps = logged([False, True, False, False, False])
    for step, url in zip(steps, ["A", "B", "A", "B", "A"], strict=True):
        step["url"] = url

    results = detect_frictions(steps, status="stuck")

    assert [(r.type, r.steps) for r in results] == [
        ("navigation_confusion", (3, 4, 5)),
        ("excessive_steps", (3, 4, 5)),
    ]


def test_hard_success_counts_all_steps_for_severity():
    """끝까지 쓴 step 이 16개 이상이면 중간이다."""
    [result] = detect_frictions(logged([True] + [False] * 15), status="max_steps")

    assert result.severity == "medium"
    assert result.steps == tuple(range(2, 17))


@pytest.mark.parametrize("count, expected", [(10, []), (12, [(12,)])])
def test_hard_success_reached_on_last_step_uses_threshold(count, expected):
    """마지막 step 에서 닿았으면 더 움직인 step 이 없어 기준대로 판정한다."""
    results = detect_frictions(logged([False] * (count - 1) + [True]), status="max_steps")

    assert [r.steps for r in results] == expected


@pytest.mark.parametrize("status", ["fail", "cancelled", None])
def test_unjudged_status_makes_no_friction(status):
    """11/03 결정의 판정 안 함: 실행 오류 · 취소 · 끝난 이유를 모름은 Friction 을 만들지 않는다."""
    steps = logged([True, False, False])
    steps[1]["result"]["error_code"] = "BROWSER_ACTION_FAILED"

    assert detect_frictions(steps, status=status) == []


def test_all_null_reached_makes_no_friction():
    """도달 기록이 모두 비면 판정 안 함이다. 뒤로 가기 · 오류가 있어도 Friction 이 없다."""
    steps = logged([None, None, None])
    steps[0]["action"]["kind"] = "back"
    steps[1]["action"]["kind"] = "back"
    steps[2]["result"]["error_code"] = "ELEMENT_NOT_FOUND"

    assert detect_frictions(steps, status="max_steps") == []


def test_partly_null_reached_is_still_judged():
    """비교하지 못한 step 이 섞여도 못 닿은 기록이 있으면 판정한다."""
    [result] = detect_frictions(logged([None, False]), status="done")

    assert result.type == "task_failure"
