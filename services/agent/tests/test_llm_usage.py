import asyncio
import json
from types import SimpleNamespace

import pytest
from conftest import NO_CHOICES

from uxight_agent import usage_report
from uxight_agent.llm import IncompleteStream, LLMClient, record_usage


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
        "reasoning_tokens", "cached_tokens", "latency_ms", "error", "cost_usd",
    }  # fmt: skip
    assert row["cost_usd"] is None  # 단가표에 없는 모델은 비용을 비운다


def test_record_usage_stores_cost_at_call_time(log) -> None:
    # 1M 입력 × $0.10 + 1M 출력 × $0.50 (gpt-6-luna, OpenRouter 단가 100만 토큰당)
    row = record_usage(
        _resp(1_000_000, 1_000_000, 0), role="persona_step", model="gpt-6-luna", latency_ms=1
    )
    assert row["cost_usd"] == pytest.approx(0.60)
    assert _rows(log)[0]["cost_usd"] == pytest.approx(0.60)


def test_report_keeps_cost_recorded_at_call_time(log, monkeypatch) -> None:
    # 부를 때 단가로 남긴 비용을 리포트가 그대로 쓴다.
    # 나중에 단가표가 바뀌어도 지난 비용은 안 바뀐다.
    monkeypatch.setenv("LLM_PRICES", '{"gpt-6-luna": [1, 1, 1]}')
    record_usage(_resp(1_000_000, 0, 0), role="persona_step", model="gpt-6-luna", latency_ms=1)
    monkeypatch.delenv("LLM_PRICES")
    record_usage(_resp(1_000_000, 0, 0), role="persona_step", model="gpt-6-luna", latency_ms=1)

    summary = usage_report.summarize(usage_report.load(log), "model", usage_report.price_table())

    assert summary["total"]["usd"] == pytest.approx(1.00 + 0.10)


def test_report_reads_several_logs(tmp_path, monkeypatch, capsys) -> None:
    # 서버에는 운영 로그와 benchmark 로그가 따로 있다 — 한 번에 묶어 서버 전체 합계를 본다.
    monkeypatch.delenv("LLM_PRICES", raising=False)
    paths = [tmp_path / "a.jsonl", tmp_path / "b.jsonl"]
    for n, path in enumerate(paths, 1):
        monkeypatch.setenv("LLM_USAGE_LOG", str(path))
        for _ in range(n):
            record_usage(
                _resp(1_000_000, 0, 0), role="persona_step", model="gpt-6-luna", latency_ms=1
            )

    assert usage_report.main(["--log", *map(str, paths), "--by", "model"]) == 0

    assert "합계: 호출 3 · 실패 0 · 약 $0.3000" in capsys.readouterr().out


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
    # 리포트는 소수 4자리로 보여 준다 — DB 의 cost_usd 칸과 같은 자리라 견주어 볼 수 있다.
    report = usage_report.render(summary, "run", "t")
    assert report.splitlines()[2].endswith(" 0.0070")
    assert report.splitlines()[3].endswith("약 $0.0070")


@pytest.mark.parametrize(
    ("model", "usd"),
    [
        # 입력 1,000 × 단가 + 출력 1,000 × 단가 (100만 토큰당)
        ("claude-haiku-5-5", 0.0006),  # 0.10 · 0.50
        ("claude-sonnet-5-5", 0.012),  # 2 · 10
        ("claude-opus-5-5", 0.024),  # 4 · 20
    ],
)
def test_claude_models_are_priced(log, model: str, usd: float) -> None:
    # dev 서버 agent 는 11/01 부터 claude-haiku-5-5 를 쓴다. 서버는 기본 단가표만 쓰므로
    # 단가가 없으면 회차 비용 칸이 비어 남는다.
    record_usage(_resp(1_000, 1_000, 0), role="persona_step", model=model, latency_ms=1, run_id=1)

    summary = usage_report.summarize(usage_report.load(log), "run", usage_report.price_table())

    assert summary["groups"]["1"]["usd"] == pytest.approx(usd)
    assert summary["unpriced"] == 0


def test_cached_input_is_billed_at_cache_price(log) -> None:
    resp = _resp(1_000_000, 1_000_000, 0)
    resp.usage.prompt_tokens_details = SimpleNamespace(cached_tokens=400_000)

    row = record_usage(resp, role="persona_step", model="openai/gpt-6-luna", latency_ms=1)

    # 캐시된 40만 × $0.01 + 나머지 입력 60만 × $0.10 + 출력 100만 × $0.50 (100만 토큰당)
    assert row["cached_tokens"] == 400_000
    assert usage_report.cost_usd(row, usage_report.price_table()) == pytest.approx(0.564)


@pytest.mark.parametrize("model", ["openai/gpt-6.1-terra", "gpt-6.1-terra"])
def test_gpt_6_1_terra_is_priced(log, model: str) -> None:
    # 판정 보조 모델(GACA-161). 서버는 기본 단가표만 쓰므로 단가가 없으면 비용 칸이 비어 남는다.
    resp = _resp(1_000_000, 1_000_000, 0)
    resp.usage.prompt_tokens_details = SimpleNamespace(cached_tokens=400_000)

    row = record_usage(resp, role="judge", model=model, latency_ms=1)

    # 캐시된 40만 × $0.05 + 나머지 입력 60만 × $1.00 + 출력 100만 × $5.00 (100만 토큰당)
    assert row["cost_usd"] == pytest.approx(5.62)


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


@pytest.mark.parametrize(
    "value",
    [
        '{"a/b": [1]}',  # 값 1개
        '{"a/b": 0.1}',  # 숫자 하나 (목록이 아님)
        "not json",
        '{"a/b": [-1, 2]}',  # 음수
        '{"a/b": [1, 2, 3, 4]}',
        '{"a/b": [NaN, 2]}',
        '{"a/b": [1, Infinity]}',
        '{"a/b": ["1", 2]}',
        '{"a/b": [true, 2]}',
        '{"a/b": null}',
        "[1, 2]",
    ],
)
def test_malformed_prices_env_is_value_error(monkeypatch, value: str) -> None:
    monkeypatch.setenv("LLM_PRICES", value)

    with pytest.raises(ValueError):
        usage_report.price_table()


def test_prices_env_accepts_two_or_three_numbers_and_zero(monkeypatch) -> None:
    monkeypatch.setenv("LLM_PRICES", '{"a/free": [0, 0], "a/full": [1, 2.5, 0]}')

    table = usage_report.price_table()

    assert table["a/free"] == (0.0, 0.0, 0.0)
    assert table["a/full"] == (1.0, 2.5, 0.0)
    assert table["gpt-6-luna"] == usage_report.GPT_6_LUNA_PRICES  # 기본표는 그대로 남는다


def test_blank_prices_env_means_not_set(monkeypatch) -> None:
    monkeypatch.setenv("LLM_PRICES", "")

    assert usage_report.price_table() == usage_report.DEFAULT_PRICES


def test_slack_text_warns_over_threshold(log) -> None:
    record_usage(
        _resp(1_000_000, 1_000_000, 0), role="judge", model="openai/gpt-5.6-luna", latency_ms=1
    )
    summary = usage_report.summarize(usage_report.load(log), "role", usage_report.price_table())
    report = usage_report.render(summary, "role", "t")
    assert ":warning:" in usage_report.slack_text(summary, report, alert_usd=1.0)
    assert ":warning:" not in usage_report.slack_text(summary, report, alert_usd=5.0)


def test_chat_stream_gives_the_shape_of_chat_and_records_usage(scripted_llm, tmp_path) -> None:
    llm, requests = scripted_llm("긴 답입니다")

    response = asyncio.run(
        llm.chat_stream([{"role": "user", "content": "x"}], role="r", max_tokens=8000, timeout=5)
    )

    assert response.choices[0].message.content == "긴 답입니다"
    assert response.choices[0].finish_reason == "stop"
    assert requests[0]["stream"] is True
    assert requests[0]["max_completion_tokens"] == 8000
    (row,) = _rows(tmp_path / "llm-usage.jsonl")
    assert (row["input_tokens"], row["output_tokens"], row["error"]) == (11, 7, None)


def test_chat_stream_keeps_finish_reason_length(scripted_llm) -> None:
    llm, _ = scripted_llm(("잘린 답", "length"))

    response = asyncio.run(
        llm.chat_stream([{"role": "user", "content": "x"}], role="r", max_tokens=10, timeout=5)
    )

    assert response.choices[0].finish_reason == "length"


def test_chat_stream_failure_is_recorded_and_raised(scripted_llm, tmp_path) -> None:
    llm, _ = scripted_llm(None)

    with pytest.raises(Exception, match="boom"):
        asyncio.run(
            llm.chat_stream([{"role": "user", "content": "x"}], role="r", max_tokens=10, timeout=5)
        )

    (row,) = _rows(tmp_path / "llm-usage.jsonl")
    assert row["error"] == "InternalServerError"


class _SlowStream:
    """조각을 끝없이 천천히 보내는 스트림. 닫혔는지 기억한다."""

    def __init__(self) -> None:
        self.closed = False

    async def __aenter__(self) -> "_SlowStream":
        return self

    async def __aexit__(self, *exc: object) -> None:
        self.closed = True

    def __aiter__(self) -> "_SlowStream":
        return self

    async def __anext__(self) -> SimpleNamespace:
        await asyncio.sleep(0.01)
        return SimpleNamespace(usage=None, choices=[])


def test_chat_stream_timeout_covers_the_whole_answer_and_closes_the_stream(log) -> None:
    # SDK 의 timeout 은 조각 사이만 잰다. 조각이 이어져 와도 답 전체가 상한을 넘으면 멈추고,
    # 끝까지 읽지 않은 스트림도 닫는다.
    stream = _SlowStream()

    class Completions:
        async def create(self, **kw: object) -> _SlowStream:
            return stream

    client = SimpleNamespace(chat=SimpleNamespace(completions=Completions()))
    llm = LLMClient(client=client, model="m")

    with pytest.raises(TimeoutError):
        asyncio.run(llm.chat_stream([], role="r", max_tokens=10, timeout=0.05))

    assert stream.closed
    (row,) = _rows(log)
    assert row["error"] == "TimeoutError"


def test_chat_stream_without_finish_reason_is_a_failed_call(scripted_llm, tmp_path) -> None:
    # 조각이 다 와도 끝난 이유가 없으면 도중에 끊긴 답이다. 사용량 줄에도 실패로 남긴다.
    llm, _ = scripted_llm(NO_CHOICES)

    with pytest.raises(IncompleteStream):
        asyncio.run(
            llm.chat_stream([{"role": "user", "content": "x"}], role="r", max_tokens=10, timeout=5)
        )

    (row,) = _rows(tmp_path / "llm-usage.jsonl")
    assert (row["error"], row["input_tokens"]) == ("IncompleteStream", 11)


class _ListStream:
    """정해 둔 조각을 차례로 보내는 스트림."""

    def __init__(self, chunks: list) -> None:
        self._chunks = list(chunks)

    async def __aenter__(self) -> "_ListStream":
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None

    def __aiter__(self) -> "_ListStream":
        return self

    async def __anext__(self) -> SimpleNamespace:
        if not self._chunks:
            raise StopAsyncIteration
        return self._chunks.pop(0)


def test_chat_stream_takes_a_chunk_whose_choices_is_null(log) -> None:
    # 사용량 조각에 choices 가 [] 가 아니라 null 로 오는 제공자도 있다.
    delta = SimpleNamespace(content="답")
    chunks = [
        SimpleNamespace(usage=None, choices=[SimpleNamespace(delta=delta, finish_reason="stop")]),
        SimpleNamespace(usage=None, choices=None),
    ]

    class Completions:
        async def create(self, **kw: object) -> _ListStream:
            return _ListStream(chunks)

    client = SimpleNamespace(chat=SimpleNamespace(completions=Completions()))
    response = asyncio.run(
        LLMClient(client=client, model="m").chat_stream([], role="r", max_tokens=10, timeout=5)
    )

    assert response.choices[0].message.content == "답"
