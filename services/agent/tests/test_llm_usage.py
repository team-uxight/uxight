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

    async def create(self, **kw: object) -> SimpleNamespace:
        self.calls.append("create")
        if self.fail:
            raise TimeoutError("boom")
        return _resp()

    async def parse(self, **kw: object) -> SimpleNamespace:
        self.calls.append("parse")
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


def test_slack_text_warns_over_threshold(log) -> None:
    record_usage(
        _resp(1_000_000, 1_000_000, 0), role="judge", model="openai/gpt-5.6-luna", latency_ms=1
    )
    summary = usage_report.summarize(usage_report.load(log), "role", usage_report.price_table())
    report = usage_report.render(summary, "role", "t")
    assert ":warning:" in usage_report.slack_text(summary, report, alert_usd=1.0)
    assert ":warning:" not in usage_report.slack_text(summary, report, alert_usd=5.0)
