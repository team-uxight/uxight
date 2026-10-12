"""SomDriver — 번호 박스 · 입력칸 가림 · 스크린샷 · 원상 복구.

LLM 없이 로컬 fixture 페이지로 본다.
"""

import asyncio
from pathlib import Path

from uxight_agent.driver.base import Observation
from uxight_agent.driver.dom_driver import DomDriver
from uxight_agent.driver.som_driver import MARK_ATTRIBUTE, SomDriver
from uxight_agent.schemas import Action

FIXTURES = Path(__file__).parent / "fixtures"
PAGE_URL = (FIXTURES / "som_page.html").as_uri()
DIALOG_URL = (FIXTURES / "som_dialog.html").as_uri()
ZOOM_URL = (FIXTURES / "som_zoom.html").as_uri()
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
