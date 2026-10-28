"""도메인 이탈 차단 (GACA-152). 사본(로컬 http 서버) 밖 링크는 누르지 않고 차단을 남긴다."""

import asyncio
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from sqlalchemy import text

from uxight_agent.db import create_db_engine
from uxight_agent.driver.base import Observation
from uxight_agent.driver.dom_driver import DomDriver
from uxight_agent.guard.domain import allowed_hosts, blocked_destination, is_allowed
from uxight_agent.persona.persona_agent import Decider, Decision, PersonaAgent
from uxight_agent.repositories import audit_log_repository as audit_module
from uxight_agent.repositories.audit_log_repository import AuditLogRepository
from uxight_agent.schemas import Action

PAGE = "domain_links.html"


def test_allowed_hosts_are_snapshot_plus_target_host_and_port() -> None:
    hosts = allowed_hosts("https://Copy.Example:8443/kor/index.do", [" CDN.example ", "", "a.b:81"])

    assert hosts == frozenset({"copy.example:8443", "cdn.example:80", "cdn.example:443", "a.b:81"})
    assert is_allowed("https://copy.example:8443/x", hosts)
    assert not is_allowed("https://copy.example/x", hosts)  # 같은 호스트 다른 포트 = 밖
    assert not is_allowed("http://sub.cdn.example/", hosts)
    assert not is_allowed("javascript:void(0)", hosts)


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
    assert blocked["버튼"] is None
    # javascript: 링크는 목적지를 알 수 없어 막는다.
    assert blocked["스크립트 링크"] == "javascript:void(0)"
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


# 클릭 전에는 목적지를 알 수 없거나 속는 이동 — 브라우저가 이동 요청을 끊거나 되돌려야 막힌다.
BYPASS_PAGE = """<!doctype html><html><head><meta charset="utf-8"></head><body>
<a href="javascript:location.href='{ext}'">js link</a>
<svg width="200" height="40"><a href="{ext}"><text x="5" y="20">svg link</text></a></svg>
<a href="/redir">redirect link</a>
<form action="{ext}" method="get"><button type="submit">form go</button></form>
<a href="/inside" onmousedown="this.href='{ext}'">rewrite link</a>
</body></html>"""


def _serve(handler: type[BaseHTTPRequestHandler]) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


@pytest.fixture(scope="module")
def two_sites():
    """허용 사이트 · 외부 사이트 두 서버 (같은 호스트, 다른 포트 = 밖). 외부가 받은 요청을 센다."""
    hits: list[str] = []

    class External(BaseHTTPRequestHandler):
        def log_message(self, *args) -> None:
            pass

        def do_GET(self) -> None:
            hits.append(self.path)
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<html><body>outside</body></html>")

    external = _serve(External)
    ext = f"http://127.0.0.1:{external.server_address[1]}/outside"

    class Allowed(BaseHTTPRequestHandler):
        def log_message(self, *args) -> None:
            pass

        def do_GET(self) -> None:
            if self.path.startswith("/redir"):
                self.send_response(302)
                self.send_header("Location", ext)
                self.end_headers()
                return
            body = BYPASS_PAGE.format(ext=ext) if self.path == "/" else "<html>inside</html>"
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(body.encode())

    allowed = _serve(Allowed)
    yield f"http://127.0.0.1:{allowed.server_address[1]}/", ext, hits
    allowed.shutdown()
    external.shutdown()


@pytest.mark.parametrize(
    "label", ["js link", "svg link", "redirect link", "form go", "rewrite link"]
)
def test_navigation_outside_is_blocked_whatever_the_route(two_sites, label: str) -> None:
    target, ext, hits = two_sites
    hits.clear()

    async def run():
        async with DomDriver(allowed_hosts=allowed_hosts(target, [])) as driver:
            await driver.start(target)
            agent = PersonaAgent(
                {"persona_id": 1}, {}, driver, ClickByText(label), driver._allowed_hosts
            )
            step = await agent.step()
            await asyncio.sleep(0.5)  # 늦게 시작하는 이동도 기다린다
            return step, driver._page.url

    step, url_after_wait = asyncio.run(run())

    assert step.result.error_code == "DOMAIN_BLOCKED"
    assert ext in step.result.destination  # js 링크는 javascript:… 그대로
    # 클릭 전에 막은 step 은 브라우저 행동이 없어 url_after 가 없다 — 로그엔 행동 전 주소.
    assert (step.result.url_after or step.observation.url) == target
    assert url_after_wait == target
    if label != "redirect link":
        # 리다이렉트는 같은 도메인 요청의 응답이라 외부 요청이 한 번 나간 뒤 되돌린다.
        assert hits == []
