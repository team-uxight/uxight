"""POST /success-rules 계약 (내부 API 0, GACA-216). LLM 은 가짜 응답으로 바꾼다.

성공 200 + success_rule, LLM 실패 · 쓸 수 없는 답 502, 필수 칸 누락 422.
"""

import httpx
import pytest
from fastapi.testclient import TestClient
from openai import APITimeoutError

from uxight_agent.main import app
from uxight_agent.routers.success_rules import get_llm

BODY = {
    "target_url": "https://www.gachon.ac.kr",
    "goal": "학사일정을 확인한다",
    "success_url": "https://www.gachon.ac.kr/kor/1075/subview.do",
}


@pytest.fixture
def call(scripted_llm):
    """정해 둔 LLM 답으로 POST /success-rules 를 부른다. (응답, LLM 이 받은 요청들)."""

    def make(*replies, body=BODY):
        llm, requests = scripted_llm(*replies)
        app.dependency_overrides[get_llm] = lambda: llm
        try:
            return TestClient(app).post("/success-rules", json=body), requests
        finally:
            app.dependency_overrides.clear()

    return make


def test_returns_success_rule(call) -> None:
    res, _ = call("학사일정 페이지에 도달한다.")

    assert res.status_code == 200
    assert res.json() == {"success_rule": "학사일정 페이지에 도달한다."}


def test_prompt_carries_three_inputs_without_response_format(call) -> None:
    _, requests = call("학사일정 페이지에 도달한다.")

    sent = requests[0]
    user = sent["messages"][-1]["content"]
    assert BODY["target_url"] in user
    assert BODY["goal"] in user
    assert BODY["success_url"] in user
    assert "response_format" not in sent  # 일반 글로 받는다 — 제공자를 바꿔도 통하게
    assert sent["max_completion_tokens"] == 1000


def test_keeps_first_line_without_quotes(call) -> None:
    res, _ = call('\n"학사일정 페이지에 도달한다."\n\n이 기준은 URL 로 판단한다.')

    assert res.json() == {"success_rule": "학사일정 페이지에 도달한다."}


@pytest.mark.parametrize(
    "reply",
    [
        None,  # LLM 이 500
        "",  # 빈 답
        "  \n ",  # 공백뿐
        ('"', "stop"),  # 따옴표뿐
        ("학사일정 페이지에", "length"),  # 한도에 걸려 잘림
        ("학사일정 페이지에 도달한다.", "content_filter"),
    ],
)
def test_unusable_reply_is_502(call, reply) -> None:
    res, _ = call(reply)

    assert res.status_code == 502
    assert res.json() == {"detail": "success rule generation failed"}


def test_llm_timeout_is_502() -> None:
    class TimingOutLLM:
        model = "test-model"

        async def chat(self, *args, **kwargs):
            raise APITimeoutError(request=httpx.Request("POST", "http://llm.test/v1"))

    app.dependency_overrides[get_llm] = TimingOutLLM
    try:
        res = TestClient(app).post("/success-rules", json=BODY)
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 502


def test_missing_field_is_422(call) -> None:
    res, requests = call(body={"target_url": BODY["target_url"], "goal": BODY["goal"]})

    assert res.status_code == 422
    assert requests == []  # LLM 을 부르지 않는다
