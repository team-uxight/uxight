"""도메인 이탈 차단 (GACA-152). 사본(로컬 http 서버) 밖 링크는 누르지 않고 차단을 남긴다."""

import asyncio
import json
from pathlib import Path

import pytest
from sqlalchemy import text

from uxight_agent.db import create_db_engine
from uxight_agent.driver.base import Observation
from uxight_agent.driver.dom_driver import DomDriver
from uxight_agent.guard.domain import allowed_hosts, blocked_destination
from uxight_agent.persona.persona_agent import Decider, Decision, PersonaAgent
from uxight_agent.repositories import audit_log_repository as audit_module
from uxight_agent.repositories.audit_log_repository import AuditLogRepository
from uxight_agent.schemas import Action

PAGE = "domain_links.html"


def test_allowed_hosts_are_snapshot_plus_target_host() -> None:
    hosts = allowed_hosts("https://Copy.Example:8443/kor/index.do", [" CDN.example ", ""])

    assert hosts == frozenset({"copy.example", "cdn.example"})


def test_observed_links_resolved_by_browser(fixture_server: str) -> None:
    url = f"{fixture_server}/{PAGE}"

    async def run() -> Observation:
        async with DomDriver() as driver:
            await driver.start(url)
            return await driver.observe()

    observation = asyncio.run(run())
    hosts = allowed_hosts(url, [])
    blocked = {
        item["text"]: blocked_destination(
            Action(kind="click", element_id=element_id), observation, hosts
        )
        for element_id, item in observation.element_map.items()
    }

    assert blocked["안쪽 링크"] is None
    assert blocked["스크립트 링크"] is None
    assert blocked["버튼"] is None
    assert blocked["원본 사이트"] == "https://www.gachon.ac.kr/"
    # 파이썬 urljoin 은 이 둘을 사본 안 경로로 푼다. 브라우저가 푼 주소로 봐야 막힌다.
    assert blocked["역슬래시 링크"] == "https://www.gachon.ac.kr/"
    assert blocked["스킴 생략 링크"] == "http://www.gachon.ac.kr/"
    assert blocked["메일 보내기"] == "mailto:office@example.com"


class ClickByText(Decider):
    def __init__(self, text: str) -> None:
        self.text = text

    async def decide(self, persona, task, observation, history) -> Decision:
        element_id = next(
            i for i, item in observation.element_map.items() if item["text"] == self.text
        )
        return Decision(Action(kind="click", element_id=element_id))


def test_outside_link_is_blocked_and_page_stays(fixture_server: str) -> None:
    url = f"{fixture_server}/{PAGE}"
    acted: list[Action] = []

    async def run():
        async with DomDriver() as driver:
            await driver.start(url)
            real_act = driver.act

            async def spy_act(action: Action):
                acted.append(action)
                return await real_act(action)

            driver.act = spy_act
            agent = PersonaAgent(
                {"persona_id": 1}, {}, driver, ClickByText("원본 사이트"), allowed_hosts(url, [])
            )
            step = await agent.step()
            return step, await driver.observe()

    step, after = asyncio.run(run())

    assert step.result.ok is False
    assert step.result.error_code == "DOMAIN_BLOCKED"
    assert "https://www.gachon.ac.kr/" in step.result.error
    assert acted == []
    assert after.url == url


def test_inside_link_is_clicked(fixture_server: str) -> None:
    url = f"{fixture_server}/{PAGE}"

    async def run():
        async with DomDriver() as driver:
            await driver.start(url)
            agent = PersonaAgent(
                {"persona_id": 1}, {}, driver, ClickByText("안쪽 링크"), allowed_hosts(url, [])
            )
            step = await agent.step()
            return step, await driver.observe()

    step, after = asyncio.run(run())

    assert step.result.ok is True
    assert after.url == f"{url}?page=2"


def test_blocked_action_audit_detail_is_object(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    engine = create_db_engine(f"sqlite:///{tmp_path / 'agent.db'}")
    with engine.begin() as conn:
        conn.execute(
            text("CREATE TABLE audit_log (actor TEXT, action TEXT, target TEXT, detail TEXT)")
        )
    monkeypatch.setattr(audit_module, "engine", engine)
    repository = AuditLogRepository()

    repository.add_blocked_action(4, 2, {"step": 3, "reason": "domain"})
    with pytest.raises(TypeError):
        repository.add_blocked_action(4, 2, ["not", "an", "object"])  # type: ignore[arg-type]

    with engine.connect() as conn:
        rows = conn.execute(text("SELECT actor, action, target, detail FROM audit_log")).all()
    assert len(rows) == 1
    actor, action, target, detail = rows[0]
    assert (actor, action, target) == ("agent:4", "agent.action_blocked", "persona:2")
    assert json.loads(detail) == {"step": 3, "reason": "domain"}
