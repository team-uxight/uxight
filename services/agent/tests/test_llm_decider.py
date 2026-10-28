"""LLM 판단기 (GACA-151). 가짜 HTTP 응답을 진짜 openai SDK 로 읽어 Decision 을 확인한다."""

import asyncio
import json

import pytest
from pydantic import ValidationError

from uxight_agent.driver.base import ActionResult, Driver, Observation
from uxight_agent.persona.llm_decider import LLMDecider
from uxight_agent.persona.persona_agent import PersonaAgent
from uxight_agent.schemas import Action

PERSONA = {"persona_id": 2, "name": "p", "profile": {"web_skill": "low"}}
TASK = {"goal": "학사일정을 찾는다", "success_rule": "학사일정 페이지"}
OBSERVATION = Observation(url="https://copy.example/", title="홈", dom='[3] <a href="/a"> "학사"')

NORMAL = (
    '{"reasoning": "학사 메뉴를 누른다.", '
    '"action": {"kind": "click", "element_id": 3, "value": null}}'
)
BROKEN = '{"reasoning": "학사 메뉴를 누른다.", "action": {"kind": "cli'
UNKNOWN_FIELD = (
    '{"reasoning": "r", "action": {"kind": "click", "element_id": 3, "value": null, '
    '"url": "https://evil.example"}}'
)
UNKNOWN_KIND = (
    '{"reasoning": "r", "action": {"kind": "navigate", "element_id": null, "value": "x"}}'
)


def decide(llm, run_id: int = 7):
    return asyncio.run(LLMDecider(llm, run_id=run_id).decide(PERSONA, TASK, OBSERVATION, []))


def test_normal_reply_becomes_action(scripted_llm) -> None:
    llm, requests = scripted_llm(NORMAL)

    decision = decide(llm)

    assert decision.action == Action(kind="click", element_id=3)
    assert decision.reasoning == "학사 메뉴를 누른다."
    assert decision.error_code is None
    assert (decision.prompt_tokens, decision.completion_tokens) == (11, 7)
    assert decision.model == "test-model"
    # 답은 구조화 출력 하나로만 받는다. 도구는 넘기지 않는다 (agent-safety §2.4).
    body = requests[0]
    assert body["response_format"]["type"] == "json_schema"
    assert "tools" not in body
    assert body["messages"][0]["role"] == "system"


@pytest.mark.parametrize(
    ("content", "code"),
    [
        (BROKEN, "PARSE_FAILED"),
        (UNKNOWN_FIELD, "INVALID_ACTION"),
        (UNKNOWN_KIND, "INVALID_ACTION"),
        ((BROKEN, "length"), "PARSE_FAILED"),
    ],
    ids=["broken-json", "unknown-field", "unknown-kind", "truncated"],
)
def test_bad_reply_is_not_an_action(scripted_llm, content, code: str) -> None:
    llm, _ = scripted_llm(content)

    decision = decide(llm)

    assert decision.action is None
    assert decision.error_code == code
    assert decision.reasoning is None


def test_llm_request_failure_is_recorded_not_raised(scripted_llm) -> None:
    llm, _ = scripted_llm(None)

    decision = decide(llm)

    assert decision.action is None
    assert decision.error_code == "LLM_REQUEST_FAILED"


def test_usage_is_logged_with_run_and_persona(scripted_llm, tmp_path) -> None:
    llm, _ = scripted_llm(NORMAL)

    decide(llm, run_id=9)

    row = json.loads((tmp_path / "llm-usage.jsonl").read_text(encoding="utf-8"))
    assert (row["role"], row["run_id"], row["persona_id"]) == ("persona_step", 9, "2")


def test_action_rejects_unknown_field() -> None:
    with pytest.raises(ValidationError):
        Action.model_validate({"kind": "click", "element_id": 1, "selector": "#buy"})


class RecordingDriver(Driver):
    def __init__(self) -> None:
        self.acted: list[Action] = []

    async def start(self, url: str) -> None:
        pass

    async def observe(self) -> Observation:
        return OBSERVATION

    async def act(self, action: Action) -> ActionResult:
        self.acted.append(action)
        return ActionResult(ok=True)

    async def close(self) -> None:
        pass


def test_broken_reply_is_not_executed(scripted_llm) -> None:
    llm, _ = scripted_llm(BROKEN, NORMAL)
    driver = RecordingDriver()
    agent = PersonaAgent(PERSONA, TASK, driver, LLMDecider(llm))

    first = asyncio.run(agent.step())
    second = asyncio.run(agent.step())

    assert first.result == ActionResult(
        ok=False, error="Action JSON parsing failed", error_code="PARSE_FAILED"
    )
    assert second.result.ok
    assert driver.acted == [Action(kind="click", element_id=3)]
