"""성능 benchmark (GACA-179). 시험 페이지(tests/fixtures)에서 진짜 드라이버 · 가드 · LLMDecider 를
가짜 LLM 응답으로 돌려 설정 → 실행 → 표 · csv · jsonl 이 나오는지 본다. DB 는 쓰지 않는다.
Persona 실행이 끝나는 길(시간 상한 · 토큰 상한 · 실행 오류 · 브라우저 닫기)은 가짜 드라이버로 본다.
"""

import asyncio
import csv
import functools
import json
import os
import shutil
import socket
import subprocess
import sys
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from conftest import FIXTURES

from uxight_agent import bench, bench_metrics
from uxight_agent.driver.base import ActionResult, Driver, Observation
from uxight_agent.persona.llm_decider import LLMDecider
from uxight_agent.persona.persona_agent import Decider, Decision
from uxight_agent.schemas import Action

REPO_PERSONAS = Path(__file__).resolve().parents[3] / "config" / "school_personas_50.json"
PAGE = "domain_links.html"  # 요소 1 = 안쪽 링크(?page=2)
SPEC_FIELDS = {
    "run_id", "persona_id", "step", "ts", "url", "observation", "reasoning", "action", "result",
    "blocked", "latency_ms", "tokens", "model", "task",
}  # fmt: skip


def reply(kind: str, element_id: int | None = None, value: str | None = None) -> str:
    action = {"kind": kind, "element_id": element_id, "value": value}
    return json.dumps({"reasoning": "시험", "action": action}, ensure_ascii=False)


CLICK_INSIDE, DONE, SCROLL = reply("click", 1), reply("done"), reply("scroll", value="down")
BROKEN = '{"reasoning": "다음'
# 실행 순서는 사이트 → Task → 반복 → 변형 → Persona (동시 1). 회차 번호도 이 순서다.
REPLIES = [
    CLICK_INSIDE, DONE,  # 1 original · dom: 안쪽 링크로 성공 URL 에 닿고 done
    SCROLL, DONE,  # 2 original · som: 성공 URL 에 닿지 않는다
    BROKEN, CLICK_INSIDE, DONE,  # 3 seed1 · dom: 깨진 JSON 하나
    None, CLICK_INSIDE, DONE,  # 4 seed1 · som: LLM 호출 실패(HTTP 500) 하나
]  # fmt: skip
ANSWERS = {
    "seed": 1,
    "injected": [
        {"catalog_id": "NAV-L", "page": "*", "selector": "#gnb", "before": "안내", "after": "소개"},
        {"catalog_id": "TASK-L", "page": f"/{PAGE}", "selector": "h2", "before": "홈", "after": ""},
        {"catalog_id": "DST-ALT", "page": f"/{PAGE}", "selector": "img", "before": "", "after": ""},
    ],
}


def finding(taxonomy: str, url: str) -> dict:
    evidence = [{"persona_id": "P001", "step_from": 1, "step_to": 2, "url": url}]
    return {"taxonomy": taxonomy, "severity": "high", "summary": "시험", "evidence": evidence}


def write_json(path: Path, value) -> Path:
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    return path


@pytest.fixture
def setup(tmp_path: Path, fixture_server: str, monkeypatch: pytest.MonkeyPatch) -> dict:
    """설정 파일 · Persona 파일 · 정답 · 진단 파일과 --serve 로 띄울 결함 사본 폴더."""
    monkeypatch.setenv("LLM_PRICES", '{"test-model": [1.0, 2.0]}')
    monkeypatch.setenv("BENCH_COMMIT", "abc1234")
    persona = {"persona_id": "P001", "name": "계층 우선", "web_skill": "low", "behavior": ["본다"]}
    write_json(tmp_path / "personas.json", [persona])
    write_json(tmp_path / "answers-seed1.json", ANSWERS)
    write_json(
        tmp_path / "findings-dom-seed1.json",
        [finding("task_failure", f"http://127.0.0.1:9/{PAGE}?page=2")],
    )
    write_json(
        tmp_path / "findings-dom-original.json",
        [finding("task_failure", "http://x/a"), finding("excessive_steps", "http://x/b")],
    )
    site = tmp_path / "site-seed1"
    site.mkdir()
    shutil.copy(FIXTURES / PAGE, site / PAGE)
    config = {
        "name": "시험",
        "personas_file": "personas.json",
        "personas": ["P001"],
        "tasks": [
            {"goal": "두 번째 쪽 찾기", "success_rule": "두 번째 쪽",
             "success_url": f"/{PAGE}?page=2"},
        ],
        "sites": [
            {"name": "original", "url": f"{fixture_server}/{PAGE}", "original": True,
             "findings": {"dom": "findings-dom-original.json"}},
            {"name": "seed1", "url": f"/{PAGE}", "answers": "answers-seed1.json",
             "findings": {"dom": "findings-dom-seed1.json"}},
        ],
        "variants": {"dom": {"observation": "dom"}, "som": {"observation": "som"}},
        "max_steps": 5,
        "max_seconds": 60,
    }  # fmt: skip
    return {
        "config": write_json(tmp_path / "bench.json", config),
        "site": site,
        "out": tmp_path / "out",
        "usage_log": tmp_path / "llm-usage.jsonl",
    }


@pytest.fixture
def ran(setup: dict, scripted_llm) -> dict:
    llm, requests = scripted_llm(*REPLIES)
    argv = [str(setup["config"]), "--out", str(setup["out"]), "--serve", f"seed1={setup['site']}"]

    assert bench.main(argv, make_decider=functools.partial(LLMDecider, llm)) == 0

    out = setup["out"]
    with (out / "summary.csv").open(encoding="utf-8") as f:
        rows = {(r["variant"], r["site"]): r for r in csv.DictReader(f)}
    return {
        "out": out,
        "md": (out / "summary.md").read_text(encoding="utf-8"),
        "csv": rows,
        "personas": _jsonl(out / "personas.jsonl"),
        "steps": _jsonl(out / "steps.jsonl"),
        "requests": requests,
        "usage_log": setup["usage_log"],
    }


def _jsonl(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x]


def _md_row(md: str, variant: str, site: str) -> list[str]:
    (line,) = [x for x in md.splitlines() if x.startswith(f"| {variant} |") and f"| {site} |" in x]
    return [cell.strip() for cell in line.strip("|").split("|")]


def test_config_to_table_csv_and_raw_jsonl(ran: dict) -> None:
    assert len(ran["requests"]) == len(REPLIES)  # 가짜 LLM 답을 모두 썼다
    assert sorted(ran["csv"]) == [
        ("dom", "original"),
        ("dom", "seed1"),
        ("som", "original"),
        ("som", "seed1"),
    ]
    # 머리: 설정 · 커밋 · 모델 · 날짜
    md = ran["md"]
    assert "- 커밋: abc1234" in md
    assert "- 모델: test-model" in md
    assert "- 날짜: " in md
    assert '"name": "시험"' in md  # 설정 파일 전문
    row = ran["csv"][("dom", "original")]
    assert (row["config"], row["commit"], row["model"]) == ("시험", "abc1234", "test-model")
    assert {r["errors"] for r in ran["csv"].values()} == {"0"}
    # 원자료: Persona 실행 4개, step 로그는 행동 로그 명세 14칸 그대로 (그림은 저장하지 않는다)
    assert [p["run_id"] for p in ran["personas"]] == [1, 2, 3, 4]
    assert len(ran["steps"]) == 10
    for step in ran["steps"]:
        assert set(step) == SPEC_FIELDS
        assert step["observation"]["screenshot"] is None
    # LLM 사용량은 결과 폴더에만 남고 운영 기록에는 섞이지 않는다
    assert len(_jsonl(ran["out"] / "usage.jsonl")) == len(REPLIES)
    assert not ran["usage_log"].exists()


def test_variants_run_with_their_observation_mode(ran: dict) -> None:
    variant_of = {p["run_id"]: p["variant"] for p in ran["personas"]}
    modes = {(variant_of[s["run_id"]], s["observation"]["mode"]) for s in ran["steps"]}

    assert modes == {("dom", "dom"), ("som", "som")}


def test_success_steps_tokens_cost_and_json_rate(ran: dict) -> None:
    rows = ran["csv"]
    expected = {
        # (성공률, step, 입력 토큰, 출력 토큰, JSON 준수율)
        ("dom", "original"): (1.0, 2, 22, 14, 1.0),
        ("dom", "seed1"): (1.0, 3, 33, 21, 2 / 3),  # 깨진 JSON 은 형식 위반
        ("som", "original"): (0.0, 2, 22, 14, 1.0),  # scroll 뒤 done — 성공 URL 에 안 닿았다
        ("som", "seed1"): (1.0, 3, 22, 14, 1.0),  # 답이 없는 호출(HTTP 500)은 분모에서 뺀다
    }
    for key, (success, steps, tokens_in, tokens_out, json_rate) in expected.items():
        row = rows[key]
        assert float(row["success_rate"]) == success, key
        assert float(row["steps"]) == steps, key
        assert float(row["input_tokens"]) == tokens_in, key
        assert float(row["output_tokens"]) == tokens_out, key
        assert float(row["json_rate"]) == pytest.approx(json_rate, abs=1e-6), key
        # 비용: 답 하나 = 입력 11 × $1 + 출력 7 × $2 (100만 토큰당)
        calls = tokens_in / 11
        assert float(row["cost_usd"]) == pytest.approx(calls * 25 / 1_000_000), key
    # 표의 칸: 오류 · 성공률 · step · 입력 토큰 · 출력 토큰 · JSON 준수율
    cells = _md_row(ran["md"], "dom", "seed1")
    assert [cells[i] for i in (6, 7, 8, 10, 11, 13)] == ["0", "100%", "3.0", "33", "21", "67%"]


def test_recall_and_false_positives_only_when_files_given(ran: dict) -> None:
    md = ran["md"]

    # 결함 사본 + 정답 · 진단 파일: 심은 구현 4종 2개(NAV-L · TASK-L) 중 TASK-L 하나를 맞혔다
    assert _md_row(md, "dom", "seed1")[-2:] == ["50% (1/2)", "—"]
    # 원본 사본 + 진단 파일: 진단 2건이 모두 오탐
    assert _md_row(md, "dom", "original")[-2:] == ["—", "2"]
    # 진단 파일이 없으면 둘 다 —
    assert _md_row(md, "som", "seed1")[-2:] == ["—", "—"]
    assert _md_row(md, "som", "original")[-2:] == ["—", "—"]
    row = ran["csv"][("dom", "seed1")]
    assert (row["defects_found"], row["defects_injected"], row["recall"]) == ("1", "2", "0.5")
    assert ran["csv"][("som", "seed1")]["recall"] == ""


def test_bench_never_loads_the_db_module() -> None:
    # DB 설정 없이 돌고 DB 모듈(엔진)을 불러오지 않는다 — 벤치 회차가 dev DB 에 섞이지 않게.
    env = {k: v for k, v in os.environ.items() if k not in ("DB_URL", "LOG_DIR")}
    code = (
        "import sys, uxight_agent.bench, uxight_agent.bench_metrics; "
        "sys.exit('uxight_agent.db' in sys.modules)"
    )
    subprocess.run([sys.executable, "-c", code], env=env, check=True)


@pytest.mark.parametrize(
    "change",
    [
        lambda c: c["variants"]["dom"].update(guard="off"),  # 가드 스위치는 아직 자리만
        lambda c: c["variants"]["dom"].update(diagnosis="multi"),  # 다중 진단도 자리만
        lambda c: c["sites"][1].update(original=True),  # 정답 파일이 있는 원본 사본
        lambda c: c["sites"][0]["findings"].update(nope="findings-dom-original.json"),
        lambda c: c["personas"].append("P999"),
        lambda c: c["tasks"][0].update(success_url=f"{PAGE}?page=2"),  # / 로 시작하지 않는 경로
        lambda c: c["sites"][1].pop("answers"),  # 정답 파일 없이 진단 파일만 — 쓸 곳이 없다
    ],
    ids=[
        "guard-off",
        "diagnosis-multi",
        "original-with-answers",
        "findings-variant",
        "persona",
        "success-url",
        "findings-without-answers",
    ],
)
def test_bad_config_stops_before_any_browser(setup: dict, change) -> None:
    config = json.loads(setup["config"].read_text(encoding="utf-8"))
    change(config)
    write_json(setup["config"], config)
    argv = [str(setup["config"]), "--out", str(setup["out"]), "--serve", f"seed1={setup['site']}"]

    with pytest.raises(SystemExit) as stop:
        bench.main(argv, make_decider=lambda run_id: None)

    assert stop.value.code == 2
    assert not setup["out"].exists()


@pytest.mark.parametrize(
    "serve",
    [
        [],  # seed1 의 url 은 경로뿐인데 --serve 가 없다
        ["--serve", "seed1"],  # 폴더를 빠뜨렸다 — 지금 폴더를 띄우면 안 된다
        ["--serve", "seed1={site}", "--serve", "original={site}"],  # 주소 전체인 사이트를 띄움
    ],
    ids=["missing", "no-folder", "full-url-site"],
)
def test_serve_must_match_sites(setup: dict, serve: list[str]) -> None:
    argv = [str(setup["config"]), "--out", str(setup["out"])]
    argv += [x.format(site=setup["site"]) for x in serve]

    with pytest.raises(SystemExit):
        bench.main(argv, make_decider=lambda run_id: None)
    assert not setup["out"].exists()


def test_llm_settings_are_required_without_a_fake_decider(
    setup: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL"):
        monkeypatch.delenv(name, raising=False)
    argv = [str(setup["config"]), "--out", str(setup["out"]), "--serve", f"seed1={setup['site']}"]

    with pytest.raises(SystemExit):
        bench.main(argv)
    assert not setup["out"].exists()


class FakeDriver(Driver):
    """브라우저 없이 같은 화면만 낸다. 시작 실패 · 닫기 실패 · 닫기 멈춤을 고를 수 있다."""

    start_error: Exception | None = None
    close_error: Exception | None = None
    close_seconds = 0.0

    async def start(self, url: str) -> None:
        if self.start_error:
            raise self.start_error

    async def observe(self) -> Observation:
        return Observation(url="https://example.com/", title="t", dom="")

    async def act(self, action: Action) -> ActionResult:
        return ActionResult(ok=True)

    async def close(self) -> None:
        await asyncio.sleep(self.close_seconds)
        if self.close_error:
            raise self.close_error


SLOW, INNER_TIMEOUT = "slow", "inner-timeout"


class ScriptedDecider(Decider):
    def __init__(self, *replies) -> None:
        self._replies = list(replies)

    async def decide(self, persona, task, observation, history) -> Decision:
        reply = self._replies.pop(0)
        if reply == SLOW:
            await asyncio.sleep(10)
        if reply == INNER_TIMEOUT:  # LLM 호출 하나에 건 상한 — Persona 시간 상한과 다른 시간 초과
            await asyncio.wait_for(asyncio.sleep(10), 0.01)
        return reply


def decision(kind: str | None) -> Decision:
    action = Action(kind=kind, value="down" if kind == "scroll" else None) if kind else None
    code = None if action else "PARSE_FAILED"
    return Decision(action, error_code=code, prompt_tokens=11, completion_tokens=7, model="m")


JOB = bench.Job(
    run_id=1,
    variant="v",
    observation="dom",
    site="s",
    url="https://example.com/",
    hosts=frozenset({"example.com:443"}),
    task_no=1,
    task={"goal": "g", "success_rule": "r", "success_url": "https://example.com/goal"},
    repeat=1,
    persona={"persona_id": "P001", "name": "p", "profile": {}},
)


def limits(**values) -> bench.BenchConfig:
    return bench.BenchConfig.model_validate(
        {
            "name": "t",
            "personas_file": "p.json",
            "personas": ["P001"],
            "tasks": [{"goal": "g", "success_rule": "r", "success_url": "/goal"}],
            "sites": [{"name": "s", "url": "https://example.com/"}],
            "variants": {"v": {}},
            "max_steps": 3,
            "max_seconds": 5,
            **values,
        }
    )


@pytest.mark.parametrize(
    ("replies", "driver", "values", "expected"),
    [
        ([decision("scroll"), decision("done")], {}, {}, ("done", 2, None)),
        ([decision("scroll")] * 3, {}, {}, ("max_steps", 3, None)),
        ([decision(None)] * 3, {}, {}, ("fail", 3, None)),  # 행동 없는 step 3번 (운영 규칙)
        # 토큰 상한 20: step 마다 18 토큰 → 36 이 된 뒤 다음 step 전에 멈춘다
        ([decision("scroll")] * 3, {}, {"max_tokens": 20}, ("max_steps", 2, None)),
        ([SLOW], {}, {"max_seconds": 1}, ("timeout", 0, None)),
        ([INNER_TIMEOUT], {}, {}, ("fail", 0, "TimeoutError")),
        (
            [],
            {"start_error": RuntimeError("no browser")},
            {},
            ("fail", 0, "RuntimeError: no browser"),
        ),
        # 닫기가 실패하거나 멈춰도 정해진 결과를 덮지 않는다 (운영 Watcher 와 같다)
        ([decision("done")], {"close_error": RuntimeError("gone")}, {}, ("done", 1, None)),
        ([decision("done")], {"close_seconds": 60}, {}, ("done", 1, None)),
    ],
    ids=[
        "done",
        "max-steps",
        "no-action",
        "token-cap",
        "time-limit",
        "inner-timeout",
        "start-fails",
        "close-fails",
        "close-hangs",
    ],
)
def test_persona_run_ends_like_the_watcher(
    monkeypatch: pytest.MonkeyPatch, replies: list, driver: dict, values: dict, expected: tuple
) -> None:
    monkeypatch.setattr(bench, "BROWSER_CLOSE_TIMEOUT_SECONDS", 0.1)
    monkeypatch.setitem(bench.DRIVERS, "dom", type("Driver", (FakeDriver,), driver))
    run = bench.run_persona(JOB, ScriptedDecider(*replies), {}, limits(**values))

    record, steps = asyncio.run(asyncio.wait_for(run, 10))

    assert (record["outcome"], record["steps"], record["error"]) == expected
    assert len(steps) == record["steps"]
    # 단가표가 비었으니 step 이 하나라도 있으면 비용은 모른다(None)
    assert record["cost_usd"] == (None if steps else 0.0)


def test_matching_rule_start_values() -> None:
    nav_everywhere = {"catalog_id": "NAV-H", "page": "*"}
    task_on_page = {"catalog_id": "TASK-M", "page": "/kor/1104/subview.do"}

    # "*" 결함은 유형만 본다
    assert bench_metrics.matches(finding("navigation_confusion", "http://a/x"), nav_everywhere)
    assert not bench_metrics.matches(finding("task_failure", "http://a/x"), nav_everywhere)
    # 경로만 본다 — 호스트 · 쿼리 · 조각은 사본마다 다르다
    url = "https://copy.example/kor/1104/subview.do?x=1#top"
    assert bench_metrics.matches(finding("task_failure", url), task_on_page)
    assert not bench_metrics.matches(finding("task_failure", "https://c/kor/1/x.do"), task_on_page)


def test_recall_counts_implemented_kinds_once_per_defect() -> None:
    answers = {
        "injected": [
            {"catalog_id": "STEP-M", "page": "/a.do"},  # 한 결함이 두 곳에 걸렸다
            {"catalog_id": "STEP-M", "page": "/b.do"},
            {"catalog_id": "INT-L", "page": "/c.do"},
            {"catalog_id": "LABEL-L", "page": "/d.do"},  # 미구현 3종 — 세지 않는다
            {"catalog_id": "DST-FONT", "page": "/e.do"},  # 방해 요소 — 세지 않는다
        ]
    }
    findings = [
        finding("excessive_steps", "http://h/b.do"),
        finding("excessive_steps", "http://h/a.do"),
    ]

    assert bench_metrics.recall_counts(findings, answers) == (1, 2)
    assert bench_metrics.recall_counts([], answers) == (0, 2)


def test_serve_gives_do_pages_as_html_even_for_post(tmp_path: Path) -> None:
    (tmp_path / "kor").mkdir()
    (tmp_path / "kor" / "index.do").write_text("<p>홈</p>", encoding="utf-8")

    with bench.serve(tmp_path) as base:
        with urllib.request.urlopen(f"{base}/kor/index.do?x=1") as res:
            assert res.headers["Content-Type"].startswith("text/html")
            body = res.read()
        post = urllib.request.Request(f"{base}/kor/index.do", data=b"a=1")
        with urllib.request.urlopen(post) as res:
            assert res.status == 200 and res.read() == body


def test_serve_reads_post_body_before_answering(tmp_path: Path) -> None:
    # 본문을 읽지 않고 답한 뒤 닫으면 늦게 온 본문 때문에 연결이 끊긴다(RESET).
    # 학교 사본 홈은 공지 · 슬라이드를 POST 로 채운다. 연결이 끊기면 위젯이 가끔 비어
    # 사이트마다 관측이 달라진다.
    (tmp_path / "w.do").write_text("{}", encoding="utf-8")
    with bench.serve(tmp_path) as base:
        address = (urlsplit(base).hostname, urlsplit(base).port)
        with socket.create_connection(address, timeout=5) as sock:
            sock.sendall(b"POST /w.do HTTP/1.1\r\nHost: x\r\nContent-Length: 3\r\n\r\n")
            sock.settimeout(0.3)
            with pytest.raises(TimeoutError):  # 본문이 오기 전에는 답하지 않는다
                sock.recv(1)
            sock.settimeout(5)
            sock.sendall(b"a=1")
            assert sock.recv(1024).startswith(b"HTTP/1.0 200")


def test_persona_file_becomes_snapshot_shape() -> None:
    (p1, p50) = bench.load_personas(REPO_PERSONAS, ["P001", "P050"])

    assert p1["persona_id"] == "P001" and p50["persona_id"] == "P050"
    assert set(p1) == {"persona_id", "name", "profile"}
    assert isinstance(p1["profile"]["behavior"], list) and "device" in p1["profile"]
