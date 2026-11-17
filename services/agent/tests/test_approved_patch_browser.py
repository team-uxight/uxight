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


def approved(improvement_id, kind, patch, page_url=PAGE_URL):
    return {
        "improvement_id": improvement_id,
        "patch_kind": kind,
        "patch": {
            **patch,
            "page_url": page_url,
        },
    }


async def open_test_page(browser):
    page = await browser.new_page()

    async def serve(route):
        await route.fulfill(
            status=200,
            content_type="text/html",
            body=HTML,
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
                assert second[0]["applied"] is True
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
