import asyncio
import json
from types import SimpleNamespace

import pytest

from uxight_agent import usage_report
from uxight_agent.llm import LLMClient, record_usage


def _resp(inp: int = 100, out: int = 50, reasoning: int = 30) -> SimpleNamespace:
    usage = SimpleNamespace(
        prompt_tokens=inp,
        completion_tokens=out,
        completion_tokens_details=SimpleNamespace(reasoning_tokens=reasoning),
        prompt_tokens_details=None,
    )
    return SimpleNamespace(usage=usage)


class _FakeCompletions:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[str] = []
        self.kw: dict[str, object] = {}

    async def create(self, **kw: object) -> SimpleNamespace:
        self.calls.append("create")
        self.kw = kw
        if self.fail:
            raise TimeoutError("boom")
        return _resp()

    async def parse(self, **kw: object) -> SimpleNamespace:
        self.calls.append("parse")
        self.kw = kw
        return _resp(10, 5, 0)


def _client(fail: bool = False) -> tuple[SimpleNamespace, _FakeCompletions]:
    comp = _FakeCompletions(fail)
    return SimpleNamespace(chat=SimpleNamespace(completions=comp)), comp


@pytest.fixture
def log(tmp_path, monkeypatch):
    path = tmp_path / "usage.jsonl"
    monkeypatch.setenv("LLM_USAGE_LOG", str(path))
    monkeypatch.delenv("LLM_PRICES", raising=False)
    return path


def _rows(path) -> list[dict]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()]


def test_record_usage_keeps_counts_not_content(log) -> None:
    row = record_usage(_resp(), role="persona_step", model="m", latency_ms=12, run_id=7)
    assert (row["input_tokens"], row["output_tokens"], row["reasoning_tokens"]) == (100, 50, 30)
    assert _rows(log) == [row]
    assert set(row) == {
        "ts", "role", "model", "run_id", "persona_id", "input_tokens", "output_tokens",
        "reasoning_tokens", "cached_tokens", "latency_ms", "error",
    }  # fmt: skip


def test_chat_records_success_and_failure(log) -> None:
    client, comp = _client()
    llm = LLMClient(client=client, model="openai/gpt-5.6-luna")
    msgs = [{"role": "user", "content": "hi"}]
    asyncio.run(llm.chat(msgs, role="judge", max_tokens=200, response_format=dict))
    assert comp.calls == ["parse"]
    # 추론 모델(Luna)은 max_tokens 를 400 으로 거절한다 — API 에는 max_completion_tokens 로 보낸다
    assert comp.kw["max_completion_tokens"] == 200 and "max_tokens" not in comp.kw

    failing, _ = _client(fail=True)
    with pytest.raises(TimeoutError):
        asyncio.run(LLMClient(client=failing, model="m").chat(msgs, role="judge", max_tokens=10))

    ok, failed = _rows(log)
    assert ok["error"] is None and ok["input_tokens"] == 10
    assert failed["error"] == "TimeoutError" and failed["input_tokens"] == 0


def test_report_cost_and_unpriced(log, monkeypatch) -> None:
    for model in ("openai/gpt-5.6-luna", "other/model"):
        record_usage(_resp(1_000_000, 1_000_000, 0), role="persona_step", model=model, latency_ms=1)
    summary = usage_report.summarize(usage_report.load(log), "model", usage_report.price_table())
    assert summary["groups"]["openai/gpt-5.6-luna"]["usd"] == pytest.approx(1.40)
    assert summary["unpriced"] == 1

    monkeypatch.setenv("LLM_PRICES", '{"other/model": [1, 2]}')
    summary = usage_report.summarize(usage_report.load(log), "model", usage_report.price_table())
    assert summary["total"]["usd"] == pytest.approx(4.40)


# dev 회차 9 의 실제 합계: 입력 47,080 · 출력 4,588 · 캐시 0, 호출 10번. 호출별 나눔은 어림이다.
DEV_RUN_9_CALLS = [
    (1_900, 410), (3_100, 520), (3_800, 380), (4_400, 450), (4_900, 470),
    (5_300, 500), (5_600, 440), (5_800, 460), (5_900, 480), (6_380, 478),
]  # fmt: skip


@pytest.mark.parametrize("model", ["openai/gpt-6-luna", "gpt-6-luna"])
def test_gpt_6_luna_cost_of_dev_run_9(log, model: str) -> None:
    for inp, out in DEV_RUN_9_CALLS:
        record_usage(_resp(inp, out, 0), role="persona_step", model=model, latency_ms=1, run_id=9)

    summary = usage_report.summarize(usage_report.load(log), "run", usage_report.price_table())

    # 입력 47,080 × $0.10 + 출력 4,588 × $0.50 (100만 토큰당) = 0.004708 + 0.002294
    assert summary["groups"]["9"]["usd"] == pytest.approx(0.007002)
    assert round(summary["total"]["usd"], 4) == 0.0070
    assert summary["unpriced"] == 0


def test_cached_input_is_billed_at_cache_price(log) -> None:
    resp = _resp(1_000_000, 1_000_000, 0)
    resp.usage.prompt_tokens_details = SimpleNamespace(cached_tokens=400_000)

    row = record_usage(resp, role="persona_step", model="openai/gpt-6-luna", latency_ms=1)

    # 캐시된 40만 × $0.01 + 나머지 입력 60만 × $0.10 + 출력 100만 × $0.50 (100만 토큰당)
    assert row["cached_tokens"] == 400_000
    assert usage_report.cost_usd(row, usage_report.price_table()) == pytest.approx(0.564)


def test_reasoning_tokens_are_not_billed_twice(log) -> None:
    # 출력 1,660 안에 추론 1,559 가 들어 있다 (실제 기록의 모양) — 출력 단가는 1,660 에만 곱한다.
    row = record_usage(_resp(0, 1660, 1559), role="persona_step", model="gpt-6-luna", latency_ms=1)

    assert row["reasoning_tokens"] <= row["output_tokens"]
    expected = 1660 * 0.50 / 1_000_000
    assert usage_report.cost_usd(row, usage_report.price_table()) == pytest.approx(expected)


def test_cache_price_in_env_is_optional(monkeypatch) -> None:
    monkeypatch.setenv("LLM_PRICES", '{"a/with": [1, 2, 0.5], "a/without": [1, 2]}')
    table = usage_report.price_table()
    cached_call = {"input_tokens": 1_000_000, "cached_tokens": 1_000_000, "output_tokens": 0}

    assert usage_report.cost_usd({"model": "a/with", **cached_call}, table) == pytest.approx(0.5)
    # 캐시 단가를 안 주면 캐시된 입력도 입력 단가로 센다
    assert usage_report.cost_usd({"model": "a/without", **cached_call}, table) == pytest.approx(1.0)


def test_slack_text_warns_over_threshold(log) -> None:
    record_usage(
        _resp(1_000_000, 1_000_000, 0), role="judge", model="openai/gpt-5.6-luna", latency_ms=1
    )
    summary = usage_report.summarize(usage_report.load(log), "role", usage_report.price_table())
    report = usage_report.render(summary, "role", "t")
    assert ":warning:" in usage_report.slack_text(summary, report, alert_usd=1.0)
    assert ":warning:" not in usage_report.slack_text(summary, report, alert_usd=5.0)
