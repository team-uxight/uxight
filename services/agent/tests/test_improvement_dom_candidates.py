import asyncio
import json
from types import SimpleNamespace

import pytest
from playwright.async_api import async_playwright

from uxight_agent.improve.generator import generate_improvements


class FakeLLM:
    def __init__(self, target):
        self.target = target
        self.messages = None

    async def chat(self, messages, **kwargs):
        self.messages = messages
        content = json.dumps(
            {
                "options": [
                    {
                        "option_no": 1,
                        "finding_ids": [1],
                        "page_url": "https://school.example.com/student",
                        "patch_kind": "relabel",
                        "patch": {
                            "target": self.target,
                            "new_text": "장학금 신청 안내",
                        },
                        "rationale": "장학금 메뉴의 이름이 불명확하다.",
                        "effect_metric": "step_count",
                    }
                ]
            }
        )
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    finish_reason="stop",
                    message=SimpleNamespace(content=content),
                )
            ]
        )


def findings():
    return [
        {
            "finding_id": 1,
            "taxonomy": "navigation",
            "severity": "medium",
            "summary": "장학금 메뉴를 찾기 어렵다.",
            "evidence": [{"url": "https://school.example.com/student"}],
        }
    ]


async def run_case(target, should_fail):
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        try:
            page = await browser.new_page()
            await page.route(
                "https://school.example.com/student",
                lambda route: route.fulfill(
                    status=200,
                    content_type="text/html",
                    body="""
                    <html><body>
                      <a id="scholarship">장학금</a>
                      <div class="other">기타 안내</div>
                    </body></html>
                    """,
                ),
            )
            await page.goto("https://school.example.com/student")

            llm = FakeLLM(target)

            async def generate():
                return await generate_improvements(
                    llm=llm,
                    findings=findings(),
                    previous_patches=[],
                    task_goal="장학금 메뉴 찾기",
                    run_id=1,
                    page=page,
                )

            if should_fail:
                with pytest.raises(ValueError, match="unknown DOM selector"):
                    await generate()
            else:
                result = await generate()
                assert len(result) == 1

            payload = json.loads(llm.messages[1]["content"])
            selectors = {item["selector"] for item in payload["dom_candidates"]}

            assert "#scholarship" in selectors
            assert ".other" not in selectors

        finally:
            await browser.close()


def test_dom_candidates_sent_to_llm():
    asyncio.run(run_case("#scholarship", should_fail=False))


def test_existing_but_unlisted_selector_rejected():
    asyncio.run(run_case(".other", should_fail=True))
