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
    from uxight_agent.watcher.run_orchestrator import improvement_evidence_pages

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

    pages = improvement_evidence_pages(findings, hosts)

    assert [url for url, _ in pages] == [
        "https://school.example.com/b",
        "https://school.example.com/a",
    ]
    assert [f["finding_id"] for f in pages[0][1]] == [1, 2]


def test_select_page_excludes_external_urls(hosts):
    from uxight_agent.watcher.run_orchestrator import improvement_evidence_pages

    findings = [
        {
            "finding_id": 1,
            "evidence": [
                {"url": "https://external.example.com/a"},
            ],
        },
    ]

    assert improvement_evidence_pages(findings, hosts) == []


def test_select_page_deduplicates_evidence_per_finding(hosts):
    from uxight_agent.watcher.run_orchestrator import improvement_evidence_pages

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

    pages = improvement_evidence_pages(findings, hosts)

    assert [url for url, _ in pages] == [
        "https://school.example.com/b",
        "https://school.example.com/a",
    ]
    assert len(pages[0][1]) == 2


def test_pages_with_same_count_keep_evidence_order(hosts):
    """근거 수가 같으면 먼저 나온 페이지가 앞이다 (회차 32: /kor/3120 다음 /kor/12490)."""
    from uxight_agent.watcher.run_orchestrator import improvement_evidence_pages

    findings = [
        {"finding_id": 18, "evidence": [{"url": "https://school.example.com/kor/3120"}]},
        {"finding_id": 19, "evidence": [{"url": "https://school.example.com/kor/12490"}]},
    ]

    pages = improvement_evidence_pages(findings, hosts)

    assert [(url, [f["finding_id"] for f in items]) for url, items in pages] == [
        ("https://school.example.com/kor/3120", [18]),
        ("https://school.example.com/kor/12490", [19]),
    ]
