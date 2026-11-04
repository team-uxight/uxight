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


def test_pointer_cell_is_checked_like_button(fixture_server: str) -> None:
    observation = _observe(f"{fixture_server}/pointer_cells.html")
    verdicts = {
        item["text"]: destructive_reason(Action(kind="click", element_id=i), observation)
        for i, item in observation.element_map.items()
        if item.get("pointer")
    }

    # 손가락 커서로 클릭을 받는 칸(GACA-225)은 스크립트가 클릭을 받으므로 버튼으로 본다.
    # 버튼에만 거는 '구매' 같은 낱말도 막는다.
    # 칸 안쪽 요소의 이름도 본다 — 칸 가운데를 누르면 안쪽 ✕(title '삭제')가 눌린다.
    assert verdicts == {
        "25학번 (별표31)": None,
        "26학번 (별표32)": None,
        "구매하기": "keyword '구매'",
        "바깥 칸 안쪽 글": None,
        "✕": "keyword '삭제'",
    }


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


def test_hidden_names_and_paths_are_checked(fixture_server: str) -> None:
    observation = _observe(f"{fixture_server}/destructive_bypass.html")
    verdicts = [
        (
            item["text"],
            item.get("hint"),
            destructive_reason(Action(kind="click", element_id=i), observation),
        )
        for i, item in observation.element_map.items()
    ]
    by_text = {text or hint: reason for text, hint, reason in verdicts}

    assert by_text["삭제"] is not None  # 글 없는 링크 안 img alt (+ 경로 delete)
    assert by_text["🗑"] is not None  # 보이는 글은 아이콘, aria-label '계정 삭제'
    assert by_text["나가기"] is not None  # title '회원탈퇴'
    assert by_text["글 정리"] == "path 'remove'"
    assert by_text["검색"] is None  # POST 폼이어도 검색 버튼은 막지 않는다
    assert by_text["구매입찰"] is None  # 다른 쪽으로 가는 메뉴 링크의 명사는 걸지 않는다
    # 한계(docstring): POST 폼 안 스크립트 제출 링크는 글로만 본다.
    assert by_text["확인"] is None
