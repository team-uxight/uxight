"""도메인 이탈 차단 (GACA-152). 사본(로컬 http 서버) 밖 링크는 누르지 않고 차단을 남긴다."""

import asyncio
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from playwright.async_api import Error as PlaywrightError
from sqlalchemy import text

from uxight_agent.db import create_db_engine
from uxight_agent.driver.base import Observation
from uxight_agent.driver.dom_driver import (
    ACTION_TIMEOUT_MS,
    MAX_LATE_RETURNS,
    NEW_WINDOW_WAIT_MS,
    DomDriver,
)
from uxight_agent.guard.domain import (
    allowed_hosts,
    blocked_destination,
    is_allowed,
    safe_destination,
)
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


def test_safe_destination_drops_account_query_and_fragment() -> None:
    # 로그 · 감사 로그에 남기는 목적지 (GACA-224 리뷰). IPv6 대괄호는 그대로 둔다.
    assert (
        safe_destination("http://user:pw@a.example:8080/p?token=1#f") == "http://a.example:8080/p"
    )
    assert safe_destination("https://u@[::1]:8443/x?y=1") == "https://[::1]:8443/x"
    assert safe_destination("http://[2001:db8::1]/p#q") == "http://[2001:db8::1]/p"
    # 브라우저처럼 마지막 @ 뒤가 호스트다.
    assert safe_destination("http://a@b@c.example/") == "http://c.example/"


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
    # 페이지가 열릴 때 주 창이 스스로 창('side')을 열었으므로, 이번 행동의 새 창은 따르지 않는다.
    "named-window-link": (
        "<script>window.open('about:blank', 'side')</script><a href='/redir' target='side'>go</a>",
        STAYED,
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
    # 아래는 GACA-225 보안 리뷰에서 더했다.
    # 한꺼번에 둘 이상 열린 창은 어느 창의 주소인지 가를 수 없어 따르지 않는다.
    "two-windows": (
        "<button onclick=\"window.open('/inside?a'); window.open('/inside?b')\">go</button>",
        STAYED,
    ),
    # 주 창도 움직이면 새 창은 따르지 않는다. 주 창이 허용 밖으로 가면 지금처럼 끊고 남긴다.
    "window-then-main": (
        "<a href='/inside?main' onclick=\"window.open('/inside?popup')\">go</a>",
        ("inside?main", 0, None),
    ),
    "window-then-main-outside": (
        "<button onclick=\"window.open('/inside'); location.href = '{ext}'\">go</button>",
        BLOCKED,
    ),
    # 따라갈 주소도 파괴적 행동 가드의 경로 검사를 거친다.
    "pointer-cell-withdraw": (
        POINTER_CELL.replace("{to}", "/member/withdraw.do?confirm=1"),
        (None, 0, "DESTRUCTIVE_ACTION_BLOCKED"),
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
            if self.path.endswith("?spam"):
                # 허용 밖 iframe 이 자기를 넣은 허용 사이트 주소로 새 창을 거듭 연다.
                self.wfile.write(SPAM_FRAME.encode())
                return
            if self.path.startswith("/trap"):
                self.wfile.write(TRAP_PAGE.encode())
                return
            self.wfile.write(b"<html><body>outside</body></html>")

    external = _serve(External)
    ext = f"http://127.0.0.1:{external.server_address[1]}/outside"
    # 늦은 이동 시험(GACA-224)이 가는 허용 밖 trap 주소. 계정 · 토큰 · 조각이 들어 있다.
    trap = f"http://user:pw@127.0.0.1:{external.server_address[1]}/trap?token=SECRET#frag"

    pages = (
        {"/": BYPASS_PAGE}
        | {
            f"/new-window/{name}": f"<!doctype html><meta charset='utf-8'>{case[0]}"
            for name, case in NEW_WINDOW_CASES.items()
        }
        | {
            f"/unrelated/{name}": f"<meta charset='utf-8'><button>stay</button>{html}"
            for name, html in UNRELATED_WINDOW_PAGES.items()
        }
        | {f"/late/{ms}": LATE_PAGE.replace("{ms}", str(ms)) for ms in LATE_DELAYS_MS}
        | {"/covered": COVERED_PAGE, "/next": NEXT_PAGE, DELETE_PATH: DELETE_PAGE}
    )

    class Allowed(BaseHTTPRequestHandler):
        def log_message(self, *args) -> None:
            pass

        def do_GET(self) -> None:
            if self.path.startswith("/redir") or self.path.startswith("/late-redir"):
                self.send_response(302)
                self.send_header("Location", trap if self.path.startswith("/late") else ext)
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
            return step, after, await driver._windows()

    step, after, windows = asyncio.run(run())

    expected = f"{target}{path_after}" if path_after else url
    assert step.result.error_code == code
    # 따라가면 행동 결과의 url_after 가 새 창의 주소다. 누르기 전에 막은 step 은 url_after 가 없다.
    assert (step.result.url_after or step.observation.url) == expected
    assert after.url == expected
    assert len(hits) == outside_requests
    # 끊긴 새 창은 빈 창으로 남아 메모리를 먹는다. 행동 뒤 닫는다.
    assert windows == []


@pytest.mark.parametrize(
    ("windows", "state", "follows"),
    [
        ([{"openerFrameId": "main"}], {}, True),
        # 행동 중 허용 밖 이동을 끊었다 · 주 창도 움직였다 · 행동 전에 주 창이 스스로 창을 열었다
        ([{"openerFrameId": "main"}], {"_blocked_url": "http://outside.test/"}, False),
        ([{"openerFrameId": "main"}], {"_main_navigated": True}, False),
        ([{"openerFrameId": "main"}], {"_page_opened_window": True}, False),
        # iframe 이 연 창 · 한꺼번에 둘 이상 열린 창
        ([{"openerFrameId": "iframe"}], {}, False),
        ([{"openerFrameId": "main"}, {"openerFrameId": "main"}], {}, False),
    ],
)
def test_follow_only_window_opened_by_action(windows: list, state: dict, follows: bool) -> None:
    driver = DomDriver()
    driver._target_id = "main"
    driver._new_window_url = "http://allowed.test/inside"
    driver._navigated.set()
    for name, value in state.items():
        setattr(driver, name, value)

    async def listed() -> list[dict]:
        return [{"targetId": f"w{i}", **window} for i, window in enumerate(windows)]

    async def closed(windows: list[dict]) -> None:
        pass

    driver._windows, driver._close_windows = listed, closed

    url = asyncio.run(driver._new_window_to_follow())

    assert url == ("http://allowed.test/inside" if follows else None)


# 행동과 상관없이 페이지가 띄운 새 창 (광고 · 공지 팝업 등). 'stay' 는 아무 일도 하지 않는 버튼이다.
UNRELATED_WINDOW_PAGES = {
    # 페이지가 열린 뒤 한 번 띄우는 창
    "popup-on-load": "<script>setTimeout(() => window.open('/inside'), 500)</script>",
    # 주 창 스크립트가 거듭 띄우는 창. 행동 중에 생긴 창도 클릭이 열었는지 가를 수 없어, 행동 전에
    # 주 창이 연 창이 있었으면 따르지 않는다.
    "popup-interval": "<script>setInterval(() => window.open('/inside?ad'), 100)</script>",
    # 허용 밖 iframe 이 허용 사이트 주소로 거듭 띄우는 창. 연 frame 이 주 창이 아니라 따르지 않는다.
    "iframe-popup-interval": "<iframe src='{ext}?spam'></iframe>",
}
SPAM_FRAME = """<script>const to = new URL('/inside?iframe', document.referrer).href;
setInterval(() => window.open(to), 50)</script>"""


@pytest.mark.parametrize("page", UNRELATED_WINDOW_PAGES)
def test_window_not_opened_by_action_is_not_followed(two_sites, page: str) -> None:
    url = f"{two_sites[0]}unrelated/{page}"

    async def run():
        async with DomDriver(allowed_hosts=allowed_hosts(url, [])) as driver:
            await driver.start(url)
            # 가드가 새 창의 이동을 끊으면 requestfailed 가 온다. 창이 한 번 뜬 뒤에 행동한다.
            aborted = asyncio.Event()

            def on_failed(request) -> None:
                if request.is_navigation_request():
                    aborted.set()

            driver._page.context.on("requestfailed", on_failed)
            await asyncio.wait_for(aborted.wait(), 5)
            agent = PersonaAgent(
                {"persona_id": 1}, {}, driver, ClickByText("stay"), driver._allowed_hosts
            )
            return await agent.step()

    step = asyncio.run(run())

    assert step.result.ok is True
    assert step.result.url_after == url
    # 행동 전부터 있던 창 · iframe 이 연 창 때문에 새 창의 이동을 기다리지 않는다.
    assert step.browser_ms < NEW_WINDOW_WAIT_MS


# 늦은 이동 (GACA-224): 'go' 를 누르고 {ms} 뒤 스크립트가 주소를 허용 주소(/late-redir)로 바꾸고,
# 그 주소가 302 로 허용 밖 trap 페이지에 보낸다.
# 행동이 끝난 뒤라 행동 안의 3단계 되돌리기에 걸리지 않는다.
# 'next' 는 다른 허용 페이지로 가는 보통 링크다.
LATE_PAGE = (
    "<p>안쪽 글</p><button onclick=\"setTimeout(() => location.href = '/late-redir', {ms})\">"
    "go</button><a href='/late/1200'>next</a>"
)
LATE_DELAYS_MS = (800, 1200)
# 허용 밖 trap 페이지. 우리 번호 속성(data-ux-id, 공개 저장소에 있다)을 심어 두고, 거기서 누르거나
# 입력하면 밖 서버로 알린다.
# 알림 주소는 location.origin 으로 만든다 — trap 주소에 계정(user:pw@)이 있어, 상대 주소로
# 보내면 fetch 가 거절한다.
TRAP_PAGE = (
    '<button data-ux-id="1" onclick="fetch(location.origin + \'/clicked\')">trap</button>'
    '<input data-ux-id="2"'
    " oninput=\"fetch(location.origin + '/typed?v=' + encodeURIComponent(this.value))\">"
)
TRAP_SIGNALS = ("/clicked", "/typed")
# trap 주소의 계정 · 토큰 · 조각. 로그 · 오류 문구에는 이것을 뺀 주소(_trap)만 남아야 한다.
SECRET_PARTS = ("user:pw", "SECRET", "frag")


def _trap(ext: str) -> str:
    """/late-redir 가 보내는 trap 주소에서 계정 · 쿼리 · 조각을 뺀 것 (safe_destination)."""
    return ext.replace("/outside", "/trap")


class LateClicker(Decider):
    """'go' 를 누른다. 첫 step 뒤로는 think 초 생각한 뒤 정한다 (LLM 응답 시간)."""

    def __init__(self, think: float) -> None:
        self.think = think
        self.calls = 0

    async def decide(self, persona, task, observation, history) -> Decision:
        self.calls += 1
        if history:
            await asyncio.sleep(self.think)
        return await ClickByText("go").decide(persona, task, observation, history)


@pytest.mark.parametrize("delay_ms", LATE_DELAYS_MS)
@pytest.mark.parametrize("arrives", ["before-observe", "while-deciding"])
def test_late_navigation_outside_is_returned_and_blocked(
    two_sites, arrives: str, delay_ms: int
) -> None:
    target, ext, hits = two_sites
    url = f"{target}late/{delay_ms}"
    wait = delay_ms / 1000 + 0.5  # 늦은 이동이 허용 밖 주소에 닿기까지
    hits.clear()

    async def run():
        async with DomDriver(allowed_hosts=allowed_hosts(url, [])) as driver:
            await driver.start(url)
            decider = LateClicker(wait if arrives == "while-deciding" else 0)
            agent = PersonaAgent({"persona_id": 1}, {}, driver, decider, driver._allowed_hosts)
            clicked = await agent.step()  # 행동은 바로 끝난다. 이동은 delay_ms 뒤에 일어난다
            if arrives == "before-observe":
                await asyncio.sleep(wait)
            late = await agent.step()
            after = await driver.observe()
            await asyncio.sleep(0.3)  # trap 에서 눌렸다면 그 알림이 서버에 닿게
            return clicked, late, after, decider.calls

    clicked, late, after, calls = asyncio.run(run())

    assert clicked.result.ok is True
    assert clicked.result.url_after == url
    # 차단으로 남는다 — step 로그 · 감사 로그는 이 결과로 쓴다. 계정 · 쿼리 · 조각은 뺀다.
    assert late.result.error_code == "DOMAIN_BLOCKED"
    assert late.result.destination == _trap(ext)
    assert not any(part in late.result.error for part in SECRET_PARTS)
    # 페이지가 스스로 간 것이라 프롬프트에는 링크 차단과 다른 문구로 보인다.
    assert late.result.late is True
    # 주 창이 허용 주소로 돌아오고, 허용 밖 페이지의 글 · 요소는 관측에 들어가지 않는다.
    assert (late.result.url_after or late.observation.url) == url
    for observation in (late.observation, after):
        assert observation.url == url
        assert "안쪽 글" in observation.text
        assert "trap" not in observation.dom
    # 늦은 이동 하나는 차단 하나로 남는다. 되돌린 뒤의 관측은 차단이 아니다.
    assert after.blocked is None
    # 허용 밖 요청은 늦은 이동이 낸 하나뿐이다. 되돌리기는 허용 밖으로 가지 않고,
    # trap 에서 누르거나 입력하지 않았다.
    assert [hit.split("?")[0] for hit in hits] == ["/trap"]
    if arrives == "before-observe":
        # 관측 전에 되돌렸다. LLM 을 부르지 않고 차단만 남긴다.
        assert late.observation.blocked == _trap(ext)
        assert late.action is None
        assert calls == 1
    else:
        # 행동을 정하는 사이 허용 밖으로 갔다. trap 에도 같은 번호(1)가 있지만 누르지 않는다.
        # 누르려 했다면 번호 요소를 찾다가 ACTION_TIMEOUT_MS 를 다 쓴다.
        assert late.action == Action(kind="click", element_id=1)
        assert late.browser_ms < ACTION_TIMEOUT_MS


class Fixed(Decider):
    """정해 둔 행동 하나를 낸다."""

    def __init__(self, action: Action) -> None:
        self.action = action

    async def decide(self, persona, task, observation, history) -> Decision:
        return Decision(self.action)


# 행동을 기다리는 사이 늦은 이동 (GACA-224 리뷰): 가림 막이 3초 동안 덮고, 입력칸은 그동안
# 읽기 전용이다. 클릭 · 입력이 기다리는 사이 700ms 뒤 페이지가 허용 밖 trap 페이지로 간다.
COVERED_PAGE = (
    "<button style='width:300px; height:100px'>go</button><input name='q' readonly>"
    "<div id='cover' style='position:fixed; inset:0; z-index:10'></div>"
    "<script>setTimeout(() => { cover.remove(); document.querySelector('input').readOnly = false },"
    " 3000); setTimeout(() => location.href = '/late-redir', 700)</script>"
)


@pytest.mark.parametrize(
    "action",
    [Action(kind="click", element_id=1), Action(kind="type", element_id=2, value="비밀 1234")],
    ids=["click", "type"],
)
def test_action_is_not_done_on_page_that_left_while_waiting(two_sites, action: Action) -> None:
    # Locator 로 행동하면 기다리는 사이 바뀐 문서에서 같은 번호를 다시 찾아,
    # trap 에서 누르고 입력한다. 결과는 차단이나 실패다.
    target, _, hits = two_sites
    url = f"{target}covered"
    hits.clear()

    async def run():
        async with DomDriver(allowed_hosts=allowed_hosts(url, [])) as driver:
            await driver.start(url)
            agent = PersonaAgent(
                {"persona_id": 1}, {}, driver, Fixed(action), driver._allowed_hosts
            )
            step = await agent.step()
            await asyncio.sleep(0.5)  # trap 에서 눌렸다면 그 알림이 서버에 닿게
            return step

    step = asyncio.run(run())

    assert step.result.ok is False
    assert not [hit for hit in hits if hit.startswith(TRAP_SIGNALS)]


def test_element_on_outside_page_is_not_acted_on(two_sites) -> None:
    # 행동 전 확인과 요소를 찾는 사이 주 창이 허용 밖 trap 으로 간 경우(아주 짧은 틈)다.
    # _perform 을 바로 불러 만든다. 요소가 든 문서의 주소를 보고 행동하지 않는다.
    target, _, hits = two_sites
    url = f"{target}late/800"
    hits.clear()

    async def run():
        async with DomDriver(allowed_hosts=allowed_hosts(url, [])) as driver:
            await driver.start(url)
            await driver.observe()  # 'go' 가 1번이다
            await _leave(driver, "/late-redir")
            result = await driver._perform(Action(kind="click", element_id=1))
            await asyncio.sleep(0.5)
            return result

    result = asyncio.run(run())

    assert result.ok is False
    assert not [hit for hit in hits if hit.startswith(TRAP_SIGNALS)]


async def _leave(driver: DomDriver, to: str = "/redir") -> None:
    """늦은 이동을 일으킨다: 행동과 상관없이 주 창이 to 로 가고, 302 로 허용 밖에 닿는다."""
    await driver._page.evaluate(f"setTimeout(() => location.href = '{to}')")
    await driver._page.wait_for_url(lambda url: not is_allowed(url, driver._allowed_hosts))


def test_late_returns_are_capped_per_persona(two_sites) -> None:
    # 되돌린 페이지가 또 허용 밖으로 보내면 되돌릴 때마다 허용 밖 요청이 는다.
    # Persona 하나에 MAX_LATE_RETURNS 번까지 되돌리고, 넘으면 관측이 오류를 낸다(Persona 는 fail).
    target, ext, hits = two_sites
    hits.clear()

    async def run():
        async with DomDriver(allowed_hosts=allowed_hosts(target, [])) as driver:
            await driver.start(target)
            observations = []
            for _ in range(MAX_LATE_RETURNS):
                await _leave(driver)
                observations.append(await driver.observe())
            await _leave(driver)
            with pytest.raises(RuntimeError, match="되돌리지 못했습니다"):
                await driver.observe()
            return observations

    observations = asyncio.run(run())

    assert [o.blocked for o in observations] == [ext] * MAX_LATE_RETURNS
    assert [o.url for o in observations] == [target] * MAX_LATE_RETURNS
    assert len(hits) == MAX_LATE_RETURNS + 1  # 늦은 이동마다 하나. 넘은 뒤로는 되돌리지 않는다


def test_late_return_stops_when_return_address_leaves_too(two_sites) -> None:
    # 마지막 허용 주소마저 허용 밖으로 리다이렉트한다.
    # 예: 세션이 끝나면 허용 밖 로그인 페이지로 보내는 사이트.
    # 되돌리기는 한 번만 해 보고 그만둔다. 관측은 허용 밖 페이지를 보지 않고 오류를 낸다.
    target, ext, hits = two_sites
    hits.clear()

    async def run():
        async with DomDriver(allowed_hosts=allowed_hosts(target, [])) as driver:
            await driver.start(target)
            driver._last_allowed_url = f"{target}redir"
            await _leave(driver)
            for _ in range(2):
                with pytest.raises(RuntimeError, match="되돌리지 못했습니다"):
                    await driver.observe()
            return driver._page.url

    url = asyncio.run(run())

    assert url == ext
    assert len(hits) == 2  # 늦은 이동 하나 + 되돌려 본 것 하나


@pytest.mark.parametrize("path", ["late", "action"])
def test_failed_return_leaves_no_outside_address_in_url_after(two_sites, path: str) -> None:
    # 되돌리기가 실패해 허용 밖에 남으면 url_after 를 비운다.
    # 허용 밖 주소의 원문(계정 · 토큰)이 step 로그에 남지 않게.
    # 늦은 이동(행동 전 되돌림)과 행동의 리다이렉트(3단계) 두 길이다.
    target, _, _ = two_sites

    async def run():
        async with DomDriver(allowed_hosts=allowed_hosts(target, [])) as driver:
            await driver.start(target)
            observation = await driver.observe()

            async def fail(*args, **kwargs) -> None:
                raise PlaywrightError("navigation failed")

            if path == "late":
                await _leave(driver, "/late-redir")
                driver._page.goto = fail
                return await driver.act(Action(kind="scroll", value="down"))
            link = next(
                i for i, it in observation.element_map.items() if it["text"] == "redirect link"
            )
            driver._page.goto = fail
            return await driver.act(Action(kind="click", element_id=link))

    result = asyncio.run(run())

    assert result.error_code == "DOMAIN_BLOCKED"
    assert result.url_after is None


# 상태를 바꾸는 GET (GACA-224 리뷰): '다음' 은 글 · 주소에 동사가 없어 파괴적 행동 가드를 지나고,
# 스크립트가 삭제 주소로 간다. 삭제 페이지의 '계속' 은 허용 밖으로 리다이렉트한다.
DELETE_PATH = "/member/delete.do?id=7&token=T"
NEXT_PAGE = f"<button onclick=\"location.href = '{DELETE_PATH}'\">다음</button>"
DELETE_PAGE = "<p>삭제했습니다</p><a href='/redir'>계속</a>"


class ClickTexts(Decider):
    """step 마다 다음 글의 요소를 누른다."""

    def __init__(self, *texts: str) -> None:
        self.texts = list(texts)

    async def decide(self, persona, task, observation, history) -> Decision:
        return await ClickByText(self.texts.pop(0)).decide(persona, task, observation, history)


def _count_deletes(driver: DomDriver) -> list[str]:
    """주 창이 보낸 삭제 주소 요청을 모은다."""
    deletes: list[str] = []

    def on_request(request) -> None:
        if DELETE_PATH in request.url:
            deletes.append(request.url)

    driver._page.on("request", on_request)
    return deletes


@pytest.mark.parametrize("leaves", ["late", "action"])
def test_return_does_not_resend_destructive_get(two_sites, leaves: str) -> None:
    # 되돌리기는 되돌릴 곳을 다시 GET 한다.
    # 파괴적 경로(destructive_path)는 되돌릴 곳으로 기억하지 않고, 행동 전 주소가 파괴적 경로면
    # 그 전에 기억한 주소로 되돌린다.
    target, ext, _ = two_sites
    url = f"{target}next"

    async def run():
        async with DomDriver(allowed_hosts=allowed_hosts(url, [])) as driver:
            await driver.start(url)
            deletes = _count_deletes(driver)
            agent = PersonaAgent(
                {"persona_id": 1}, {}, driver, ClickTexts("다음", "계속"), driver._allowed_hosts
            )
            await agent.step()  # 다음 → 삭제 GET
            step = None
            if leaves == "late":
                await _leave(driver)  # 삭제 페이지가 늦게 허용 밖으로 간다
            else:
                step = await agent.step()  # 계속 → 302 로 허용 밖 → 3단계 되돌리기
            return deletes, step, await driver.observe()

    deletes, step, observation = asyncio.run(run())

    assert len(deletes) == 1  # Persona 가 누른 한 번뿐
    assert observation.url == url
    if leaves == "late":
        assert observation.blocked == ext
    else:
        assert step.result.error_code == "DOMAIN_BLOCKED"
        assert step.result.url_after == url


def test_destructive_start_page_is_not_a_return_address(two_sites) -> None:
    # 시작 주소부터 파괴적 경로면 되돌릴 곳이 없다. 다시 GET 하지 않고 차단 · 오류로 끝낸다.
    target, _, _ = two_sites
    url = f"{target}{DELETE_PATH[1:]}"

    async def run():
        async with DomDriver(allowed_hosts=allowed_hosts(url, [])) as driver:
            await driver.start(url)
            deletes = _count_deletes(driver)
            agent = PersonaAgent(
                {"persona_id": 1}, {}, driver, ClickByText("계속"), driver._allowed_hosts
            )
            step = await agent.step()  # 계속 → 302 로 허용 밖. 행동 전 주소(삭제)로 가지 않는다
            with pytest.raises(RuntimeError, match="되돌리지 못했습니다"):
                await driver.observe()
            late = await driver.act(Action(kind="scroll", value="down"))
            return deletes, step, late

    deletes, step, late = asyncio.run(run())

    assert deletes == []
    assert step.result.error_code == "DOMAIN_BLOCKED"
    assert step.result.url_after is None
    assert (late.error_code, late.url_after) == ("DOMAIN_BLOCKED", None)


def test_return_address_is_last_allowed_page(two_sites) -> None:
    # 되돌릴 곳은 마지막으로 허용 안에서 본 주소다. 관측 · 행동이 끝날 때마다 바뀐다.
    target, ext, _ = two_sites
    url = f"{target}late/800"

    async def run():
        async with DomDriver(allowed_hosts=allowed_hosts(url, [])) as driver:
            await driver.start(url)
            returned = []
            # 행동: 관측한 뒤 'next' 를 눌러 /late/1200 으로 가고, 다음 관측 전에 늦은 이동
            agent = PersonaAgent(
                {"persona_id": 1}, {}, driver, ClickByText("next"), driver._allowed_hosts
            )
            await agent.step()
            await _leave(driver)
            returned.append(await driver.observe())
            # 관측: 페이지가 행동 없이 다른 허용 페이지로 간 것을 관측한 뒤 늦은 이동
            await driver._page.goto(f"{target}inside")
            await driver.observe()
            await _leave(driver)
            returned.append(await driver.observe())
            return returned

    returned = asyncio.run(run())

    assert [o.blocked for o in returned] == [ext, ext]
    assert [o.url for o in returned] == [f"{target}late/1200", f"{target}inside"]


def test_text_from_page_that_left_and_came_back_is_dropped(two_sites) -> None:
    # 확인과 모으기 사이 주 창이 허용 밖에 닿았다가, 모은 뒤 곧 허용 주소로 돌아온다.
    # 예: SSO 처럼 거쳐 가는 페이지.
    # 모은 뒤의 주 창 주소는 허용이지만, 글은 그 글을 모은 문서의 주소로 판정해 버린다.
    target, ext, hits = two_sites
    hits.clear()

    async def run():
        async with DomDriver(allowed_hosts=allowed_hosts(target, [])) as driver:
            await driver.start(target)
            real_collect = driver._collect_elements
            calls = 0

            async def collect_on_outside_page(page) -> dict:
                nonlocal calls
                calls += 1
                if calls > 1:
                    return await real_collect(page)
                await page.goto(f"{target}redir")  # 확인한 직후 허용 밖에 닿았다
                collected = await real_collect(page)  # 그래서 허용 밖 페이지의 글을 모은다
                await page.goto(target)  # 그 페이지가 곧 허용 주소로 돌려보냈다
                return collected

            driver._collect_elements = collect_on_outside_page
            return await driver.observe(), calls

    observation, calls = asyncio.run(run())

    assert calls == 2
    assert observation.blocked == ext
    assert observation.url == target
    assert "outside" not in observation.text
    assert len(hits) == 1


def test_step_screenshot_of_page_that_left_is_dropped(two_sites) -> None:
    # 글을 모은 뒤 찍기 전에 주 창이 허용 밖으로 간다. 그 그림은 허용 밖 페이지일 수 있어 버린다
    # (SoM 과 같은 규칙). 마지막 화면 스크린샷(GACA-221)도 observe() 로 찍으므로 같다.
    target, _, _ = two_sites

    async def run():
        async with DomDriver(allowed_hosts=allowed_hosts(target, [])) as driver:
            await driver.start(target)
            real_observe_page = driver._observe_page

            async def observe_then_leave() -> Observation:
                observation = await real_observe_page()
                await _leave(driver)
                return observation

            driver._observe_page = observe_then_leave
            return await driver.observe()

    observation = asyncio.run(run())

    assert observation.url == target
    assert observation.screenshot is None
