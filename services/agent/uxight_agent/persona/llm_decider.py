"""LLM 판단기 (GACA-151). step 마다 LLM 을 한 번 불러 행동 5종 중 하나를 받는다.

- 답은 StepReply 스키마(response_format)로만 받는다. 모르는 칸 · 다른 행동 종류는 거부한다 (D18).
- 깨진 답은 예외 대신 action=None 인 Decision 으로 돌려준다 — 그 step 은 실행하지 않고
  '파싱 실패' 로 기록된다 (행동 로그 명세 3.8). LLM 호출 실패도 같은 방식이다.
"""

import time

from openai import (
    APIError,
    APITimeoutError,
    ContentFilterFinishReasonError,
    LengthFinishReasonError,
)
from pydantic import BaseModel, ConfigDict, ValidationError

from ..driver.base import Observation
from ..llm import LLMClient
from ..schemas import Action
from .persona_agent import Decider, Decision, StepResult
from .prompt import build_messages

STEP_ROLE = "persona_step"
# 추론 모델은 생각 토큰도 이 한도에 든다 — 너무 작으면 답이 잘려 파싱 실패가 된다 (AGENTS.md).
STEP_MAX_TOKENS = 2000


class StepReply(BaseModel):
    """LLM 이 step 마다 내는 답. 모르는 칸은 거부한다."""

    model_config = ConfigDict(extra="forbid")

    reasoning: str
    action: Action


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

        def failed(code: str, error: str, usage=None) -> Decision:
            return Decision(
                action=None,
                error_code=code,
                error=error,
                llm_ms=_ms(start),
                prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
                completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
                model=self._llm.model,
            )

        try:
            response = await self._llm.chat(
                messages,
                role=STEP_ROLE,
                max_tokens=STEP_MAX_TOKENS,
                response_format=StepReply,
                run_id=self._run_id,
                persona_id=str(persona["persona_id"]),
            )
        except ValidationError as e:
            # SDK 가 답을 StepReply 로 읽다 실패했다. JSON 자체가 깨졌는지, 스키마 밖인지 나눈다.
            if any(err["type"] == "json_invalid" for err in e.errors()):
                return failed("PARSE_FAILED", "Action JSON parsing failed")
            return failed("INVALID_ACTION", "Action is outside the action schema")
        except (LengthFinishReasonError, ContentFilterFinishReasonError) as e:
            # 한도에 걸려 잘렸거나 걸러진 답 — 읽을 JSON 이 없다. 쓴 토큰은 남긴다.
            completion = getattr(e, "completion", None)
            return failed(
                "PARSE_FAILED", "Action JSON parsing failed", getattr(completion, "usage", None)
            )
        except APITimeoutError:
            return failed("LLM_REQUEST_TIMEOUT", "LLM request timed out")
        except APIError as e:
            return failed("LLM_REQUEST_FAILED", f"LLM request failed: {type(e).__name__}")

        message = response.choices[0].message
        reply: StepReply | None = message.parsed
        if reply is None:  # 모델이 답을 거절했다 (refusal)
            return failed("PARSE_FAILED", "Action JSON parsing failed", response.usage)
        return Decision(
            action=reply.action,
            reasoning=reply.reasoning,
            llm_ms=_ms(start),
            prompt_tokens=response.usage.prompt_tokens if response.usage else 0,
            completion_tokens=response.usage.completion_tokens if response.usage else 0,
            model=self._llm.model,
        )


def _ms(start: float) -> int:
    return int((time.monotonic() - start) * 1000)
