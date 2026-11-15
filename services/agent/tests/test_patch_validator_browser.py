"""GACA-169: 실제 Chromium에서 DOM 패치 시험 적용 검증."""

import asyncio

from playwright.async_api import async_playwright

from uxight_agent.improve.patch_validator import validate_patch_application

HTML = """
<html>
<body>
    <a id="scholarship" href="/scholarship">장학금</a>
    <a id="nested" href="/nested"><span>학사 안내</span></a>
    <div id="destination">이동 위치</div>
    <button id="help">신청 방법</button>
</body>
</html>
"""


async def run_case(kind, patch, expected_success=True):
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        try:
            page = await browser.new_page()
            await page.set_content(HTML)

            success, reason = await validate_patch_application(page, kind, patch)

            assert success is expected_success, reason
            if not expected_success:
                assert reason is not None
            return page
        finally:
            await browser.close()


def test_relabel_browser():
    asyncio.run(
        run_case(
            "relabel",
            {"target": "#scholarship", "new_text": "장학금 신청"},
        )
    )


def test_move_browser():
    asyncio.run(
        run_case(
            "move",
            {
                "target": "#scholarship",
                "destination": "#destination",
                "position": "after",
            },
        )
    )


def test_highlight_browser():
    asyncio.run(
        run_case(
            "highlight",
            {"target": "#scholarship", "style": "outline"},
        )
    )


def test_help_text_browser():
    asyncio.run(
        run_case(
            "help_text",
            {"target": "#help", "text": "학생지원팀에 문의하세요"},
        )
    )


def test_nested_span_relabel_rejected():
    asyncio.run(
        run_case(
            "relabel",
            {"target": "#nested", "new_text": "학사 안내 보기"},
            expected_success=False,
        )
    )
