"""파괴적 행동 차단 (GACA-153). 위험한 버튼 5개 · 안전한 버튼 5개를 실제 관측으로 가른다."""

import asyncio

import pytest

from uxight_agent.driver.base import Observation
from uxight_agent.driver.dom_driver import DomDriver
from uxight_agent.guard.destructive import destructive_reason
from uxight_agent.persona.persona_agent import Decider, Decision, PersonaAgent
from uxight_agent.schemas import Action

PAGE = "destructive_buttons.html"
DANGEROUS = ["회원 탈퇴", "결제하기", "Delete account", "구매 확정", "등록"]
SAFE = ["검색", "공지사항", "다음", "Search", "메뉴 열기"]


def _observe(url: str) -> Observation:
    async def run() -> Observation:
        async with DomDriver() as driver:
            await driver.start(url)
            return await driver.observe()

    return asyncio.run(run())


def test_dangerous_and_safe_buttons_are_told_apart(fixture_server: str) -> None:
    observation = _observe(f"{fixture_server}/{PAGE}")
    verdicts = {
        item["text"]: destructive_reason(Action(kind="click", element_id=i), observation)
        for i, item in observation.element_map.items()
    }

    assert sorted(verdicts) == sorted(DANGEROUS + SAFE)
    assert [text for text in DANGEROUS if verdicts[text] is None] == []
    assert [text for text in SAFE if verdicts[text] is not None] == []
    # '등록' 은 낱말이 아니라 POST 폼 제출이라는 속성으로 걸린다.
    assert verdicts["등록"] == "submit of a POST form"


@pytest.mark.parametrize("label", ["회원 탈퇴", "삭 제", "ｐａｙ now", "탈​퇴"])
def test_spacing_and_lookalikes_do_not_hide_keyword(label: str) -> None:
    observation = Observation(
        url="https://copy.example/",
        title="t",
        dom="",
        element_map={1: {"tag": "button", "text": label}},
    )

    assert destructive_reason(Action(kind="click", element_id=1), observation) is not None


class ClickByText(Decider):
    def __init__(self, text: str) -> None:
        self.text = text

    async def decide(self, persona, task, observation, history) -> Decision:
        element_id = next(i for i, e in observation.element_map.items() if e["text"] == self.text)
        return Decision(Action(kind="click", element_id=element_id))


def test_blocked_click_leaves_page_untouched(fixture_server: str) -> None:
    url = f"{fixture_server}/{PAGE}"

    async def run():
        async with DomDriver() as driver:
            await driver.start(url)
            agent = PersonaAgent(
                {"persona_id": 1}, {}, driver, ClickByText("회원 탈퇴"), frozenset()
            )
            step = await agent.step()
            return step, await driver._page.title(), driver._page.url

    step, title, page_url = asyncio.run(run())

    assert step.result.error_code == "DESTRUCTIVE_ACTION_BLOCKED"
    assert "탈퇴" in step.result.error
    assert step.browser_ms == 0
    assert (title, page_url) == ("버튼", url)  # onclick 이 돌지 않았다
