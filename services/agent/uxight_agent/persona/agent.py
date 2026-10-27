
"""Persona와 웹페이지 관측 정보를 바탕으로 다음 행동 하나를 생성한다."""

from typing import Any

from pydantic import ValidationError

from uxight_agent.persona.prompts import build_messages
from uxight_agent.schemas import Action


class PersonaActionError(ValueError):
    """Persona Agent의 행동 생성 오류."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


class PersonaAgent:
    """LLM을 이용해 Persona의 다음 행동을 결정한다."""

    def __init__(self, llm: Any) -> None:
        self.llm = llm

    async def decide(
        self,
        *,
        persona: str,
        task: str,
        observation: str,
        run_id: int | None = None,
        persona_id: str | None = None,
    ) -> Action:
        messages = build_messages(
            persona=persona,
            task=task,
            observation=observation,
        )

        last_error: PersonaActionError | None = None

        for attempt in range(2):
            if attempt > 0:
                messages = [
                    *messages,
                    {
                        "role": "user",
                        "content": (
                            "직전 응답이 올바른 Action 형식이 아닙니다. "
                            "허용된 행동과 필드 형식에 맞춰 "
                            "다음 행동 하나만 다시 반환하세요."
                        ),
                    },
                ]

            try:
                response = await self.llm.chat(
                    messages,
                    role="persona_step",
                    response_format=Action,
                    max_tokens=1000,
                    run_id=run_id,
                    persona_id=persona_id,
                )
            except ValidationError:
                last_error = PersonaActionError(
                    "INVALID_ACTION", "행동 데이터 형식이 올바르지 않습니다."
                )
                continue

            if not response.choices:
                last_error = PersonaActionError(
                    "PARSE_FAILED", "LLM 응답에 선택지가 없습니다."
                )
                continue

            parsed = response.choices[0].message.parsed

            if parsed is None:
                last_error = PersonaActionError(
                    "PARSE_FAILED", "LLM 행동 응답을 해석할 수 없습니다."
                )
                continue

            try:
                return Action.model_validate(parsed)
            except ValidationError:
                last_error = PersonaActionError(
                    "INVALID_ACTION", "허용되지 않는 행동 또는 필드가 포함됐습니다."
                )

        raise last_error or PersonaActionError(
            "PARSE_FAILED", "행동 생성에 실패했습니다."
        )
