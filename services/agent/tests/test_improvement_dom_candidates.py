import asyncio
import json
from types import SimpleNamespace

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
                result = await generate()
                assert result == []
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


async def candidates_on(html):
    from uxight_agent.improve.dom_candidates import collect_dom_candidates

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        try:
            page = await browser.new_page()
            await page.set_content(html)
            candidates = await collect_dom_candidates(page)
            counts = [
                await page.evaluate("s => document.querySelectorAll(s).length", item["selector"])
                for item in candidates
            ]
            return candidates, counts
        finally:
            await browser.close()


# 회차 32 의 답 페이지(/kor/12490, 26학번 졸업 이수학점 표)와 같은 모양.
# id 가 있는 요소 · 링크가 없다.
TABLE_ONLY_PAGE = """
<html><body>
  <div class="wrap-contents"><div class="container">
    <h2 class="objHeading_h2">26학번 (별표32)</h2>
    <div class="con-table"><table>
      <caption>26학번 졸업이수학점기준표</caption>
      <tr><th>대학</th><td>경영학과</td><td>120</td></tr>
    </table></div>
  </div></div>
</body></html>
"""


def test_page_without_id_or_link_gets_path_selector():
    candidates, counts = asyncio.run(candidates_on(TABLE_ONLY_PAGE))

    assert candidates == [
        {
            "selector": "body > div:nth-of-type(1) > div:nth-of-type(1) > h2:nth-of-type(1)",
            "tag": "h2",
            "text": "26학번 (별표32)",
            "role": None,
        }
    ]
    assert counts == [1]


def test_path_selector_only_when_no_other_candidate():
    """id · id 가 있는 부모로 후보가 하나라도 나오면 경로 선택자를 만들지 않는다 (전과 같다)."""
    html = """
    <html><body>
      <button id="notice">공지</button>
      <ul id="menu"><li>학사</li></ul>
      <div><h2>제목</h2></div>
    </body></html>
    """

    candidates, _ = asyncio.run(candidates_on(html))

    assert [item["selector"] for item in candidates] == [
        "#notice",
        "#menu > li:nth-of-type(1)",
    ]


class CountingLLM:
    def __init__(self, options):
        self.options = options
        self.calls = 0

    async def chat(self, messages, **kwargs):
        self.calls += 1
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    finish_reason="stop",
                    message=SimpleNamespace(
                        content=json.dumps({"options": self.options}, ensure_ascii=False)
                    ),
                )
            ]
        )


async def generate_on(html, llm):
    url = "https://school.example.com/student"
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        try:
            page = await browser.new_page()
            await page.route(
                url,
                lambda route: route.fulfill(status=200, content_type="text/html", body=html),
            )
            await page.goto(url)
            return await generate_improvements(
                llm=llm,
                findings=findings(),
                previous_patches=[],
                task_goal="장학금 메뉴 찾기",
                run_id=7,
                page=page,
            )
        finally:
            await browser.close()


def test_page_without_dom_candidates_returns_no_option_without_llm(caplog):
    """후보가 하나도 없는 페이지는 LLM 을 부르지 않고 빈 목록을 돌려준다.
    오케스트레이터가 다음 근거 페이지로 넘어갈 수 있게 예외를 내지 않는다."""
    llm = CountingLLM([])
    caplog.set_level("INFO", logger="uxight_agent.improve.generator")

    result = asyncio.run(generate_on("<html><body><div>안내 글</div></body></html>", llm))

    assert result == []
    assert llm.calls == 0
    assert any(
        "run=7" in r.getMessage()
        and "https://school.example.com/student" in r.getMessage()
        and "DOM 후보 0개" in r.getMessage()
        for r in caplog.records
    )


def test_generation_logs_page_candidates_options_and_filtered(caplog):
    """고른 페이지 · DOM 후보 수 · LLM 이 낸 안의 수 · 걸러진 수를 info 한 줄로 남긴다."""
    valid = {
        "option_no": 1,
        "finding_ids": [1],
        "patch_kind": "relabel",
        "patch": {"target": "#scholarship", "new_text": "장학금 신청 안내"},
        "rationale": "장학금 메뉴의 이름이 불명확하다.",
        "effect_metric": "step_count",
    }
    unknown_selector = {**valid, "option_no": 2, "patch": {**valid["patch"], "target": ".other"}}
    llm = CountingLLM([valid, unknown_selector])
    caplog.set_level("INFO", logger="uxight_agent.improve.generator")

    html = '<html><body><a id="scholarship">장학금</a><div class="other">기타</div></body></html>'
    result = asyncio.run(generate_on(html, llm))

    assert len(result) == 1
    lines = [
        r.getMessage()
        for r in caplog.records
        if r.levelname == "INFO" and "https://school.example.com/student" in r.getMessage()
    ]
    assert lines == [
        "run=7 개선안 페이지 https://school.example.com/student: "
        "DOM 후보 1개, LLM 이 낸 안 2개, 걸러진 안 1개"
    ]
