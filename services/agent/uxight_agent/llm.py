"""LLM 호출은 전부 `LLMClient.chat()` 한 곳을 거친다 (GACA-106). 호출마다 사용량을 한 줄씩 남긴다.

- 주소 · 키 · 모델은 env 로만: LLM_BASE_URL · LLM_API_KEY · LLM_MODEL.
  제공자를 바꿀 땐 env 만 바꾼다.
- 사용량 로그: LLM_USAGE_LOG (기본 data/llm-usage.jsonl). 한 줄 = 호출 한 번. 비용 리포트는
  `uv run python -m uxight_agent.usage_report`.
- 로그에는 토큰 수 · 걸린 시간 · 역할 · 실행 id 만 남긴다.
  키 · 프롬프트 · 응답 본문은 남기지 않는다.
"""

import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path
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
    path = usage_log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


class LLMClient:
    """`chat()` 하나. `response_format` 을 주면 구조화 출력(parse), 없으면 일반 응답."""

    def __init__(self, client: Any | None = None, model: str | None = None) -> None:
        self.model = model or os.environ["LLM_MODEL"]
        self._client = client or AsyncOpenAI(
            base_url=os.environ["LLM_BASE_URL"], api_key=os.environ["LLM_API_KEY"]
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
            resp = await call(model=self.model, messages=messages, max_tokens=max_tokens, **kwargs)
        except Exception as e:
            record_usage(None, latency_ms=_ms(start), error=type(e).__name__, **meta)
            raise
        record_usage(resp, latency_ms=_ms(start), **meta)
        return resp


def _ms(start: float) -> int:
    return int((time.monotonic() - start) * 1000)
