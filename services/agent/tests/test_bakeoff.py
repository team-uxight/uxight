from uxight_agent import bakeoff


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
