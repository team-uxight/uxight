import pytest

from uxight_agent import bakeoff, usage_report


def test_cases_have_labels_in_allowed_values() -> None:
    allowed_types = set(bakeoff.FrictionCall.model_fields["type"].annotation.__args__)
    for task in bakeoff.SCHEMA:
        cases = bakeoff.load_cases(task)
        assert len(cases) == 10
        assert len({c["id"] for c in cases}) == 10
        for c in cases:
            assert bakeoff.ANSWER_KEY[task] in c["label"], c["id"]
        if task == "friction":
            assert {c["label"]["type"] for c in cases} <= allowed_types


def test_score_and_model_arg() -> None:
    assert bakeoff.score("judge", {"success": True}, {"success": True, "evidence": "x"})
    assert not bakeoff.score("judge", {"success": True}, None)
    assert bakeoff.parse_model_arg("terra=openai/gpt-5.6-terra@OPENROUTER") == (
        "terra",
        "openai/gpt-5.6-terra",
        "OPENROUTER",
    )
    assert bakeoff.parse_model_arg("luna=openai/gpt-5.6-luna")[2] == "LLM"


def test_summarize_accuracy_consistency_cost() -> None:
    calls = [
        {
            "model": "m",
            "task": "judge",
            "case": "J01",
            "answer": {"success": True},
            "correct": True,
        },
        {
            "model": "m",
            "task": "judge",
            "case": "J01",
            "answer": {"success": False},
            "correct": False,
        },
        {"model": "m", "task": "judge", "case": "J02", "answer": None, "correct": False},
        {"model": "m", "task": "judge", "case": "J02", "answer": None, "correct": False},
    ]
    usage = [
        {"model": "openai/gpt-5.6-luna", "role": "bakeoff_judge", "input_tokens": 0,
         "output_tokens": 0, "latency_ms": 2000},
        {"model": "m", "role": "bakeoff_judge", "input_tokens": 1_000_000, "output_tokens": 0,
         "latency_ms": 1000},
    ]  # fmt: skip
    (row,) = bakeoff.summarize(calls, usage)
    assert row["accuracy"] == 0.25 and row["valid"] == 0.5
    assert row["consistency"] == 0.75  # J01 은 둘이 갈리고(0.5), J02 는 둘 다 무응답(1.0)
    assert row["latency_s"] == 1.0 and row["usd_per_call"] is None  # 모델 m 은 단가가 없다


def test_bakeoff_shares_the_price_table_with_usage_report() -> None:
    # 단가표는 usage_report 한 곳이다 — 모델을 더하거나 값을 고쳐도 비교 표가 같이 바뀐다.
    assert bakeoff.price_table is usage_report.price_table
    assert bakeoff.cost_usd is usage_report.cost_usd


def test_summarize_prices_gpt_6_luna_with_cached_input() -> None:
    calls = [
        {
            "model": "openai/gpt-6-luna",
            "task": "judge",
            "case": "J01",
            "answer": {"success": True},
            "correct": True,
        }
    ]
    usage = [
        {"model": "openai/gpt-6-luna", "role": "bakeoff_judge", "input_tokens": 1_000_000,
         "cached_tokens": 500_000, "output_tokens": 0, "latency_ms": 1000},
    ]  # fmt: skip
    (row,) = bakeoff.summarize(calls, usage)
    # 캐시 안 된 입력 50만 × $0.10 + 캐시된 입력 50만 × $0.01 (100만 토큰당)
    assert row["usd_per_call"] == pytest.approx(0.055)
