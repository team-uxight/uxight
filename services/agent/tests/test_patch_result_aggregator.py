"""GACA-170: 회차별 패치 적용 결과 집계 테스트."""

from uxight_agent.patch.result_aggregator import aggregate_patch_results


def approved_patch():
    return {
        "improvement_id": 10,
        "patch_kind": "relabel",
        "patch": {
            "target": "#menu",
            "new_text": "장학금 안내",
            "page_url": "https://example.com/",
        },
    }


def attempt(applied=True, reason=None):
    return {
        "improvement_id": 10,
        "applied": applied,
        "fail_reason": reason,
    }


def test_all_personas_succeed():
    rows = aggregate_patch_results(
        [approved_patch()],
        {
            1: [attempt()],
            2: [attempt()],
            3: [attempt()],
        },
    )

    assert len(rows) == 1
    assert rows[0]["applied"] is True
    assert rows[0]["fail_reason"] is None


def test_one_persona_fails():
    rows = aggregate_patch_results(
        [approved_patch()],
        {
            1: [attempt()],
            2: [attempt(False, "Target not found")],
            3: [attempt()],
        },
    )

    assert rows[0]["applied"] is False
    assert "persona=2" in rows[0]["fail_reason"]
    assert "Target not found" in rows[0]["fail_reason"]


def test_persona_never_visits_target_page():
    rows = aggregate_patch_results(
        [approved_patch()],
        {
            1: [attempt()],
            2: [],
        },
    )

    assert rows[0]["applied"] is False
    assert "persona=2" in rows[0]["fail_reason"]
    assert "not visited" in rows[0]["fail_reason"]


def test_repeated_observation_preserves_failure():
    rows = aggregate_patch_results(
        [approved_patch()],
        {
            1: [
                attempt(False, "Selector missing"),
                attempt(True),
            ],
        },
    )

    assert rows[0]["applied"] is False
    assert "Selector missing" in rows[0]["fail_reason"]


def test_no_persona_results_is_not_success():
    rows = aggregate_patch_results([approved_patch()], {})

    assert rows[0]["applied"] is False
    assert rows[0]["fail_reason"] == "No persona execution results"


def test_no_approved_patches():
    assert aggregate_patch_results([], {1: []}) == []


def test_repeated_failures_are_merged_and_capped():
    """같은 실패가 관측마다 쌓여도 사유는 한 번만 적고 2,000자 안으로 저장한다."""
    reason = "Error: Page.evaluate: Error: Expected exactly one element for #a, found 0"
    rows = aggregate_patch_results(
        [approved_patch()],
        {persona_id: [attempt(False, reason)] * 120 for persona_id in range(1, 6)},
    )

    assert rows[0]["applied"] is False
    assert rows[0]["fail_reason"] == f"persona=1,2,3,4,5: {reason}"


def test_long_fail_reason_is_truncated():
    rows = aggregate_patch_results(
        [approved_patch()],
        {
            persona_id: [attempt(False, f"Reason {persona_id} " + "x" * 300)]
            for persona_id in range(1, 21)
        },
    )

    fail_reason = rows[0]["fail_reason"]
    assert len(fail_reason) <= 2000
    assert fail_reason.endswith("(truncated)")
    assert fail_reason.startswith("persona=1: Reason 1 ")
