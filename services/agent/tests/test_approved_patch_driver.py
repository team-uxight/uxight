"""GACA-170: DomDriver 관측 시 승인 패치 자동 적용 검증."""

import asyncio

from playwright.async_api import async_playwright

from uxight_agent.driver.dom_driver import DomDriver
from uxight_agent.guard.domain import host_key

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


async def make_page(browser):
    page = await browser.new_page()

    async def serve(route):
        await route.fulfill(
            status=200,
            content_type="text/html; charset=utf-8",
            body=HTML,
        )

    await page.route("**/*", serve)
    await page.goto(PAGE_URL)
    return page


def make_driver(page, patches):
    driver = DomDriver(
        allowed_hosts=frozenset({host_key(PAGE_URL)}),
        block_outside_subrequests=False,
    )
    # 브라우저 시작 절차와 무관하게 observe() 연결만 검증한다.
    driver._page = page
    driver.set_approved_patches(patches)
    return driver


def approved_patch(
    improvement_id=10,
    target="#scholarship",
    page_url=PAGE_URL,
):
    return {
        "improvement_id": improvement_id,
        "patch_kind": "relabel",
        "patch": {
            "target": target,
            "new_text": "장학금 안내",
            "page_url": page_url,
        },
    }


def test_observe_applies_approved_patch_automatically():
    async def run():
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            try:
                page = await make_page(browser)
                driver = make_driver(page, [approved_patch()])

                observation = await driver.observe()

                assert await page.locator("#scholarship").inner_text() == "장학금 안내"
                assert "장학금 안내" in observation.dom

                assert len(driver.patch_results) == 1
                assert driver.patch_results[0] == {
                    "improvement_id": 10,
                    "applied": True,
                    "fail_reason": None,
                }
            finally:
                await browser.close()

    asyncio.run(run())


def test_observe_collects_patch_failures():
    async def run():
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            try:
                page = await make_page(browser)
                driver = make_driver(
                    page,
                    [approved_patch(target="#missing")],
                )

                observation = await driver.observe()

                assert "학생지원" in observation.dom
                assert len(driver.patch_results) == 1
                assert driver.patch_results[0]["applied"] is False
                assert driver.patch_results[0]["fail_reason"]
            finally:
                await browser.close()

    asyncio.run(run())


def test_observe_skips_other_page_patch():
    async def run():
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            try:
                page = await make_page(browser)
                driver = make_driver(
                    page,
                    [approved_patch(page_url="https://uxight.test/other")],
                )

                observation = await driver.observe()

                assert "학생지원" in observation.dom
                assert driver.patch_results == []
            finally:
                await browser.close()

    asyncio.run(run())


def test_repeated_observe_preserves_patch_results():
    async def run():
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            try:
                page = await make_page(browser)
                driver = make_driver(page, [approved_patch()])

                await driver.observe()
                await driver.observe()

                assert await page.locator("#scholarship").inner_text() == "장학금 안내"
                # 같은 문서에는 한 번만 넣으므로 결과도 하나다.
                assert len(driver.patch_results) == 1
                assert all(result["applied"] for result in driver.patch_results)
            finally:
                await browser.close()

    asyncio.run(run())
