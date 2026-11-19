"""GACA-170: 승인 패치의 실제 브라우저 적용 검증."""

import asyncio

from playwright.async_api import async_playwright

from uxight_agent.patch.approved_patches import apply_approved_patches

PAGE_URL = "https://uxight.test/scholarship"

HTML = """
<!doctype html>
<html lang="ko">
<head><meta charset="utf-8"></head>
<body>
    <nav>
        <button id="scholarship">학생지원</button>
        <button id="notice">공지사항</button>
    </nav>
</body>
</html>
"""

MENU_HTML = """
<!doctype html>
<html lang="ko">
<head><meta charset="utf-8"></head>
<body>
    <ul id="menu"><li>학사</li><li>공지</li><li>장학</li></ul>
</body>
</html>
"""


def approved(improvement_id, kind, patch, page_url=PAGE_URL):
    return {
        "improvement_id": improvement_id,
        "patch_kind": kind,
        "patch": {
            **patch,
            "page_url": page_url,
        },
    }


async def open_test_page(browser, html=HTML):
    page = await browser.new_page()

    async def serve(route):
        await route.fulfill(
            status=200,
            content_type="text/html",
            body=html,
        )

    await page.route("**/*", serve)
    await page.goto(PAGE_URL)

    return page


def test_approved_relabel_changes_real_dom():
    async def run():
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            try:
                page = await open_test_page(browser)

                patches = [
                    approved(
                        10,
                        "relabel",
                        {
                            "target": "#scholarship",
                            "new_text": "장학금 안내",
                        },
                    )
                ]

                results = await apply_approved_patches(page, patches)

                assert await page.locator("#scholarship").inner_text() == "장학금 안내"
                assert results == [
                    {
                        "improvement_id": 10,
                        "applied": True,
                        "fail_reason": None,
                    }
                ]
            finally:
                await browser.close()

    asyncio.run(run())


def test_approved_patches_apply_in_order():
    async def run():
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            try:
                page = await open_test_page(browser)

                patches = [
                    approved(
                        10,
                        "relabel",
                        {
                            "target": "#scholarship",
                            "new_text": "장학금 안내",
                        },
                    ),
                    approved(
                        11,
                        "help_text",
                        {
                            "target": "#scholarship",
                            "text": "장학금 정보를 확인하세요",
                        },
                    ),
                ]

                results = await apply_approved_patches(page, patches)

                assert [item["improvement_id"] for item in results] == [10, 11]
                assert all(item["applied"] for item in results)

                assert await page.locator("#scholarship").inner_text() == "장학금 안내"
                assert (
                    await page.locator("[data-uxight-help]").inner_text()
                    == "장학금 정보를 확인하세요"
                )
            finally:
                await browser.close()

    asyncio.run(run())


def test_repeated_application_does_not_duplicate_help_text():
    async def run():
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            try:
                page = await open_test_page(browser)

                patches = [
                    approved(
                        10,
                        "help_text",
                        {
                            "target": "#scholarship",
                            "text": "장학금 정보를 확인하세요",
                        },
                    )
                ]

                first = await apply_approved_patches(page, patches)
                first_dom = await page.locator("body").inner_html()

                second = await apply_approved_patches(page, patches)
                second_dom = await page.locator("body").inner_html()

                assert first[0]["applied"] is True
                # 같은 문서에는 다시 넣지 않으므로 두 번째는 결과가 없다.
                assert second == []
                assert first_dom == second_dom
                assert await page.locator("[data-uxight-help]").count() == 1
            finally:
                await browser.close()

    asyncio.run(run())


def test_patch_for_other_page_is_skipped():
    async def run():
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            try:
                page = await open_test_page(browser)

                patches = [
                    approved(
                        10,
                        "relabel",
                        {
                            "target": "#scholarship",
                            "new_text": "변경하면 안 됨",
                        },
                        page_url="https://uxight.test/other",
                    )
                ]

                results = await apply_approved_patches(page, patches)

                assert results == []
                assert await page.locator("#scholarship").inner_text() == "학생지원"
            finally:
                await browser.close()

    asyncio.run(run())


def test_patch_failure_is_returned_without_crashing():
    async def run():
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            try:
                page = await open_test_page(browser)

                patches = [
                    approved(
                        10,
                        "relabel",
                        {
                            "target": "#missing",
                            "new_text": "장학금 안내",
                        },
                    )
                ]

                results = await apply_approved_patches(page, patches)

                assert len(results) == 1
                assert results[0]["improvement_id"] == 10
                assert results[0]["applied"] is False
                assert results[0]["fail_reason"]
                assert await page.locator("#scholarship").inner_text() == "학생지원"
            finally:
                await browser.close()

    asyncio.run(run())


async def menu_order(page):
    return await page.locator("#menu > li").all_inner_texts()


def test_move_by_position_is_applied_once_per_document():
    """순서 선택자 옮기기는 같은 문서에 여러 번 넣어도 한 번만 옮긴다."""

    async def run():
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            try:
                page = await open_test_page(browser, MENU_HTML)

                patches = [
                    approved(
                        10,
                        "move",
                        {
                            "target": "#menu > li:nth-of-type(3)",
                            "destination": "#menu",
                            "position": "first",
                        },
                    )
                ]
                success = {"improvement_id": 10, "applied": True, "fail_reason": None}

                results = []
                for _ in range(4):
                    results.extend(await apply_approved_patches(page, patches))
                    assert await menu_order(page) == ["장학", "학사", "공지"]

                assert results == [success]

                # 페이지를 다시 열면 새 문서라 다시 들어간다.
                await page.goto(PAGE_URL)
                assert await menu_order(page) == ["학사", "공지", "장학"]

                again = await apply_approved_patches(page, patches)

                assert again == [success]
                assert await menu_order(page) == ["장학", "학사", "공지"]
            finally:
                await browser.close()

    asyncio.run(run())


def test_failed_patch_is_retried_with_first_line_reason():
    """실패한 패치는 표시를 달지 않아 다시 시도하고, 사유는 첫 줄만 남긴다."""

    async def run():
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            try:
                page = await open_test_page(browser)

                patches = [
                    approved(
                        10,
                        "relabel",
                        {
                            "target": "#missing",
                            "new_text": "장학금 안내",
                        },
                    )
                ]

                first = await apply_approved_patches(page, patches)
                second = await apply_approved_patches(page, patches)

                assert [item["applied"] for item in first + second] == [False, False]
                reason = first[0]["fail_reason"]
                assert "Expected exactly one element" in reason
                assert "\n" not in reason
                assert second[0]["fail_reason"] == reason
            finally:
                await browser.close()

    asyncio.run(run())
