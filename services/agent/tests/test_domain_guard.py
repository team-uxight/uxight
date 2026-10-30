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

# 새 창(target=_blank · window.open · 이름 있는 창 · form.target)의 이동은 주소와 상관없이 끊는다
# (GACA-223). 행동 뒤 첫 이동이 새 창의 허용 주소 GET 이면 그 주소를 주 창에서 연다 (GACA-225).
# 'go' 를 누르는 페이지들이다. 처음 17가지는 GACA-223 보안 리뷰 probe 의 시나리오다.
# 빈 창에 주소를 나중에 넣는 두 가지만 300ms 를 100ms 로 줄였다 — 기다리는 상한(500ms)과 거리를
# 두려고.
# 허용된 주소는 대부분 허용 밖으로 보내는 리다이렉트(/redir)다. 따라가면 주 창이 허용 밖 주소에
# 한 번 닿고 3단계가 되돌린다. 같은 창 링크(위 'redirect link')와 같다.
# 새 창이 스스로 요청을 보냈다면 허용 밖 요청이 하나 더 는다.
# 행동 뒤 결과: (주 창 경로 — None 이면 그대로, 허용 밖 요청 수, 오류 코드)
REVERTED = (None, 1, "DOMAIN_BLOCKED")  # 따라간 주소가 허용 밖으로 리다이렉트 → 3단계가 되돌린다
FOLLOWED = ("inside", 0, None)  # 따라가 주 창이 그 주소로 간다
BLOCKED = (None, 0, "DOMAIN_BLOCKED")  # 허용 밖 주소 → 끊고 차단으로 남긴다
STAYED = (None, 0, None)  # 따르지 않는다
# 학교 사본 졸업 페이지의 학번 칸: 링크가 아닌 칸을 누르면 스크립트가 칸 안 경로를
# 창 이름 · 크기와 함께 새 창으로 연다. 손가락 커서라 번호가 붙는다.
POINTER_CELL = (
    "<table><tr><td style='cursor: pointer' onclick=\"window.open(this.querySelector('span')"
    ".textContent, 'table-credit', 'width=1200, height=600')\"><p>go</p>"
    "<span style='display: none'>{to}</span></td></tr></table>"
)
NEW_WINDOW_CASES = {
    "blank-link": ('<a href="/redir" target="_blank">go</a>', REVERTED),
    "open-blank-move-later": (
        "<button onclick=\"const w = window.open(''); "
        "setTimeout(() => w.location = '/redir', 100)\">go</button>",
        REVERTED,
    ),
    "open-blank-move": (
        "<button onclick=\"const w = window.open(''); w.location = '/redir'\">go</button>",
        REVERTED,
    ),
    "open-inside-move-later": (
        "<button onclick=\"const w = window.open('/inside'); "
        "setTimeout(() => w.location = '/redir', 300)\">go</button>",
        FOLLOWED,
    ),
    "open-blank-meta-refresh": (
        "<button onclick=\"const w = window.open(''); "
        "w.document.write('<meta http-equiv=refresh content=0;url=/redir>'); w.document.close()\">"
        "go</button>",
        REVERTED,
    ),
    "named-window-link": (
        "<script>window.open('about:blank', 'side')</script><a href='/redir' target='side'>go</a>",
        REVERTED,
    ),
    "form-new-window": (
        '<form action="/redir" target="_blank"><button type="submit">go</button></form>',
        REVERTED,
    ),
    "base-target": ('<base target="_blank"><a href="/redir">go</a>', REVERTED),
    "open-noopener": (
        "<button onclick=\"window.open('/redir', '_blank', 'noopener')\">go</button>",
        REVERTED,
    ),
    "open-outside": ("<button onclick=\"window.open('{ext}')\">go</button>", BLOCKED),
    "blank-link-inside": ('<a href="/inside" target="_blank">go</a>', FOLLOWED),
    "open-blob-meta-refresh": (
        "<button onclick=\"window.open(URL.createObjectURL(new Blob(['<meta http-equiv=refresh "
        "content=0;url=/redir>'], { type: 'text/html' })))\">go</button>",
        STAYED,
    ),
    "open-javascript-url": (
        "<button onclick=\"window.open('javascript:location.href=\\'/redir\\'')\">go</button>",
        STAYED,
    ),
    "open-data-url-outside": (
        "<button onclick=\"window.open('data:text/html,<meta http-equiv=refresh "
        "content=0;url={ext}>')\">go</button>",
        STAYED,
    ),
    "open-about-blank-move-later": (
        "<button onclick=\"const w = window.open('about:blank', '_blank'); "
        "setTimeout(() => w.location = '/redir', 100)\">go</button>",
        REVERTED,
    ),
    "open-inside-move-after-4s": (
        "<button onclick=\"const w = window.open('/inside'); "
        "setTimeout(() => w.location = '/redir', 4000)\">go</button>",
        FOLLOWED,
    ),
    "form-named-popup": (
        '<form action="/redir" target="pay"><input type="hidden" name="amount" value="1">'
        "<button type=\"submit\" onclick=\"window.open('', 'pay', 'width=400, height=300')\">"
        "go</button></form>",
        REVERTED,
    ),
    # 아래는 GACA-225 에서 더했다.
    # 하위 요청이 계속 나가는 페이지 (GACA-223: 가드 오류가 다른 요청을 거쳐 관측에서 터졌다).
    "busy-blank-link": (
        '<a href="/redir" target="_blank">go</a>'
        "<script>setInterval(() => { new Image().src = '/img?' + Math.random(); }, 20)</script>",
        REVERTED,
    ),
    "pointer-cell": (POINTER_CELL.replace("{to}", "/inside"), FOLLOWED),
    "pointer-cell-outside": (POINTER_CELL.replace("{to}", "{ext}"), BLOCKED),
    # 밖으로 가는 새 창 링크는 1단계(누르기 전)에서 막힌다.
    "blank-link-outside": ('<a href="{ext}" target="_blank">go</a>', BLOCKED),
    # 폼 POST 는 주 창에서 다시 보낼 수 없어 따르지 않는다.
    # 버튼 이름이 '검색' 이라 파괴적 행동 가드는 통과한다.
    "form-post-new-window": (
        '<form method="post" action="/redir" target="_blank">'
        '<button type="submit" aria-label="검색">go</button></form>',
        STAYED,
    ),
}


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

    pages = {"/": BYPASS_PAGE, "/popup-on-load": POPUP_ON_LOAD_PAGE} | {
        f"/new-window/{name}": f"<!doctype html><meta charset='utf-8'>{case[0]}"
        for name, case in NEW_WINDOW_CASES.items()
    }

    class Allowed(BaseHTTPRequestHandler):
        def log_message(self, *args) -> None:
            pass

        def do_GET(self) -> None:
            if self.path.startswith("/redir"):
                self.send_response(302)
                self.send_header("Location", ext)
                self.end_headers()
                return
            body = pages.get(self.path, "<html>inside</html>").replace("{ext}", ext)
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(body.encode())

        # 새 창의 폼 POST 가 새어 나가면 /redir 를 거쳐 허용 밖 요청으로 잡힌다.
        do_POST = do_GET

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


@pytest.mark.parametrize("case", NEW_WINDOW_CASES)
def test_new_window_followed_in_main_window_through_guard(two_sites, case: str) -> None:
    target, ext, hits = two_sites
    url = f"{target}new-window/{case}"
    _, (path_after, outside_requests, code) = NEW_WINDOW_CASES[case]
    hits.clear()

    async def run():
        async with DomDriver(allowed_hosts=allowed_hosts(url, [])) as driver:
            await driver.start(url)
            agent = PersonaAgent(
                {"persona_id": 1}, {}, driver, ClickByText("go"), driver._allowed_hosts
            )
            step = await agent.step()
            after = await driver.observe()  # 가드가 예외를 내면 Playwright 가 여기서 대신 던진다
            return step, after

    step, after = asyncio.run(run())

    expected = f"{target}{path_after}" if path_after else url
    assert step.result.error_code == code
    # 따라가면 행동 결과의 url_after 가 새 창의 주소다. 누르기 전에 막은 step 은 url_after 가 없다.
    assert (step.result.url_after or step.observation.url) == expected
    assert after.url == expected
    assert len(hits) == outside_requests


# 행동과 상관없이 페이지가 띄운 새 창 (광고 · 공지 팝업 등).
POPUP_ON_LOAD_PAGE = """<!doctype html><meta charset="utf-8">
<button>stay</button><script>setTimeout(() => window.open('/inside'), 500)</script>"""


def test_popup_without_action_is_not_followed_and_closed(two_sites) -> None:
    url = f"{two_sites[0]}popup-on-load"

    async def run():
        async with DomDriver(allowed_hosts=allowed_hosts(url, [])) as driver:
            await driver.start(url)
            # 가드가 새 창의 이동을 끊으면 requestfailed 가 온다. 그때까지 기다린 뒤 행동한다.
            aborted = asyncio.Event()

            def on_failed(request) -> None:
                if request.is_navigation_request():
                    aborted.set()

            driver._page.context.on("requestfailed", on_failed)
            await asyncio.wait_for(aborted.wait(), 5)
            agent = PersonaAgent(
                {"persona_id": 1}, {}, driver, ClickByText("stay"), driver._allowed_hosts
            )
            step = await agent.step()
            targets = (await driver._cdp.send("Target.getTargets"))["targetInfos"]
            return step, [t for t in targets if t["type"] == "page"]

    step, pages = asyncio.run(run())

    assert step.result.ok is True
    assert step.result.url_after == url
    # 끊긴 새 창은 빈 창으로 남아 메모리를 먹는다. 행동 뒤 닫는다.
    assert len(pages) == 1
