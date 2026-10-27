
"""Persona Agent 행동 생성 단위 테스트."""

import asyncio
from types import SimpleNamespace

from uxight_agent.persona.agent import PersonaAgent


class FakeLLM:
    """실제 API 비용 없이 행동 생성 과정을 검증한다."""

    def __init__(self, parsed):
        self.parsed = parsed
        self.calls = []

    async def chat(self, messages, **kwargs):
        self.calls.append({"messages": messages, **kwargs})
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(parsed=self.parsed)
                )
            ]
        )


def test_persona_agent_generates_click():
    llm = FakeLLM({
        "action": "click",
        "element": 3,
        "reasoning": "장학금 메뉴를 선택한다.",
    })
    agent = PersonaAgent(llm)

    action = asyncio.run(
        agent.decide(
            persona="웹 탐색에 익숙하지 않은 대학생",
            task="장학금 안내 페이지 찾기",
            observation="[3] 장학금 안내 링크",
            run_id=1,
            persona_id="P001",
        )
    )

    assert action.action == "click"
    assert action.element == 3
    assert llm.calls[0]["role"] == "persona_step"
    assert llm.calls[0]["response_format"] is not None
    assert llm.calls[0]["run_id"] == 1


def test_persona_agent_rejects_empty_response():
    llm = FakeLLM(None)
    agent = PersonaAgent(llm)

    try:
        asyncio.run(
            agent.decide(
                persona="초보 사용자",
                task="장학금 찾기",
                observation="[0] 학사 안내",
            )
        )
    except ValueError as exc:
        assert "PARSE_FAILED" in str(exc)
    else:
        raise AssertionError("빈 행동 응답을 거부해야 합니다.")


def test_persona_agent_retries_then_succeeds():
    """첫 응답이 비어 있어도 두 번째 응답이 정상이라면 성공한다."""

    class RetryLLM:
        def __init__(self):
            self.calls = 0

        async def chat(self, messages, **kwargs):
            self.calls += 1

            if self.calls == 1:
                parsed = None
            else:
                parsed = {
                    "action": "click",
                    "element": 2,
                    "reasoning": "장학금 메뉴를 선택한다.",
                }

            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(parsed=parsed)
                    )
                ]
            )

    llm = RetryLLM()
    agent = PersonaAgent(llm)

    action = asyncio.run(
        agent.decide(
            persona="초보 사용자",
            task="장학금 페이지 찾기",
            observation="[2] 장학금 안내",
        )
    )

    assert action.action == "click"
    assert action.element == 2
    assert llm.calls == 2


def test_persona_agent_stops_after_two_failures():
    """두 번 모두 잘못된 응답이면 추가 호출 없이 실패한다."""

    llm = FakeLLM(None)
    agent = PersonaAgent(llm)

    try:
        asyncio.run(
            agent.decide(
                persona="초보 사용자",
                task="장학금 페이지 찾기",
                observation="[2] 장학금 안내",
            )
        )
    except ValueError as exc:
        assert "PARSE_FAILED" in str(exc)
    else:
        raise AssertionError("두 번 실패하면 오류가 발생해야 합니다.")

    assert len(llm.calls) == 2


def test_persona_agent_rejects_invalid_action():
    """허용되지 않는 행동이면 INVALID_ACTION으로 처리한다."""

    llm = FakeLLM({
        "action": "delete",
        "element": 1,
    })
    agent = PersonaAgent(llm)

    try:
        asyncio.run(
            agent.decide(
                persona="초보 사용자",
                task="장학금 페이지 찾기",
                observation="[1] 장학금 안내",
            )
        )
    except ValueError as exc:
        assert "INVALID_ACTION" in str(exc)
    else:
        raise AssertionError("허용되지 않는 행동을 거부해야 합니다.")

    assert len(llm.calls) == 2
