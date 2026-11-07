"""GACA-168: LLM 개선안 생성과 실제 DOM 검증 통합 테스트."""

import asyncio
import json
from types import SimpleNamespace

from playwright.async_api import async_playwright

from uxight_agent.improve.generator import generate_improvements


class FakeLLM:
    def __init__(self, target):
        self.target = target

    async def chat(self, messages, **kwargs):
        payload = {
            "options": [
                {
                    "option_no": 1,
                    "finding_ids": [10],
                    "patch_kind": "relabel",
                    "patch": {
                        "target": self.target,
                        "new_text": "장학금 신청",
                    },
                    "rationale": "메뉴 이름이 불명확해 탐색이 지연됐다.",
                    "effect_metric": "step_count",
                }
            ]
        }
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    finish_reason="stop",
                    message=SimpleNamespace(content=json.dumps(payload, ensure_ascii=False)),
                )
            ]
        )


def findings(url):
    return [
        {
            "finding_id": 10,
            "taxonomy": "navigation_confusion",
            "severity": "medium",
            "summary": "장학금 메뉴를 찾기 어려웠다.",
            "evidence": [{"url": url, "step_from": 2, "step_to": 5}],
        }
    ]


async def run_case(target, evidence_url, expected_error=None):
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        try:
            page = await browser.new_page()
            await page.route(
                "https://school.example.com/student",
                lambda route: route.fulfill(
                    status=200,
                    content_type="text/html",
                    body='<html><body><a id="scholarship">장학금</a></body></html>',
                ),
            )
            await page.goto("https://school.example.com/student")

            before = await page.content()

            async def generate():
                return await generate_improvements(
                    llm=FakeLLM(target),
                    findings=findings(evidence_url),
                    previous_patches=[],
                    task_goal="장학금 메뉴 찾기",
                    run_id=1,
                    page=page,
                )

            result = await generate()

            if expected_error:
                assert result == []
            else:
                assert len(result) == 1
                assert result[0]["patch"]["target"] == "#scholarship"
                assert result[0]["patch"]["page_url"] == "https://school.example.com/student"

            assert await page.content() == before
        finally:
            await browser.close()


def test_valid_page_and_selector():
    asyncio.run(
        run_case(
            "#scholarship",
            "https://school.example.com/student",
        )
    )


def test_reject_missing_selector():
    asyncio.run(
        run_case(
            "#nonexistent",
            "https://school.example.com/student",
            "Target selector must match exactly one",
        )
    )


def test_accept_finding_with_multiple_evidence_pages():
    asyncio.run(
        run_case(
            "#scholarship",
            "https://school.example.com/student",
        )
    )


def test_orchestrator_saves_dom_validated_improvement(monkeypatch):
    """GACA-168: 실제 오케스트레이터가 DOM 검증 후 개선안을 저장한다."""
    from uxight_agent.watcher import run_orchestrator as module
    from uxight_agent.watcher.run_orchestrator import RunOrchestrator

    url = "https://school.example.com/student"
    evidence = findings(url)
    saved = []

    monkeypatch.setattr(
        module.finding_repository,
        "get_by_run",
        lambda run_id: evidence,
    )
    monkeypatch.setattr(
        module.improvement_repository,
        "insert_all",
        lambda run_id, rows: saved.append((run_id, rows)),
    )
    monkeypatch.setattr(
        module,
        "llm_client",
        lambda: FakeLLM("#scholarship"),
    )

    async def run():
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            page = await browser.new_page()
            await page.route(
                url,
                lambda route: route.fulfill(
                    status=200,
                    content_type="text/html",
                    body='<html><body><a id="scholarship">장학금</a></body></html>',
                ),
            )
            await page.goto(url)

            from contextlib import asynccontextmanager

            @asynccontextmanager
            async def fake_open_driver(self, run_id, persona_id, hosts):
                yield SimpleNamespace(page=page)

            async def fake_open_page(self, driver, page_url, hosts):
                assert page_url == url
                assert page.url == url

            monkeypatch.setattr(RunOrchestrator, "_open_driver", fake_open_driver)
            monkeypatch.setattr(RunOrchestrator, "_open_improvement_page", fake_open_page)

            try:
                from uxight_agent.repositories.run_repository import RunSnapshot

                fields = RunSnapshot.__dataclass_fields__
                values = {
                    name: (
                        {"goal": "장학금 메뉴 찾기"}
                        if name == "task"
                        else url
                        if name == "target_url"
                        else []
                        if name == "allowed_domains"
                        else "improve"
                        if name == "mode"
                        else None
                    )
                    for name in fields
                }
                snap = RunSnapshot(**values)

                await RunOrchestrator()._save_improvements(1, snap)

                assert len(saved) == 1
                assert saved[0][0] == 1
                assert len(saved[0][1]) == 1
                assert saved[0][1][0]["patch"]["target"] == "#scholarship"
                assert saved[0][1][0]["patch"]["page_url"] == url
            finally:
                await browser.close()

    asyncio.run(run())
