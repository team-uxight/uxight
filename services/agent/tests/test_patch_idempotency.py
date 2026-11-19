"""GACA-170: DOM 패치 반복 적용 멱등성 테스트."""

import asyncio

import pytest
from playwright.async_api import async_playwright

from uxight_agent.patch.patcher import apply_patch


@pytest.mark.parametrize(
    ("patch_kind", "patch", "html"),
    [
        (
            "relabel",
            {"target": "#target", "new_text": "새 메뉴"},
            "<button id='target'>기존 메뉴</button>",
        ),
        (
            "move",
            {
                "target": "#target",
                "destination": "#destination",
                "position": "after",
            },
            "<div id='target'>메뉴</div><div id='destination'>목적지</div>",
        ),
        (
            "highlight",
            {"target": "#target", "style": "outline"},
            "<button id='target'>메뉴</button>",
        ),
        (
            "help_text",
            {"target": "#target", "text": "여기서 장학금을 찾으세요"},
            "<button id='target'>장학금</button>",
        ),
    ],
)
def test_patch_applied_twice_has_same_dom(patch_kind, patch, html):
    async def run():
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            try:
                page = await browser.new_page()
                await page.set_content(html)

                await apply_patch(page, patch_kind, patch)
                first_dom = await page.locator("body").inner_html()

                await apply_patch(page, patch_kind, patch)
                second_dom = await page.locator("body").inner_html()

                assert first_dom == second_dom
            finally:
                await browser.close()

    asyncio.run(run())


def test_help_text_is_not_duplicated():
    async def run():
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            try:
                page = await browser.new_page()
                await page.set_content("<button id='target'>장학금</button>")

                patch = {
                    "target": "#target",
                    "text": "장학금 안내입니다",
                }

                await apply_patch(page, "help_text", patch)
                await apply_patch(page, "help_text", patch)

                assert await page.locator("[data-uxight-help='true']").count() == 1
            finally:
                await browser.close()

    asyncio.run(run())
