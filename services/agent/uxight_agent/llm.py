"""LLM 호출은 전부 `LLMClient.chat()` 한 곳을 거친다 (GACA-106). 호출마다 사용량을 한 줄씩 남긴다.

- 주소 · 키 · 모델은 env 로만: LLM_BASE_URL · LLM_API_KEY · LLM_MODEL.
  제공자를 바꿀 땐 env 만 바꾼다.
- 사용량 로그: LLM_USAGE_LOG (기본 data/llm-usage.jsonl). 한 줄 = 호출 한 번. 비용 리포트는
  `uv run python -m uxight_agent.usage_report`.
- 로그에는 토큰 수 · 비용(부를 때의 단가) · 걸린 시간 · 역할 · 실행 id 만 남긴다.
  키 · 프롬프트 · 응답 본문은 남기지 않는다.
"""

import asyncio
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from openai import AsyncOpenAI


def usage_log_path() -> Path:
    return Path(os.environ.get("LLM_USAGE_LOG", "data/llm-usage.jsonl"))


def record_usage(
    response: Any,
    *,
    role: str,
    model: str,
    latency_ms: int,
    run_id: int | None = None,
    persona_id: str | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    """응답의 usage 를 한 줄로 남긴다. 실패한 호출도 남긴다 — 재시도가 몰리는 걸 보려고."""
    usage = getattr(response, "usage", None)
    out_details = getattr(usage, "completion_tokens_details", None)
    in_details = getattr(usage, "prompt_tokens_details", None)
    row = {
        "ts": datetime.now(UTC).isoformat(timespec="seconds"),
        "role": role,
        "model": model,
        "run_id": run_id,
        "persona_id": persona_id,
        "input_tokens": getattr(usage, "prompt_tokens", 0) or 0,
        "output_tokens": getattr(usage, "completion_tokens", 0) or 0,  # 추론 토큰이 여기 포함된다
        "reasoning_tokens": getattr(out_details, "reasoning_tokens", 0) or 0,
        "cached_tokens": getattr(in_details, "cached_tokens", 0) or 0,
        "latency_ms": latency_ms,
        "error": error,
    }
    # 부를 때의 단가(OpenRouter 기준)로 비용을 같이 남긴다. 단가표에 없는 모델이면 None.
    from .usage_report import cost_usd, price_table  # usage_report 가 이 모듈을 불러서 여기서

    row["cost_usd"] = cost_usd(row, price_table())
    path = usage_log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


class LLMClient:
    """`chat()` 하나. `response_format` 을 주면 구조화 출력(parse), 없으면 일반 응답."""

    def __init__(
        self, client: Any | None = None, model: str | None = None, max_retries: int = 2
    ) -> None:
        # max_retries: 실패한 호출을 SDK 가 다시 보내는 횟수 (SDK 기본 2).
        self.model = model or os.environ["LLM_MODEL"]
        self._client = client or AsyncOpenAI(
            base_url=os.environ["LLM_BASE_URL"],
            api_key=os.environ["LLM_API_KEY"],
            max_retries=max_retries,
        )

    async def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        role: str,
        max_tokens: int,
        response_format: type | None = None,
        run_id: int | None = None,
        persona_id: str | None = None,
        **kwargs: Any,
    ) -> Any:
        completions = self._client.chat.completions
        call = completions.create
        if response_format is not None:
            call = completions.parse
            kwargs["response_format"] = response_format
        start = time.monotonic()
        meta = {"role": role, "model": self.model, "run_id": run_id, "persona_id": persona_id}
        try:
            # Luna 같은 추론 모델은 max_tokens 를 400 으로 거절한다 — 같은 한도를 새 이름으로 보낸다
            resp = await call(
                model=self.model, messages=messages, max_completion_tokens=max_tokens, **kwargs
            )
        except Exception as e:
            record_usage(None, latency_ms=_ms(start), error=type(e).__name__, **meta)
            raise
        record_usage(resp, latency_ms=_ms(start), **meta)
        return resp

    async def chat_stream(
        self,
        messages: list[dict[str, Any]],
        *,
        role: str,
        max_tokens: int,
        timeout: float,
        run_id: int | None = None,
        persona_id: str | None = None,
    ) -> Any:
        """chat() 과 같은 모양의 답을 스트리밍으로 받는다 (GACA-181).

        MLAPI 프록시는 스트리밍 아닌 답의 한도를 2000 까지만 받는다. 그보다 긴 답에 쓴다.
        timeout 은 답 전체의 상한(초)이다. SDK 의 timeout 은 조각 사이의 시간만 재서 따로 건다.
        사용량은 마지막 조각에 온다(stream_options include_usage, MLAPI 에서 확인했다). 그 조각이
        없으면 토큰이 0 으로 남는다. 답이 도중에 끊기면 쓴 토큰을 알 수 없어 실패로만 남긴다.
        스트림은 끝까지 읽지 않고 빠져도(시간 초과 · 오류) 닫는다.
        finish_reason 이 한 번도 오지 않은 답은 choices 가 빈 답으로 돌려준다.
        """
        start = time.monotonic()
        meta = {"role": role, "model": self.model, "run_id": run_id, "persona_id": persona_id}
        texts: list[str] = []
        finish_reason, usage = None, None
        try:
            async with asyncio.timeout(timeout):
                stream = await self._client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    max_completion_tokens=max_tokens,
                    stream=True,
                    stream_options={"include_usage": True},
                    timeout=timeout,
                )
                async with stream:
                    async for chunk in stream:
                        usage = chunk.usage or usage
                        for choice in chunk.choices:
                            texts.append((choice.delta.content if choice.delta else None) or "")
                            finish_reason = choice.finish_reason or finish_reason
        except Exception as e:
            record_usage(None, latency_ms=_ms(start), error=type(e).__name__, **meta)
            raise
        message = SimpleNamespace(content="".join(texts))
        choice = SimpleNamespace(finish_reason=finish_reason, message=message)
        response = SimpleNamespace(usage=usage, choices=[choice] if finish_reason else [])
        record_usage(response, latency_ms=_ms(start), **meta)
        return response


def _ms(start: float) -> int:
    return int((time.monotonic() - start) * 1000)
