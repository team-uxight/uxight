"""가려진 요소 (GACA-232). 메뉴를 열면 그 뒤 요소는 사람도 Playwright 도 못 누른다.

LLM 없이 tests/fixtures/menu_cover.html 을 Playwright 로 띄워 DomDriver 관측을 본다.
"""

import asyncio
from pathlib import Path

from uxight_agent.driver.base import ActionResult, Observation
from uxight_agent.driver.dom_driver import DomDriver
from uxight_agent.schemas import Action

FIXTURES = Path(__file__).parent / "fixtures"
URL = (FIXTURES / "menu_cover.html").as_uri()
MENU = "대학생활"
FULL_MENU = "전체메뉴"


def texts(observation: Observation) -> list[str]:
    return [item["text"] for item in observation.element_map.values()]


def click(observation: Observation, text: str) -> Action:
    element_id = next(i for i, item in observation.element_map.items() if item["text"] == text)
    return Action(kind="click", element_id=element_id)


def observe_after(*clicks: str) -> Observation:
    async def run() -> Observation:
        async with DomDriver() as driver:
            await driver.start(URL)
            observation = await driver.observe()
            for text in clicks:
                result = await driver.act(click(observation, text))
                assert result.ok, result.error
                observation = await driver.observe()
            return observation

    return asyncio.run(run())


def test_elements_behind_open_menu_are_left_out() -> None:
    closed = observe_after()
    opened = observe_after(MENU)

    assert {"가려지는 버튼", "가려지는 링크"} <= set(texts(closed))
    assert "장학공지" not in texts(closed)
    assert "장학공지" in texts(opened)
    assert not {"가려지는 버튼", "가려지는 링크"} & set(texts(opened))


def test_elements_come_back_when_menu_closes() -> None:
    closed_again = observe_after(MENU, MENU)

    assert {"가려지는 버튼", "가려지는 링크"} <= set(texts(closed_again))


def test_every_observed_element_can_be_clicked_with_menu_open() -> None:
    # 관측에 남은 요소는 시간 초과 없이 눌러야 한다.
    async def run() -> list[str]:
        async with DomDriver() as driver:
            await driver.start(URL)
            first = await driver.observe()
            await driver.act(click(first, MENU))
            await driver.observe()
            failed = []
            # 입력칸은 click 이 아니라 fill 로 쓰므로 위에 뜬 자기 라벨이 있어도 된다.
            for handle in await driver._page.query_selector_all("[data-ux-id]:not(input)"):
                try:
                    await handle.click(trial=True, timeout=1000)
                except Exception:  # noqa: BLE001 — 어떤 실패든 누를 수 없다는 뜻이다
                    failed.append(await handle.inner_text())
            return failed

    assert asyncio.run(run()) == []


def test_elements_below_the_screen_stay() -> None:
    # 화면 아래 요소는 가렸는지 알 수 없다. 스크롤하면 보이므로 남긴다.
    assert "아래쪽 링크" in texts(observe_after(MENU))


def test_elements_below_the_screen_leave_when_menu_covers_the_whole_screen() -> None:
    # 화면보다 큰 메뉴가 열리면 어디로 스크롤해도 그 뒤다. 사람도 메뉴를 닫아야 누른다.
    opened = observe_after(FULL_MENU)

    assert "전체 메뉴 링크" in texts(opened)
    assert not {"아래쪽 링크", "바닥 링크"} & set(texts(opened))
    assert {"아래쪽 링크", "바닥 링크"} <= set(texts(observe_after(FULL_MENU, FULL_MENU)))


def test_long_text_over_background_does_not_hide_links_below() -> None:
    # 본문은 스크롤로 비켜난다. 뒤에 고정 배경이 깔려 있어도 가린 것이 아니다.
    async def run() -> Observation:
        async with DomDriver() as driver:
            await driver.start((FIXTURES / "below_background.html").as_uri())
            return await driver.observe()

    assert "아래쪽 링크" in texts(asyncio.run(run()))


def test_wrapped_link_stays() -> None:
    # 줄바꿈된 링크는 전체 상자 가운데가 글자 사이 빈 곳일 수 있다. Playwright 처럼 첫 상자를 본다.
    assert any(text.startswith("여러 줄로") for text in texts(observe_after()))


def test_input_under_its_own_label_stays() -> None:
    # 입력칸 위에 뜬 자기 라벨은 눌러도 입력칸으로 간다. 가린 것이 아니다.
    observation = observe_after()

    assert any(item["tag"] == "input" for item in observation.element_map.values())


def test_covered_link_text_does_not_move_to_body() -> None:
    # 번호 없는 글로 본문에 새로 들어오면 모델이 누를 수 없는 글을 읽는다.
    opened = observe_after(MENU)

    assert "가려지는 링크" not in opened.text
    assert "가려지는 버튼" not in opened.text
    assert "본문 글" in opened.text


def test_empty_veil_does_not_hide_elements() -> None:
    # 아무것도 안 보이는 막 뒤를 빼면 관측이 빈다. 사람 눈에는 뒤가 보인다.
    async def run() -> Observation:
        async with DomDriver() as driver:
            await driver.start((FIXTURES / "cover_empty.html").as_uri())
            return await driver.observe()

    assert {"홈", "학사일정"} <= set(texts(asyncio.run(run())))


def test_file_link_in_new_window_is_not_a_failure(fixture_server) -> None:
    # 새 창으로 여는 파일 링크를 주 창에서 열면 Playwright 는 내려받기 오류를 낸다.
    # 사람에게는 파일이 받아지는 정상 동작이다.
    async def run() -> tuple[ActionResult, Observation]:
        async with DomDriver() as driver:
            url = f"{fixture_server}/download_link.html"
            await driver.start(url)
            first = await driver.observe()
            result = await driver.act(click(first, "[신청서및안내]"))
            return result, await driver.observe()

    result, after = asyncio.run(run())

    assert result.ok, result.error
    assert result.downloaded
    assert result.url_after.endswith("/download_link.html")
    assert "본문 안내 글" in after.text


def observe_page(fixture: str, *actions: Action) -> Observation:
    async def run() -> Observation:
        async with DomDriver() as driver:
            await driver.start((FIXTURES / fixture).as_uri())
            for action in actions:
                await driver.act(action)
            return await driver.observe()

    return asyncio.run(run())


def test_link_under_fixed_header_stays_after_scroll() -> None:
    # 고정 머리글 밑은 스크롤로 비켜난다. Playwright 도 스크롤을 바꿔 가며 다시 누른다.
    scrolled = observe_page("cover_fixed_header.html", Action(kind="scroll", value="down"))

    assert {"머리 메뉴", "첫째 링크", "둘째 링크"} <= set(texts(scrolled))


def test_link_pushed_out_of_scroll_box_stays() -> None:
    # 상자 밖으로 밀린 요소는 화면 밖처럼 남긴다. 빼면 상자를 움직일 길이 없다.
    assert "목록 20번 링크" in texts(observe_page("cover_scroll_box.html"))


def test_input_under_text_stays_when_text_is_not_its_label() -> None:
    # 입력칸은 fill 로 쓴다. 칸 크기 안의 글은 가린 것이 아니다.
    for fixture in ("cover_label_nofor.html", "cover_input_span.html"):
        items = observe_page(fixture).element_map.values()
        assert any(item["tag"] == "input" for item in items), fixture


def test_dead_link_loses_number_but_keeps_text() -> None:
    # pointer-events:none 링크는 눌리지 않는다. 사람 눈에는 보이므로 글은 남긴다.
    observation = observe_page("cover_dead_link.html")

    assert "신청 마감" not in texts(observation)
    assert "신청 마감" in observation.text


def test_veil_beside_shown_content_does_not_hide_elements() -> None:
    # 막과 같은 부모에 보이는 글이 있어도 막 자체는 아무것도 안 그린다.
    assert texts(observe_page("cover_veil_toast.html"))
    assert len(texts(observe_page("cover_veil_header.html"))) >= 4


def test_link_under_image_is_left_out() -> None:
    names = texts(observe_page("cover_image.html"))

    assert "덮인 링크" not in names
    assert "보이는 링크" in names
