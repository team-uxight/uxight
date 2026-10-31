"""SomDriver — 번호 박스 · 입력칸 가림 · 스크린샷 · 원상 복구.

LLM 없이 로컬 fixture 페이지로 본다.
"""

import asyncio
import time
from pathlib import Path

from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from uxight_agent.driver import som_driver
from uxight_agent.driver.base import Observation
from uxight_agent.driver.dom_driver import ID_ATTRIBUTE, DomDriver
from uxight_agent.driver.som_driver import MARK_ATTRIBUTE, STILL_WAIT_MS, SomDriver
from uxight_agent.schemas import Action

FIXTURES = Path(__file__).parent / "fixtures"
PAGE_URL = (FIXTURES / "som_page.html").as_uri()
DIALOG_URL = (FIXTURES / "som_dialog.html").as_uri()
ZOOM_URL = (FIXTURES / "som_zoom.html").as_uri()
HIDDEN_URL = (FIXTURES / "som_hidden.html").as_uri()
FADE_URL = (FIXTURES / "som_fade.html").as_uri()
SMOOTH_URL = (FIXTURES / "som_smooth.html").as_uri()
REDIRECT_URL = (FIXTURES / "som_redirect.html").as_uri()
PROGRESS_URL = (FIXTURES / "som_progress.html").as_uri()
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
TYPED_QUERY = "졸업 요건"

# 찍는 순간의 덧그림 상태: 번호 박스 · 번호 딱지 · 불투명 막 위치 · 입력칸 위치와 값.
_CAPTURE_STATE_JS = """
(markAttr) => {
  const rectOf = el => {
    const r = el.getBoundingClientRect();
    return [r.left, r.top, r.width, r.height].map(Math.round);
  };
  const root = document.querySelector(`[${markAttr}=""]`);
  const boxes = Array.from(document.querySelectorAll(`[${markAttr}=box]`));
  // 계산된 배경색이 알파 없는 rgb() 면 불투명하다.
  const masks = Array.from(document.querySelectorAll(`[${markAttr}=mask]`))
    .filter(m => getComputedStyle(m).backgroundColor.startsWith('rgb('));
  const fields = Array.from(document.querySelectorAll('input, textarea'));
  return {
    in_top_layer: root !== null && root.matches(':popover-open'),
    box_count: boxes.length,
    labels: boxes.map(box => Number(box.textContent)),
    box_rects: boxes.map(rectOf),
    label_rects: boxes.map(box => rectOf(box.firstElementChild)),
    mask_rects: masks.map(rectOf),
    field_rects: Object.fromEntries(fields.map(el => [el.name || el.type, rectOf(el)])),
    values: Object.fromEntries(fields.map(el => [el.name || el.type, el.value])),
  };
}
"""

# 찍기 전후 비교용 페이지 상태. outerHTML 에 안 잡히는 입력값(value 속성이 아닌 값)도 함께 본다.
_PAGE_STATE_JS = """
() => ({
  html: document.documentElement.outerHTML,
  values: Array.from(document.querySelectorAll('input, textarea, select'), el => el.value),
})
"""


def _element_id(observation: Observation, name: str) -> int:
    return next(id_ for id_, item in observation.element_map.items() if item["name"] == name)


async def _observe_with_spy(url: str, type_query: bool) -> tuple[Observation, dict]:
    """observe() 를 한 번 하면서 screenshot() 직전의 페이지 상태를 잡아 둔다."""
    async with SomDriver() as driver:
        await driver.start(url)
        if type_query:
            first = await driver.observe()
            await driver.act(
                Action(kind="type", element_id=_element_id(first, "q"), value=TYPED_QUERY)
            )

        page = driver._page
        real_screenshot = page.screenshot
        captured: dict = {}

        async def spy_screenshot(**kwargs) -> bytes:
            captured.update(await page.evaluate(_CAPTURE_STATE_JS, MARK_ATTRIBUTE))
            return await real_screenshot(**kwargs)

        page.screenshot = spy_screenshot
        observation = await driver.observe()
        return observation, captured


def test_screenshot_is_png() -> None:
    observation, _ = asyncio.run(_observe_with_spy(PAGE_URL, type_query=True))

    assert isinstance(observation.screenshot, bytes)
    assert observation.screenshot.startswith(PNG_SIGNATURE)


def test_marks_match_observed_elements() -> None:
    observation, captured = asyncio.run(_observe_with_spy(PAGE_URL, type_query=True))

    # a · button · email · password · q · memo · select · submit. 숨은 버튼은 빠진다.
    assert len(observation.element_map) == 8
    assert captured["box_count"] == len(observation.element_map)
    assert sorted(captured["labels"]) == sorted(observation.element_map)


def test_input_values_masked_at_capture() -> None:
    # fixture 는 CSP(style-src 'self')로 인라인 <style> 주입을 막는다.
    _, captured = asyncio.run(_observe_with_spy(PAGE_URL, type_query=True))

    # 값이 들어 있는 채로 찍히지만, 그 순간 입력칸마다 같은 자리에 불투명 막이 덮여 있다.
    assert captured["values"]["email"] == "kim@example.com"
    assert captured["values"]["q"] == TYPED_QUERY
    for name in ("email", "password", "q", "memo"):
        assert captured["field_rects"][name] in captured["mask_rects"], name
    # 버튼 계열 input 은 값이 버튼 글자라 가리지 않는다.
    assert captured["field_rects"]["submit"] not in captured["mask_rects"]


def test_invisible_fields_not_masked() -> None:
    _, captured = asyncio.run(_observe_with_spy(HIDDEN_URL, type_query=False))

    # visibility hidden · opacity 0 칸은 값도 안 보여 가릴 것이 없다.
    # 막을 그리면 그 자리 아래의 보이는 배너 글을 덮는다.
    # 반투명 칸은 값이 비쳐 보이므로 보통 칸과 함께 가린다.
    fields = captured["field_rects"]
    assert sorted(captured["mask_rects"]) == sorted([fields["faded"], fields["plain"]])


async def _field_shot(value: str) -> bytes:
    """zoom fixture 입력칸에 value 를 넣고 SomDriver 로 찍되, 입력칸 사각형만 잘라 온다."""
    async with SomDriver() as driver:
        await driver.start(ZOOM_URL)
        first = await driver.observe()
        # 실제 행동 경로(fill)로 넣어, 찍을 때 입력칸에 포커스와 커서가 있다.
        result = await driver.act(
            Action(kind="type", element_id=_element_id(first, "secret"), value=value)
        )
        assert result.ok, result.error

        page = driver._page
        real_screenshot = page.screenshot

        async def clipped_screenshot(**kwargs) -> bytes:
            clip = await page.locator("[name=secret]").bounding_box()
            return await real_screenshot(clip=clip, **kwargs)

        page.screenshot = clipped_screenshot
        observation = await driver.observe()
        return observation.screenshot


def test_typed_value_not_in_screenshot() -> None:
    # 글자 32px · body zoom 1.5 — 블러로는 읽히던 크기다.
    shots = [asyncio.run(_field_shot(value)) for value in ("hunter2", "XXXXXXX")]

    # 값이 한 픽셀이라도 이미지에 남으면 두 장이 달라진다.
    assert shots[0] == shots[1]


def test_label_outside_above_box() -> None:
    _, captured = asyncio.run(_observe_with_spy(PAGE_URL, type_query=False))

    # 딱지는 박스 왼쪽 위 모서리 바로 위. 안쪽이면 짧은 링크의 첫 글자를 덮는다.
    for box, label in zip(captured["box_rects"], captured["label_rects"], strict=True):
        assert label[0] == box[0]
        assert label[1] + label[3] == box[1]


def test_label_inside_box_at_page_top() -> None:
    _, captured = asyncio.run(_observe_with_spy(ZOOM_URL, type_query=False))

    # 맨 위 링크는 위에 자리가 없어 박스 안쪽에, 그 아래 입력칸은 박스 바깥 위에 단다.
    link_box, field_box = captured["box_rects"]
    link_label, field_label = captured["label_rects"]
    # 링크 위쪽 여백이 딱지 높이보다 작다 = 위에 자리가 없다.
    assert link_box[1] < link_label[3]
    assert link_label[1] >= link_box[1]
    assert field_label[1] + field_label[3] == field_box[1]


def test_marks_drawn_above_modal_dialog() -> None:
    observation, captured = asyncio.run(_observe_with_spy(DIALOG_URL, type_query=False))

    # 모달도 top layer 라, 덧그림이 그 위(top layer)에 있어야 번호와 막이 보인다.
    assert captured["in_top_layer"]
    assert captured["box_count"] == len(observation.element_map)
    assert captured["field_rects"]["password"] in captured["mask_rects"]


def test_page_restored_after_capture() -> None:
    async def scenario() -> tuple[dict, dict, dict]:
        async with SomDriver() as driver:
            await driver.start(PAGE_URL)
            # 번호(data-ux-id)는 DomDriver 몫이라 남는다.
            # 덧그림 없이 번호만 붙인 상태를 "찍기 전" 으로 삼는다.
            first = await DomDriver.observe(driver)
            await driver.act(
                Action(kind="type", element_id=_element_id(first, "q"), value=TYPED_QUERY)
            )
            page = driver._page
            before = await page.evaluate(_PAGE_STATE_JS)
            await driver.observe()
            after = await page.evaluate(_PAGE_STATE_JS)
            leftover = await page.evaluate(_CAPTURE_STATE_JS, MARK_ATTRIBUTE)
            return before, after, leftover

    before, after, leftover = asyncio.run(scenario())

    assert after == before
    assert TYPED_QUERY in after["values"]
    assert leftover["box_count"] == 0
    assert leftover["mask_rects"] == []


async def _shot_after_click(url: str, text: str) -> bytes | None:
    """url 을 열어 글이 text 인 요소를 누르고, 곧바로 SomDriver 로 찍는다.

    막을 그린 뒤 찍기까지 0.15초가 걸리게 한다. 빠른 기계에서는 화면이 움직이기 전에 찍혀
    막이 빗나가는 경우를 놓친다. 느린 러너에서는 그사이 화면이 움직인다.
    """
    async with SomDriver() as driver:
        await driver.start(url)
        first = await driver.observe()
        target = next(id_ for id_, item in first.element_map.items() if item["text"] == text)
        result = await driver.act(Action(kind="click", element_id=target))
        assert result.ok, result.error

        page = driver._page
        real_screenshot = page.screenshot

        async def slow_screenshot(**kwargs) -> bytes:
            await asyncio.sleep(0.15)
            return await real_screenshot(**kwargs)

        page.screenshot = slow_screenshot
        observation = await driver.observe()
        return observation.screenshot


def test_value_masked_while_modal_fades_in() -> None:
    # 값이 든 창이 0.5초 동안 나타나며 내려온다. 그 사이 막을 그리면 막이 빠지거나 빗나간다.
    shots = [
        asyncio.run(_shot_after_click(f"{FADE_URL}?v={value}", "로그인 창 열기"))
        for value in ("hunter2", "XXXXXXX")
    ]

    assert shots[0] is not None
    # 값이 한 픽셀이라도 이미지에 남으면 두 장이 달라진다.
    assert shots[0] == shots[1]


def test_value_masked_after_smooth_scroll() -> None:
    # 부드러운 스크롤 중에 막을 그리면 막은 그린 자리에 남고 입력칸만 올라간다.
    shots = [
        asyncio.run(_shot_after_click(f"{SMOOTH_URL}?v={value}", "폼으로 이동"))
        for value in ("hunter2", "XXXXXXX")
    ]

    assert shots[0] is not None
    assert shots[0] == shots[1]


def test_decorative_animation_not_waited() -> None:
    # 7초짜리 진행 막대는 번호를 붙일 요소 · 입력칸을 품지 않아 기다리지 않는다.
    async def scenario() -> tuple[float, Observation]:
        async with SomDriver() as driver:
            await driver.start(PROGRESS_URL)
            started = time.monotonic()
            observation = await driver.observe()
            return time.monotonic() - started, observation

    elapsed, observation = asyncio.run(scenario())

    assert observation.screenshot is not None
    assert elapsed < STILL_WAIT_MS / 1000


def test_screenshot_dropped_when_page_moves_during_capture() -> None:
    async def scenario() -> Observation:
        async with SomDriver() as driver:
            await driver.start(f"{SMOOTH_URL}?v=hunter2")
            page = driver._page
            real_screenshot = page.screenshot

            async def moved_screenshot(**kwargs) -> bytes:
                # 막을 그린 뒤 찍기 전에 화면이 움직인다. 몇 번을 다시 해도 그렇다.
                await page.evaluate("() => scrollBy({ top: 100, behavior: 'instant' })")
                return await real_screenshot(**kwargs)

            page.screenshot = moved_screenshot
            return await driver.observe()

    observation = asyncio.run(scenario())

    # 막이 빗나간 그림은 내보내지 않고 글 관측만 돌려준다.
    assert observation.screenshot is None
    assert observation.element_map


def test_value_masked_when_field_moves_then_hides() -> None:
    # JS 로 움직이는 패널(getAnimations 에 안 잡힌다)이 찍는 사이 미끄러지고, 확인 전에 숨는다.
    # 확인할 때 보이는 입력칸이 없어도, 막 밖에 값이 찍힌 그림은 받아들이지 않는다.
    async def shot(value: str) -> bytes | None:
        async with SomDriver() as driver:
            await driver.start(f"{SMOOTH_URL}?v={value}")
            page = driver._page
            real_screenshot = page.screenshot
            calls = 0

            async def slide_then_hide(**kwargs) -> bytes:
                nonlocal calls
                calls += 1
                if calls > 1:
                    return await real_screenshot(**kwargs)
                form = "document.getElementById('form').style"
                await page.evaluate(f"() => {{ {form}.transform = 'translateX(400px)'; }}")
                image = await real_screenshot(**kwargs)
                await page.evaluate(f"() => {{ {form}.visibility = 'hidden'; }}")
                return image

            page.screenshot = slide_then_hide
            observation = await driver.observe()
            return observation.screenshot

    shots = [asyncio.run(shot(value)) for value in ("hunter2", "XXXXXXX")]

    assert shots[0] is not None
    assert shots[0] == shots[1]


def test_observe_survives_redirect_after_load() -> None:
    # 로드 직후 스크립트가 다른 페이지로 넘긴다. 관측 도중 문서가 바뀐다.
    async def observe_once(delay_ms: int) -> tuple[float, Observation]:
        async with SomDriver() as driver:
            await driver.start(f"{REDIRECT_URL}?ms={delay_ms}")
            started = time.monotonic()
            observation = await driver.observe()
            return time.monotonic() - started, observation

    # 넘기기 전 페이지는 링크 1개, 넘긴 뒤 페이지(som_page)는 요소 8개다.
    element_count = {"SoM redirect fixture": 1, "SoM fixture": 8}
    for delay_ms in (0, 5, 10, 15, 20, 25):
        elapsed, observation = asyncio.run(observe_once(delay_ms))

        # 예외 없이 10초 안에 끝난다. 전에는 스크린샷에서 30초 동안 멈추기도 했다.
        assert elapsed < 10, delay_ms
        assert observation.screenshot is not None, delay_ms
        # 제목과 요소 목록이 같은 문서의 것이다. 전에는 새 제목에 옛 요소 목록이 섞이기도 했다.
        assert len(observation.element_map) == element_count[observation.title], delay_ms


def test_reobserved_when_document_changes_before_marks() -> None:
    # 번호를 붙인 직후, 덧그림을 그리기 전에 문서가 바뀐다. 새 문서에는 번호가 없다.
    async def scenario() -> Observation:
        async with SomDriver() as driver:
            await driver.start(ZOOM_URL)
            real_collect = driver._collect_elements
            calls = 0

            async def collect_then_navigate(page):
                nonlocal calls
                calls += 1
                items = await real_collect(page)
                if calls == 1:
                    await page.goto(PAGE_URL)
                return items

            driver._collect_elements = collect_then_navigate
            return await driver.observe()

    observation = asyncio.run(scenario())

    # 옛 문서(요소 2개)의 목록을 새 문서(som_page, 요소 8개)의 제목 · 그림과 섞지 않는다.
    assert observation.title == "SoM fixture"
    assert len(observation.element_map) == 8
    assert observation.screenshot is not None


def test_reobserved_when_page_leaves_before_marks() -> None:
    # 번호를 붙인 뒤 주 창이 허용 밖으로 간다 (늦은 이동, GACA-224).
    # 허용 밖 페이지에 번호 요소가 있어 덧그림 확인을 통과해도 그 그림은 내보내지 않는다.
    # 되돌린 뒤 다시 찍는다.
    async def scenario() -> tuple[Observation, str]:
        async with SomDriver() as driver:
            await driver.start(PAGE_URL)
            page = driver._page
            real_observe_page = driver._observe_page
            calls = 0

            async def observe_then_leave() -> Observation:
                nonlocal calls
                calls += 1
                observation = await real_observe_page()
                if calls == 1:
                    # about:blank 는 http(s) 가 아니라 허용 밖이다.
                    await page.goto("about:blank")
                    await page.set_content(f'<a {ID_ATTRIBUTE}="1" href="#">밖</a>')
                return observation

            driver._observe_page = observe_then_leave
            return await driver.observe(), page.url

    observation, url = asyncio.run(scenario())

    assert observation.blocked == "about:blank"
    assert observation.title == "SoM fixture"
    assert len(observation.element_map) == 8
    assert observation.screenshot is not None
    assert url == PAGE_URL


def test_stuck_screenshot_cut_and_retried(monkeypatch) -> None:
    # 찍기가 멈추면(관측 중 문서가 바뀔 때 30초 멈춘 적이 있다) 상한에서 끊고 다시 찍는다.
    # 상한을 줄여 빨리 돌린다.
    monkeypatch.setattr(som_driver, "SCREENSHOT_TIMEOUT_MS", 300)

    async def scenario() -> tuple[float, Observation]:
        async with SomDriver() as driver:
            await driver.start(PAGE_URL)
            page = driver._page
            real_screenshot = page.screenshot
            calls = 0

            async def stuck_once(**kwargs) -> bytes:
                nonlocal calls
                calls += 1
                if calls > 1:
                    return await real_screenshot(**kwargs)
                # 멈춘 찍기는 받은 상한이 지나야 TimeoutError 로 끝난다.
                # 상한을 넘기지 않으면 Playwright 기본값(30초)을 다 기다린다.
                await asyncio.sleep(kwargs.get("timeout", 30_000) / 1000)
                raise PlaywrightTimeoutError("Timeout exceeded")

            page.screenshot = stuck_once
            started = time.monotonic()
            observation = await driver.observe()
            return time.monotonic() - started, observation

    elapsed, observation = asyncio.run(scenario())

    assert observation.screenshot is not None
    assert elapsed < 10
