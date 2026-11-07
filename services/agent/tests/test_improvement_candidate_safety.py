"""GACA-169: 위험한 개선안 DOM 후보 제외 검증."""

import asyncio

from playwright.async_api import async_playwright

from uxight_agent.improve.dom_candidates import collect_dom_candidates

HTML = """
<html><body>
  <a id="scholarship" href="/scholarship">장학금 안내</a>
  <button id="withdraw">회원탈퇴<span id="withdraw-child">하기</span></button>
  <a id="outside" href="https://outside.example.com/page">외부 안내</a>
  <a id="delete" href="/member/delete.do">계정 관리</a>
  <button id="search">검색</button>
</body></html>
"""


async def run_case():
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        try:
            page = await browser.new_page()
            await page.route(
                "https://school.example.com/",
                lambda route: route.fulfill(
                    status=200,
                    content_type="text/html",
                    body=HTML,
                ),
            )
            await page.goto("https://school.example.com/")
        except Exception:
            await browser.close()
            raise

        try:
            await page.set_content(HTML)
            candidates = await collect_dom_candidates(page)
            selectors = {item["selector"] for item in candidates}

            assert "#scholarship" in selectors
            assert "#search" in selectors

            assert "#withdraw" not in selectors
            assert "#withdraw-child" not in selectors
            assert "#outside" not in selectors
            assert "#delete" not in selectors
        finally:
            await browser.close()


def test_unsafe_dom_candidates_are_excluded():
    asyncio.run(run_case())


def test_allowed_secondary_domain_and_english_destructive_link():
    """추가 허용 호스트는 유지하고 영어 위험 요소는 제외한다."""

    async def check():
        from uxight_agent.guard.domain import allowed_hosts

        html = """
        <html><body>
          <a id="allowed" href="https://admission.example.com/info">입학 안내</a>
          <a id="blocked" href="https://outside.example.com/info">외부 안내</a>
          <a id="delete" href="/member/delete">Account settings</a>
          <button id="withdraw">Withdraw account</button>
          <button id="remove">Remove account</button>
        </body></html>
        """

        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            try:
                page = await browser.new_page()
                await page.route(
                    "https://school.example.com/",
                    lambda route: route.fulfill(
                        status=200,
                        content_type="text/html",
                        body=html,
                    ),
                )
                await page.goto("https://school.example.com/")

                hosts = allowed_hosts(
                    "https://school.example.com/",
                    ["admission.example.com"],
                )
                candidates = await collect_dom_candidates(page, hosts=hosts)
                selectors = {item["selector"] for item in candidates}

                assert "#allowed" in selectors
                assert "#blocked" not in selectors
                assert "#delete" not in selectors
                assert "#withdraw" not in selectors
                assert "#remove" not in selectors
            finally:
                await browser.close()

    asyncio.run(check())
