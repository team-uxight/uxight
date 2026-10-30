"""LLM 판단기 (GACA-151). step 마다 LLM 을 한 번 불러 행동 5종 중 하나를 받는다.

- 답의 형식은 StepReply 스키마(response_format, strict)로 요청하고, 받은 글을 여기서 직접
  StepReply 로 검증한다. SDK 의 parse() 를 쓰지 않는 까닭: 검증이 실패해도 응답(사용량 ·
  reasoning)을 잃지 않으려고. 모르는 칸 · 다른 행동 종류 · 행동별 필수 칸 누락은 거부한다 (D18).
- 깨진 답은 예외 대신 action=None 인 Decision 으로 돌려준다 — 그 step 은 실행하지 않고
  기록된다 (행동 로그 명세 3.8). LLM 호출 실패도 같은 방식이다.
"""

import json
import time

from openai import APIError, APITimeoutError
from openai.lib._parsing import type_to_response_format_param
from pydantic import BaseModel, ConfigDict, ValidationError

from ..driver.base import Observation
from ..llm import LLMClient
from ..schemas import Action
from .persona_agent import Decider, Decision, StepResult
from .prompt import build_messages

STEP_ROLE = "persona_step"
# 추론 모델은 생각 토큰도 이 한도에 든다 — 너무 작으면 답이 잘려 파싱 실패가 된다 (AGENTS.md).
STEP_MAX_TOKENS = 2000
# step 호출 하나의 상한(초)과 SDK 재시도 횟수. 응답이 없는 호출이 Persona 시간을 다 먹지 않게.
STEP_TIMEOUT_SECONDS = 60
STEP_MAX_RETRIES = 1


class StepReply(BaseModel):
    """LLM 이 step 마다 내는 답. 모르는 칸은 거부한다."""

    model_config = ConfigDict(extra="forbid")

    reasoning: str
    action: Action


# SDK 가 parse() 에서 보내는 것과 같은 strict JSON schema 형식 (모든 칸 필수 · 추가 칸 금지).
STEP_REPLY_FORMAT = type_to_response_format_param(StepReply)


class LLMDecider(Decider):
    """LLMClient 를 주입받는다 — 테스트는 가짜 클라이언트를 넣는다. run_id 는 사용량 기록용."""

    def __init__(self, llm: LLMClient, run_id: int | None = None) -> None:
        self._llm = llm
        self._run_id = run_id

    async def decide(
        self, persona: dict, task: dict, observation: Observation, history: list[StepResult]
    ) -> Decision:
        messages = build_messages(persona, task, observation, history)
        start = time.monotonic()
        try:
            # response_format 을 본문에 직접 실어 create() 로 부른다 — parse() 처럼 SDK 가
            # 검증하다 예외를 내면 응답이 사라진다. 사용량은 LLMClient 가 그대로 남긴다.
            response = await self._llm.chat(
                messages,
                role=STEP_ROLE,
                max_tokens=STEP_MAX_TOKENS,
                run_id=self._run_id,
                persona_id=str(persona["persona_id"]),
                timeout=STEP_TIMEOUT_SECONDS,
                extra_body={"response_format": STEP_REPLY_FORMAT},
            )
        except APITimeoutError:
            return self._failed(start, None, "LLM_REQUEST_TIMEOUT", "LLM request timed out")
        except APIError as e:
            return self._failed(
                start, None, "LLM_REQUEST_FAILED", f"LLM request failed: {type(e).__name__}"
            )

        usage = getattr(response, "usage", None)
        if not response.choices:
            return self._failed(start, usage, "LLM_REQUEST_FAILED", "LLM returned no choices")
        choice = response.choices[0]
        content = choice.message.content
        if choice.finish_reason in ("length", "content_filter") or not content:
            # 한도에 걸려 잘림(length) · 걸러짐 · 거절 — 읽을 JSON 이 없다.
            return self._failed(start, usage, "PARSE_FAILED", "Action JSON parsing failed")
        try:
            reply = StepReply.model_validate_json(content)
        except ValidationError as e:
            if any(err["type"] == "json_invalid" for err in e.errors()):
                return self._failed(start, usage, "PARSE_FAILED", "Action JSON parsing failed")
            return self._failed(
                start,
                usage,
                "INVALID_ACTION",
                "Action is outside the action schema",
                reasoning=_reasoning_of(content),
            )
        return Decision(
            action=reply.action,
            reasoning=reply.reasoning,
            **self._measures(start, usage),
        )

    def _failed(
        self, start: float, usage, code: str, error: str, reasoning: str | None = None
    ) -> Decision:
        return Decision(
            action=None,
            reasoning=reasoning,
            error_code=code,
            error=error,
            **self._measures(start, usage),
        )

    def _measures(self, start: float, usage) -> dict:
        in_details = getattr(usage, "prompt_tokens_details", None)
        return {
            "llm_ms": int((time.monotonic() - start) * 1000),
            "prompt_tokens": getattr(usage, "prompt_tokens", 0) or 0,
            "cached_tokens": getattr(in_details, "cached_tokens", 0) or 0,
            "completion_tokens": getattr(usage, "completion_tokens", 0) or 0,
            "model": self._llm.model,
        }


def _reasoning_of(content: str) -> str | None:
    """스키마 밖이어도 JSON 으로 읽히면 reasoning 은 남긴다 (명세 3.8)."""
    try:
        reasoning = json.loads(content).get("reasoning")
    except (ValueError, AttributeError):
        return None
    return reasoning if isinstance(reasoning, str) else None
