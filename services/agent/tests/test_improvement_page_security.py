"""GACA-168: 개선안 근거 페이지 접근 보안 테스트."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from uxight_agent.guard.domain import allowed_hosts
from uxight_agent.watcher.run_orchestrator import (
    RunOrchestrator,
    validate_improvement_page_url,
)


@pytest.fixture
def hosts():
    return allowed_hosts(
        "https://school.example.com",
        ["school.example.com"],
    )


def test_allowed_evidence_page(hosts):
    url = "https://school.example.com/student/scholarship"
    assert validate_improvement_page_url(url, hosts) == url


def test_block_external_domain(hosts):
    with pytest.raises(ValueError, match="outside allowed domains"):
        validate_improvement_page_url("https://external.example.com/student", hosts)


def test_block_different_port(hosts):
    with pytest.raises(ValueError, match="outside allowed domains"):
        validate_improvement_page_url("https://school.example.com:8443/student", hosts)


def test_block_javascript_url(hosts):
    with pytest.raises(ValueError, match="outside allowed domains"):
        validate_improvement_page_url("javascript:alert(1)", hosts)


async def _test_open_allowed_improvement_page(hosts):
    url = "https://school.example.com/student"
    driver = SimpleNamespace(
        start=AsyncMock(),
        page=SimpleNamespace(url=url),
    )

    await RunOrchestrator._open_improvement_page(driver, url, hosts)

    driver.start.assert_awaited_once_with(url)


async def _test_reject_improvement_page_before_navigation(hosts):
    driver = SimpleNamespace(
        start=AsyncMock(),
        page=SimpleNamespace(url="https://external.example.com"),
    )

    with pytest.raises(ValueError, match="outside allowed domains"):
        await RunOrchestrator._open_improvement_page(driver, "https://external.example.com", hosts)

    driver.start.assert_not_awaited()


async def _test_reject_redirected_improvement_page(hosts):
    url = "https://school.example.com/student"
    driver = SimpleNamespace(
        start=AsyncMock(),
        page=SimpleNamespace(url="https://external.example.com"),
    )

    with pytest.raises(ValueError, match="outside allowed domains"):
        await RunOrchestrator._open_improvement_page(driver, url, hosts)

    driver.start.assert_awaited_once_with(url)


def test_open_allowed_improvement_page():
    asyncio.run(
        _test_open_allowed_improvement_page(
            allowed_hosts("https://school.example.com", ["school.example.com"])
        )
    )


def test_reject_improvement_page_before_navigation():
    asyncio.run(
        _test_reject_improvement_page_before_navigation(
            allowed_hosts("https://school.example.com", ["school.example.com"])
        )
    )


def test_reject_redirected_improvement_page():
    asyncio.run(
        _test_reject_redirected_improvement_page(
            allowed_hosts("https://school.example.com", ["school.example.com"])
        )
    )


def test_select_page_with_most_findings(hosts):
    from uxight_agent.watcher.run_orchestrator import select_improvement_evidence

    findings = [
        {
            "finding_id": 1,
            "evidence": [
                {"url": "https://school.example.com/a"},
                {"url": "https://school.example.com/b"},
            ],
        },
        {
            "finding_id": 2,
            "evidence": [
                {"url": "https://school.example.com/b"},
            ],
        },
    ]

    selected = select_improvement_evidence(findings, hosts)

    assert selected is not None
    assert selected[0] == "https://school.example.com/b"
    assert [f["finding_id"] for f in selected[1]] == [1, 2]


def test_select_page_excludes_external_urls(hosts):
    from uxight_agent.watcher.run_orchestrator import select_improvement_evidence

    findings = [
        {
            "finding_id": 1,
            "evidence": [
                {"url": "https://external.example.com/a"},
            ],
        },
    ]

    assert select_improvement_evidence(findings, hosts) is None


def test_select_page_deduplicates_evidence_per_finding(hosts):
    from uxight_agent.watcher.run_orchestrator import select_improvement_evidence

    findings = [
        {
            "finding_id": 1,
            "evidence": [
                {"url": "https://school.example.com/a"},
                {"url": "https://school.example.com/a"},
            ],
        },
        {
            "finding_id": 2,
            "evidence": [
                {"url": "https://school.example.com/b"},
            ],
        },
        {
            "finding_id": 3,
            "evidence": [
                {"url": "https://school.example.com/b"},
            ],
        },
    ]

    selected = select_improvement_evidence(findings, hosts)

    assert selected is not None
    assert selected[0] == "https://school.example.com/b"
    assert len(selected[1]) == 2
