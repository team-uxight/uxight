"""모달이 열렸을 때의 관측 (GACA-157). 사람은 모달이 열리면 그 안만 보고 누른다.

LLM 없이 tests/fixtures 페이지를 Playwright 로 띄워 DomDriver 관측을 본다.
- modal_layer.html: 결함 사본의 '필수 정보가 모달 뒤'(INT-H)와 같은 마크업. 표가 40줄이다.
- som_dialog.html: 브라우저 모달 dialog(showModal).
- popup_corner.html: 화면 일부만 가리는 공지 팝업 (모달이 아님).
"""

import asyncio
from pathlib import Path

from uxight_agent.driver.base import Observation
from uxight_agent.driver.dom_driver import DomDriver
from uxight_agent.schemas import Action

FIXTURES = Path(__file__).parent / "fixtures"
MODAL_URL = (FIXTURES / "modal_layer.html").as_uri()
SCROLL_DOWN = Action(kind="scroll", value="down")


def texts(observation: Observation) -> list[str]:
    return [item["text"] for item in observation.element_map.values()]


def click(observation: Observation, text: str) -> Action:
    element_id = next(i for i, item in observation.element_map.items() if item["text"] == text)
    return Action(kind="click", element_id=element_id)


def observe_steps(url: str, *steps: str | Action) -> list[Observation]:
    """url 을 띄우고 관측한다. steps 는 글이면 그 글의 요소를 click, Action 이면 그 행동이다.

    행동마다 다시 관측해 모든 관측을 돌려준다.
    """

    async def run() -> list[Observation]:
        async with DomDriver() as driver:
            await driver.start(url)
            observations = [await driver.observe()]
            for step in steps:
                action = click(observations[-1], step) if isinstance(step, str) else step
                result = await driver.act(action)
                assert result.ok, result.error
                observations.append(await driver.observe())
            return observations

    return asyncio.run(run())


def credit_rows(observation: Observation) -> list[str]:
    return [line for line in observation.text.splitlines() if "학번 |" in line]


def test_background_dropped_while_modal_open() -> None:
    closed, opened = observe_steps(MODAL_URL, "자세히 보기")

    assert {"홈", "학사일정", "장학제도", "자세히 보기"} <= set(texts(closed))
    # 뒤 메뉴 · 버튼은 막에 가려 누를 수 없다. 모달 안 요소만 남는다.
    assert texts(opened) == ["×", "학칙 보기"]
    assert "1학번 | 149" in opened.text
    assert "문의: 학사지원팀" not in opened.text
    assert "학번별 졸업 이수학점은 아래 표를 본다." not in opened.text


def test_background_back_after_modal_closed() -> None:
    *_, closed_again = observe_steps(MODAL_URL, "자세히 보기", "×")

    assert {"홈", "학사일정", "장학제도", "자세히 보기"} <= set(texts(closed_again))
    assert "문의: 학사지원팀" in closed_again.text


def test_scroll_moves_inside_modal() -> None:
    _, opened, scrolled = observe_steps(MODAL_URL, "자세히 보기", SCROLL_DOWN)

    assert "40학번 | 110" not in opened.text
    # 창이 아니라 모달 막이 움직여 표 아래쪽이 보인다.
    assert "40학번 | 110" in scrolled.text
    assert credit_rows(scrolled)[0] != credit_rows(opened)[0]


def test_native_modal_dialog_limits_observation() -> None:
    (observation,) = observe_steps((FIXTURES / "som_dialog.html").as_uri())

    assert "뒤 버튼" not in texts(observation)
    assert texts(observation) == ["", "로그인"]  # 비밀번호 칸(글 없음)과 버튼


def test_corner_popup_is_not_modal() -> None:
    (observation,) = observe_steps((FIXTURES / "popup_corner.html").as_uri())

    assert {"홈", "학사일정", "닫기"} <= set(texts(observation))
    assert "본문 안내 글" in observation.text


def test_empty_cover_is_not_modal() -> None:
    # 화면을 다 덮어도 안에 아무것도 없는 투명 막이면 모달로 보지 않는다 — 그 안만 보면 빈 화면이다.
    (observation,) = observe_steps((FIXTURES / "cover_empty.html").as_uri())

    assert {"홈", "학사일정"} <= set(texts(observation))
    assert "본문 안내 글" in observation.text
