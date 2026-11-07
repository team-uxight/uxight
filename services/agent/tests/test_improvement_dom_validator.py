"""GACA-168: 실제 DOM을 이용한 읽기 전용 패치 검증 테스트."""

import asyncio

import pytest
from playwright.async_api import async_playwright

from uxight_agent.improve.dom_validator import validate_patch_target

HTML = """
<html>
<body>
  <nav id="navigation">
    <a id="scholarship">장학금</a>
    <a class="menu-item">학사 안내</a>
    <a class="menu-item">등록 안내</a>
  </nav>
  <main id="content">
    <p id="description">장학금 신청 안내</p>
    <div id="empty"></div>
  </main>
</body>
</html>
"""


async def run_validation(kind, patch, expected_error=None):
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        try:
            page = await browser.new_page()
            await page.set_content(HTML)

            before = await page.content()

            if expected_error:
                with pytest.raises(ValueError, match=expected_error):
                    await validate_patch_target(page, kind, patch)
            else:
                await validate_patch_target(page, kind, patch)

            after = await page.content()
            assert before == after, "DOM validation must not modify the page"
        finally:
            await browser.close()


def test_valid_relabel():
    asyncio.run(
        run_validation(
            "relabel",
            {"target": "#scholarship", "new_text": "장학금 신청"},
        )
    )


def test_missing_target():
    asyncio.run(
        run_validation(
            "relabel",
            {"target": "#not-found", "new_text": "장학금 신청"},
            "Target selector must match exactly one",
        )
    )


def test_duplicate_target():
    asyncio.run(
        run_validation(
            "highlight",
            {"target": ".menu-item", "style": "outline"},
            "Target selector must match exactly one",
        )
    )


def test_empty_target():
    asyncio.run(
        run_validation(
            "help_text",
            {"target": "#empty", "text": "도움말"},
            "Target element has no readable text",
        )
    )


def test_valid_move():
    asyncio.run(
        run_validation(
            "move",
            {
                "target": "#scholarship",
                "destination": "#content",
                "position": "first",
            },
        )
    )


def test_reject_move_into_descendant():
    asyncio.run(
        run_validation(
            "move",
            {
                "target": "#navigation",
                "destination": "#scholarship",
                "position": "first",
            },
            "Cannot move an element into itself",
        )
    )


def test_reject_form_control_relabel():
    async def check():
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            try:
                page = await browser.new_page()
                await page.set_content('<input id="name" value="기존 이름">')
                with pytest.raises(ValueError, match="form controls"):
                    await validate_patch_target(
                        page,
                        "relabel",
                        {"target": "#name", "new_text": "새 이름"},
                    )
            finally:
                await browser.close()

    asyncio.run(check())
