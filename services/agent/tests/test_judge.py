"""성공 판정 보조 (GACA-161) — 판정 입력 만들기 · 판정 LLM 부르기 · 판정 모델 설정."""

import asyncio
import json

import pytest

from uxight_agent.bakeoff import SYSTEM
from uxight_agent.driver.base import Observation
from uxight_agent.judge import judge, judge_input
from uxight_agent.llm import LLMClient
from uxight_agent.watcher import run_orchestrator as orchestrator_module

TASK = {
    "task_id": 1,
    "goal": "교내 장학금 종류와 신청 방법을 찾는다",
    "success_rule": "장학제도 안내 페이지에 도달한다",
    "success_url": "https://school.example/kor/3126/subview.do",
}


def step(no: int, action: dict | None, reasoning: str | None = None) -> dict:
    """step 로그 한 줄에서 판정 입력이 읽는 칸만."""
    return {"step": no, "url": "https://school.example/", "reasoning": reasoning, "action": action}


def act(kind: str, target: int | None = None, direction: str | None = None) -> dict:
    text = "***" if kind == "type" else None
    return {"kind": kind, "target": target, "text": text, "direction": direction}


STEPS = [
    step(1, act("click", 3)),
    step(2, None),  # 행동을 얻지 못한 step 은 행동이 아니다
    step(3, act("type", 5)),
    step(4, act("scroll", direction="down")),
    step(5, act("back")),
    step(6, act("click", 12)),
    step(7, act("done"), reasoning="장학금 지급 방법 안내를 찾았다"),
]

PAGE = Observation(
    url="https://school.example/kor/3126/subview.do",
    title="장학제도",
    dom="[1] link 학사안내",
    text="장학주요안내 장학금 지급방법 " + "가" * 3000,
)


def test_judge_input_has_the_shape_of_the_judge_cases() -> None:
    # 문제집(eval/cases/judge.jsonl)의 input 과 같은 칸이다. 마지막 행동은 행동이 있는 step 의
    # 마지막 5개, done 은 그 step 의 이유를 붙인다. 본문 글은 앞 2000자만.
    assert judge_input(TASK, STEPS, PAGE) == {
        "task": "교내 장학금 종류와 신청 방법을 찾는다",
        "criterion": "장학제도 안내 페이지에 도달한다",
        "final_page": {
            "url": "https://school.example/kor/3126/subview.do",
            "title": "장학제도",
            "crumb": [],
            "text": ("장학주요안내 장학금 지급방법 " + "가" * 3000)[:2000],
        },
        "last_actions": [
            "type [5]",
            "scroll down",
            "back",
            "click [12]",
            "done — 장학금 지급 방법 안내를 찾았다",
        ],
    }


def test_judge_input_done_without_reasoning_and_no_steps() -> None:
    done_only = [step(1, act("done"))]
    assert judge_input(TASK, done_only, PAGE)["last_actions"] == ["done"]
    assert judge_input(TASK, [], PAGE)["last_actions"] == []


def test_judge_input_without_last_page_is_none() -> None:
    # 마지막 화면이 없으면(브라우저를 띄우기 전에 끝남 등) 판정할 것이 없다.
    assert judge_input(TASK, STEPS, None) is None


def test_judge_asks_with_the_bakeoff_prompt_and_records_role_judge(scripted_llm, tmp_path) -> None:
    llm, requests = scripted_llm('{"success": true, "evidence": "장학금 지급방법"}')
    payload = judge_input(TASK, STEPS, PAGE)

    answer = asyncio.run(judge(llm, payload, run_id=7, persona_id=3))

    assert (answer.success, answer.evidence) == (True, "장학금 지급방법")
    # 프롬프트 · 입력 글 · 답 모양이 bakeoff 의 판정과 같다 — 문제집으로 잰 정답률이 그대로 맞게.
    [request] = requests
    assert request["messages"] == [
        {"role": "system", "content": SYSTEM["judge"]},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False, indent=1)},
    ]
    assert request["response_format"]["json_schema"]["name"] == "Judgment"
    assert request["max_completion_tokens"] == 2000
    [usage] = [json.loads(x) for x in (tmp_path / "llm-usage.jsonl").read_text().splitlines()]
    assert (usage["role"], usage["run_id"], usage["persona_id"]) == ("judge", 7, "3")


@pytest.mark.parametrize("reply", ["성공입니다", None], ids=["bad-format", "call-failed"])
def test_judge_failure_raises(scripted_llm, reply: str | None) -> None:
    llm, _ = scripted_llm(reply)
    with pytest.raises(Exception):  # noqa: B017 — 형식 오류 · 호출 실패 모두 부른 쪽이 None 으로 둔다
        asyncio.run(judge(llm, judge_input(TASK, STEPS, PAGE), run_id=7, persona_id=3))


def test_llm_client_takes_base_url_and_key_as_arguments(monkeypatch) -> None:
    # 판정 모델은 다른 배포일 수 있다. 인자로 주면 LLM_* env 를 읽지 않는다.
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    llm = LLMClient(model="judge-model", base_url="http://judge.test/v1", api_key="judge-key")
    assert (llm.model, str(llm._client.base_url), llm._client.api_key) == (
        "judge-model",
        "http://judge.test/v1/",
        "judge-key",
    )


def test_llm_client_default_still_reads_llm_env(monkeypatch) -> None:
    monkeypatch.setenv("LLM_BASE_URL", "http://step.test/v1")
    monkeypatch.setenv("LLM_API_KEY", "step-key")
    monkeypatch.setenv("LLM_MODEL", "step-model")
    llm = LLMClient()
    assert (llm.model, str(llm._client.base_url), llm._client.api_key) == (
        "step-model",
        "http://step.test/v1/",
        "step-key",
    )


def test_no_judge_model_means_no_judge(monkeypatch) -> None:
    monkeypatch.delenv("JUDGE_MODEL", raising=False)
    assert orchestrator_module.make_judge_llm() is None
    monkeypatch.setenv("JUDGE_MODEL", "")
    assert orchestrator_module.make_judge_llm() is None


def test_judge_model_settings_and_key_fallback(monkeypatch) -> None:
    monkeypatch.setenv("JUDGE_MODEL", "judge-model")
    monkeypatch.setenv("JUDGE_BASE_URL", "http://judge.test/v1")
    monkeypatch.setenv("LLM_API_KEY", "step-key")
    monkeypatch.delenv("JUDGE_API_KEY", raising=False)
    llm = orchestrator_module.make_judge_llm()
    assert (llm.model, str(llm._client.base_url), llm._client.api_key) == (
        "judge-model",
        "http://judge.test/v1/",
        "step-key",  # JUDGE_API_KEY 가 없으면 LLM_API_KEY
    )
    monkeypatch.setenv("JUDGE_API_KEY", "judge-key")
    assert orchestrator_module.make_judge_llm()._client.api_key == "judge-key"


def test_judge_model_without_base_url_is_an_error(monkeypatch) -> None:
    # 주소가 비면 Persona 의 주소로 넘어가지 않는다 — MLAPI 는 주소 하나에 모델 하나가 묶인다.
    monkeypatch.setenv("JUDGE_MODEL", "judge-model")
    monkeypatch.setenv("JUDGE_BASE_URL", "")
    monkeypatch.setenv("LLM_BASE_URL", "http://step.test/v1")
    monkeypatch.setenv("LLM_API_KEY", "step-key")
    with pytest.raises(KeyError):
        orchestrator_module.make_judge_llm()
