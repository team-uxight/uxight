"""GACA-167: DOM 패치 4종 적용 및 설명 생성 테스트."""

import asyncio

import pytest
from playwright.async_api import async_playwright
from pydantic import TypeAdapter, ValidationError

from uxight_agent.patch.patcher import apply_patch
from uxight_agent.patch.schema import Patch

HTML = """
<!doctype html>
<html lang="ko">
<body>
  <nav id="nav">
    <a id="scholarship">학생지원</a>
    <a id="notice">공지사항</a>
  </nav>
  <main id="main">학사 안내</main>
</body>
</html>
"""


@pytest.mark.parametrize(
    ("kind", "patch", "expected_description"),
    [
        (
            "relabel",
            {"target": "#scholarship", "new_text": "장학금 신청·안내"},
            "라벨 '학생지원' → '장학금 신청·안내'",
        ),
        (
            "move",
            {"target": "#scholarship", "destination": "#notice", "position": "after"},
            "'학생지원' 요소를 '공지사항' 기준 after 위치로 이동",
        ),
        (
            "highlight",
            {"target": "#scholarship", "style": "outline"},
            "'학생지원' 요소 강조 (outline)",
        ),
        (
            "help_text",
            {"target": "#scholarship", "text": "장학금 정보를 확인하세요"},
            "'학생지원' 아래 도움말 추가: '장학금 정보를 확인하세요'",
        ),
    ],
)
def test_patch_applies_and_describes_visible_text(kind, patch, expected_description):
    async def run():
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            try:
                page = await browser.new_page()
                await page.set_content(HTML)
                result = await apply_patch(page, kind, patch)

                assert result["description"] == expected_description
                assert "#scholarship" not in result["description"]

                if kind == "relabel":
                    assert await page.locator("#scholarship").inner_text() == "장학금 신청·안내"
                elif kind == "move":
                    assert await page.locator("#nav").evaluate(
                        "(el) => Array.from(el.children).map(child => child.id)"
                    ) == ["notice", "scholarship"]
                elif kind == "highlight":
                    assert (
                        await page.locator("#scholarship").evaluate("(el) => el.style.outlineStyle")
                        == "solid"
                    )
                elif kind == "help_text":
                    assert await page.locator("[data-uxight-help]").inner_text() == (
                        "장학금 정보를 확인하세요"
                    )
            finally:
                await browser.close()

    asyncio.run(run())


def test_patch_rejects_unknown_fields():
    adapter = TypeAdapter(Patch)

    with pytest.raises(ValidationError):
        adapter.validate_python(
            {
                "kind": "relabel",
                "target": "#scholarship",
                "new_text": "장학금",
                "script": "alert(1)",
            }
        )


@pytest.mark.parametrize(
    ("patch", "expected_error"),
    [
        (
            {"target": "#missing", "new_text": "변경"},
            "found 0",
        ),
        (
            {"target": "nav a", "new_text": "변경"},
            "found 2",
        ),
    ],
)
def test_patch_rejects_missing_or_multiple_targets(patch, expected_error):
    async def run():
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            try:
                page = await browser.new_page()
                await page.set_content(HTML)
                before = await page.locator("#nav").inner_html()

                with pytest.raises(Exception, match=expected_error):
                    await apply_patch(page, "relabel", patch)

                assert await page.locator("#nav").inner_html() == before
            finally:
                await browser.close()

    asyncio.run(run())


@pytest.mark.parametrize(
    ("target", "destination"),
    [
        ("#nav", "#nav"),
        ("#nav", "#scholarship"),
    ],
)
def test_move_rejects_self_or_descendant(target, destination):
    async def run():
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            try:
                page = await browser.new_page()
                await page.set_content(HTML)
                before = await page.locator("body").inner_html()

                with pytest.raises(Exception, match="Cannot move an element"):
                    await apply_patch(
                        page,
                        "move",
                        {
                            "target": target,
                            "destination": destination,
                            "position": "last",
                        },
                    )

                assert await page.locator("body").inner_html() == before
            finally:
                await browser.close()

    asyncio.run(run())


def test_patch_rejects_kind_inside_payload():
    async def run():
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            try:
                page = await browser.new_page()
                await page.set_content(HTML)
                before = await page.locator("body").inner_html()

                with pytest.raises(ValueError, match="patch must not contain kind"):
                    await apply_patch(
                        page,
                        "relabel",
                        {
                            "kind": "highlight",
                            "target": "#scholarship",
                            "new_text": "장학금 안내",
                        },
                    )

                assert await page.locator("body").inner_html() == before
            finally:
                await browser.close()

    asyncio.run(run())


@pytest.mark.parametrize("position", ["first", "last"])
def test_move_description_uses_destination_text_before_moving(position):
    async def run():
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            try:
                page = await browser.new_page()
                await page.set_content(HTML)

                result = await apply_patch(
                    page,
                    "move",
                    {
                        "target": "#scholarship",
                        "destination": "#main",
                        "position": position,
                    },
                )

                assert result["description"] == (
                    f"'학생지원' 요소를 '학사 안내' 기준 {position} 위치로 이동"
                )

                assert await page.locator("#main").locator("#scholarship").count() == 1
            finally:
                await browser.close()

    asyncio.run(run())


def test_highlight_description_truncates_long_text():
    """긴 메뉴 텍스트도 설명은 한 줄, 최대 30자만 사용한다."""

    async def run():
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            try:
                page = await browser.new_page()

                long_text = ("장학금 신청 안내\n    ") * 1000
                await page.set_content('<div id="long-menu"></div>')
                await page.locator("#long-menu").evaluate(
                    "(el, text) => { el.textContent = text; }",
                    long_text,
                )

                original_text = await page.locator("#long-menu").text_content()

                result = await apply_patch(
                    page,
                    "highlight",
                    {
                        "target": "#long-menu",
                        "style": "outline",
                    },
                )

                description = result["description"]
                summary = description.removeprefix("'").split("' 요소 강조")[0]

                assert len(original_text) > 12000
                assert len(summary) == 30
                assert "\n" not in description
                assert "  " not in description
                assert description.endswith("요소 강조 (outline)")

                assert await page.locator("#long-menu").text_content() == original_text
                assert (
                    await page.locator("#long-menu").evaluate("(el) => el.style.outlineStyle")
                    == "solid"
                )
            finally:
                await browser.close()

    asyncio.run(run())
