"""성능 benchmark (GACA-179) — 같은 사본 · Task · Persona 로 변형을 돌려 지표 표 하나를 낸다.

    uv run python -m uxight_agent.bench <설정 파일> --out <폴더> [--serve 이름=폴더 ...]

- 운영과 같은 코드로 돈다: Persona 루프(PersonaAgent) · 드라이버(DomDriver · SomDriver) · 가드 ·
  LLM 판단기(LLMDecider) · step 로그 14칸과 판정 · 비용(watcher/step_rules).
- DB 없이 돈다. DB 모듈을 불러오지 않고 결과는 --out 폴더에만 쓴다. 벤치 회차가 dev DB 에 섞여
  운영자 화면에 보이지 않게 한다. 그래서 운영 Watcher 의 DB 일(취소 · 감사 로그 · 하루 예산)은 없다.
- 설정 파일(JSON) 모양은 BenchConfig 이다. 안의 상대 경로는 설정 파일이 있는 폴더 기준이다.
- --serve 이름=폴더: 로컬 폴더의 사본을 127.0.0.1 에 잠깐 띄우고, 그 이름의 사이트 주소로 쓴다.
- LLM 설정은 운영과 같은 env(LLM_BASE_URL · LLM_API_KEY · LLM_MODEL)다.
  사용량은 <out>/usage.jsonl 에 따로 남긴다.
- 변형의 guard 가 shadow 면 가드 그림자 모드로 돈다 (GACA-180). 가드 셋(도메인 · 파괴적 행동 ·
  지시문 표시)은 판단만 하고 막지 않으며, 판단은 shadow.jsonl 에 남긴다.
  - 그림자 모드는 막을 행동을 실제로 실행한다. 그래서 그림자 변형이 하나라도 있으면 모든 사이트가
    --serve 로 띄운 사본이어야 한다 (check_shadow_sites).
  - 드라이버의 요청 단계 차단은 주 창 · 새 창 이동만 끊는다. 실행된 클릭이 낸 하위 요청
    (fetch · 이미지 · beacon · ping) · iframe 이동 · WebSocket 은 밖에 닿을 수 있다. 그래서 그림자
    변형이 있는 benchmark 는 모든 변형에 엄격 요청 차단(드라이버 strict_requests)을 켠다.
    두 조건이 같은 조건에서 돌게 하려는 것이다. route 를 거치지 않는 연결(worker · 떠날 때의
    beacon · 추측 prefetch · WebRTC · QUIC)은 엄격 차단의 브라우저 설정(닫힌 프록시)이 막는다.
- 결과 (지표 정의는 bench_metrics 에 있다):
  - summary.md · summary.csv: 변형 × 사이트마다 한 행
  - personas.jsonl: Persona 실행 하나 = 한 줄
  - steps.jsonl: step 하나 = 한 줄 (행동 로그 명세 14칸)
  - shadow.jsonl: 그림자 변형에서 가드가 걸린 것 하나 = 한 줄 (guard_lines). 그림자 변형만 쓴다
"""

import argparse
import asyncio
import contextlib
import functools
import http.server
import json
import os
import subprocess
import threading
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Literal, Self
from urllib.parse import urljoin, urlsplit

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PositiveInt,
    field_validator,
    model_validator,
)

from . import bench_metrics
from .driver.base import Observation
from .driver.dom_driver import DomDriver
from .driver.som_driver import SomDriver
from .guard.domain import allowed_hosts
from .llm import LLMClient
from .persona.llm_decider import STEP_MAX_RETRIES, LLMDecider
from .persona.persona_agent import Decider, GuardMode, PersonaAgent, StepResult
from .persona.prompt import instruction_marks
from .usage_report import PriceTable, price_table
from .watcher.step_rules import (
    BLOCK_REASONS,
    action_log,
    persona_outcome,
    step_cost_usd,
    to_step_log,
)

# 관측 방식 → 드라이버. 이름은 드라이버의 mode(step 로그 observation.mode)와 같다.
DRIVERS: dict[str, type[DomDriver]] = {d.mode: d for d in (DomDriver, SomDriver)}

# 브라우저 닫기 상한(초). 운영 Watcher 와 같은 값이다 (run_orchestrator).
BROWSER_CLOSE_TIMEOUT_SECONDS = 5


class Task(BaseModel):
    model_config = ConfigDict(extra="forbid")

    goal: str
    success_rule: str
    success_url: str  # 사이트 기준 경로(/kor/3126/subview.do). 사이트마다 그 주소에 붙는다

    @field_validator("success_url")
    @classmethod
    def _path_only(cls, value: str) -> str:
        # 주소 전체를 쓰면 --serve 로 띄운 사이트와 호스트가 달라 성공률이 소리 없이 0% 가 된다.
        if not value.startswith("/"):
            raise ValueError("success_url 은 / 로 시작하는 사이트 기준 경로다")
        return value


class Site(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str  # 표에 쓰는 이름 (original · seedN)
    url: str  # 시작 URL. --serve 로 띄우는 사이트는 경로(/kor/index.do)만 쓴다
    allowed_domains: list[str] = []  # 회차의 허용 도메인과 같은 뜻. 시작 URL 의 호스트는 늘 허용
    original: bool = False  # 원본 사본(심은 결함 0). 여기서 나온 진단은 모두 오탐으로 센다
    answers: Path | None = None  # 결함 사본의 정답 파일
    findings: dict[str, Path] = {}  # 변형 이름 → 진단 결과 파일 (findings 표 행의 JSON 배열)


class Variant(BaseModel):
    """변형 하나가 바꾸는 값. 쓰지 않은 값은 운영 기본값이다."""

    model_config = ConfigDict(extra="forbid")

    observation: Literal["dom", "som"] = "dom"
    body_text: bool = True  # 끄면 관측에서 본문 글을 뺀다 — 본문 글(GACA-217)의 효과 비교
    # on = 집행(운영 값). shadow = 가드 셋을 판단만 하고 막지 않는다 (GACA-180)
    guard: GuardMode = "on"
    # 자리만 있다. 지금 코드에 스위치가 없어 운영 값만 받는다. 다중 진단은 GACA-181
    diagnosis: Literal["single"] = "single"


class BenchConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    personas_file: Path  # config/school_personas_50.json 모양
    personas: list[str] = Field(min_length=1)  # 돌릴 Persona id
    tasks: list[Task] = Field(min_length=1)
    sites: list[Site] = Field(min_length=1)
    variants: dict[str, Variant] = Field(min_length=1)  # 변형 이름 → 바꿀 값
    repeat: PositiveInt = 1  # Persona 하나가 Task 하나를 도는 횟수
    concurrency: PositiveInt = 1  # 동시에 도는 Persona(브라우저) 수
    # 한도. step · 시간은 운영 정책과 같은 뜻이다. 토큰은 Persona 실행 하나마다 센다
    # (운영은 회차 안 Persona 가 나눠 쓴다). 넘으면 운영처럼 max_steps 로 끝낸다.
    max_steps: PositiveInt
    max_seconds: PositiveInt
    max_tokens: PositiveInt | None = None

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        names = [s.name for s in self.sites]
        if len(set(names)) != len(names):
            raise ValueError("사이트 이름이 겹친다")
        if len(set(self.personas)) != len(self.personas):
            raise ValueError("Persona id 가 겹친다")
        for site in self.sites:
            if site.original and site.answers:
                raise ValueError(f"{site.name}: 원본 사본에는 정답 파일이 없다")
            if unknown := sorted(set(site.findings) - set(self.variants)):
                raise ValueError(f"{site.name}: 없는 변형의 진단 파일 {unknown}")
            if site.findings and not (site.original or site.answers):
                raise ValueError(f"{site.name}: 진단 파일은 원본 사본이나 정답 파일이 있어야 쓴다")
        return self

    @property
    def has_shadow(self) -> bool:
        """그림자 변형이 하나라도 있다 — 사본 검사와 엄격 요청 차단을 켠다 (GACA-180)."""
        return any(v.guard == "shadow" for v in self.variants.values())


@dataclass(frozen=True)
class Job:
    """Persona 실행 하나 — Persona 한 명이 Task 하나를 한 번 돈다."""

    run_id: int  # 벤치 안의 회차 번호(사이트 × Task × 반복 × 변형). DB 의 runs 와 상관없다
    variant: str
    observation: str
    site: str
    url: str
    hosts: frozenset[str]
    task_no: int
    task: dict  # 회차 스냅샷 모양. success_url 은 사이트 주소에 붙인 것
    repeat: int
    persona: dict
    body_text: bool = True
    guard: GuardMode = "on"


def load_config(path: Path) -> BenchConfig:
    """설정 파일을 읽는다. 상대 경로를 설정 파일 폴더 기준으로 바꾸고 파일이 있는지 본다."""
    config = BenchConfig.model_validate_json(path.read_text(encoding="utf-8"))

    def resolve(p: Path) -> Path:
        full = path.parent / p
        if not full.is_file():
            raise ValueError(f"파일이 없다: {full}")
        return full

    config.personas_file = resolve(config.personas_file)
    for site in config.sites:
        if site.answers:
            site.answers = resolve(site.answers)
        site.findings = {name: resolve(p) for name, p in site.findings.items()}
    return config


def load_personas(path: Path, ids: list[str]) -> list[dict]:
    """Persona 파일에서 고른 Persona 를 회차 스냅샷 모양 {persona_id, name, profile} 으로.

    id · 이름 밖의 속성은 모두 profile 에 넣는다. 프롬프트가 속성 이름을 그대로 쓴다.
    """
    by_id = {p["persona_id"]: p for p in json.loads(path.read_text(encoding="utf-8"))}
    if missing := [i for i in ids if i not in by_id]:
        raise ValueError(f"Persona 파일에 없는 id: {missing}")
    return [
        {
            "persona_id": i,
            "name": by_id[i]["name"],
            "profile": {k: v for k, v in by_id[i].items() if k not in ("persona_id", "name")},
        }
        for i in ids
    ]


class _CopyHandler(http.server.SimpleHTTPRequestHandler):
    """학교 사본을 VM 의 nginx 처럼 낸다. .do 는 HTML 로 내고, POST 에도 같은 파일을 준다.

    홈의 공지 · 슬라이드는 POST 로 채운다. 사본에 없는 경로는 404 다 (VM 은 안내 페이지를 준다).
    """

    extensions_map = {
        **http.server.SimpleHTTPRequestHandler.extensions_map,
        ".do": "text/html; charset=utf-8",
    }

    def do_POST(self) -> None:
        # 본문을 다 읽고 답한다. 읽지 않은 채 연결을 닫으면 브라우저는 연결 끊김(RESET)으로 받는다.
        self.rfile.read(int(self.headers.get("Content-Length") or 0))
        self.do_GET()

    def log_message(self, *args) -> None:
        pass


@contextlib.contextmanager
def serve(folder: Path) -> Iterator[str]:
    """folder 를 http://127.0.0.1:<빈 포트> 로 띄우고 그 주소를 준다. 나가면 내린다."""
    handler = functools.partial(_CopyHandler, directory=str(folder))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()


def site_urls(config: BenchConfig, served: dict[str, str]) -> dict[str, str]:
    """사이트마다 실제로 갈 시작 주소. --serve 로 띄운 사이트(served)는 그 사본 주소에 붙인다."""
    return {
        s.name: urljoin(served[s.name], s.url) if s.name in served else s.url for s in config.sites
    }


def check_shadow_sites(config: BenchConfig, served: dict[str, str], urls: dict[str, str]) -> None:
    """그림자 변형이 있으면 모든 사이트가 bench 가 띄운 사본인지 본다. 아니면 ValueError (GACA-180).

    그림자 모드는 가드가 막을 행동(파괴적 클릭 · 허용 밖 링크)을 실제로 실행한다. 그래서 사이트마다
    아래를 모두 지켜야 한다.
    1. --serve 로 띄운 사본이다(served 에 있다).
    2. 실제로 갈 시작 주소(urls)의 scheme · 호스트 · 포트가 그 사본 주소와 같다.
       'https:evil.example/x' 는 호스트가 비어 경로처럼 보이지만, urljoin 은 사본 주소를 버리고
       Chromium 은 https://evil.example 로 읽는다.
    3. allowed_domains 가 비었다. 사본 밖 주소를 허용하면 사본의 파괴적 링크가 그리로 간다.
    """
    if not config.has_shadow:
        return
    for site in config.sites:
        if site.name not in served:
            raise ValueError(f"{site.name}: 그림자 변형은 --serve 로 띄운 사본에서만 돈다")
        if urlsplit(urls[site.name])[:2] != urlsplit(served[site.name])[:2]:
            raise ValueError(f"{site.name}: 시작 주소가 --serve 사본 밖이다 ({site.url})")
        if site.allowed_domains:
            raise ValueError(f"{site.name}: 그림자 변형에서는 allowed_domains 를 쓰지 않는다")


def plan(config: BenchConfig, personas: list[dict], urls: dict[str, str]) -> list[Job]:
    """돌릴 Persona 실행 목록. 사이트 → Task → 반복 → 변형 → Persona 순서다.

    변형을 안쪽에 둬 같은 조건의 변형끼리 가까운 시각에 돈다. 그사이 LLM 지연이 바뀌어도
    변형 차이로 보이지 않게 한다.
    """
    jobs: list[Job] = []
    run_id = 0
    for site in config.sites:
        url = urls[site.name]
        hosts = allowed_hosts(url, site.allowed_domains)
        for task_no, task in enumerate(config.tasks, 1):
            snapshot = {
                "task_id": task_no,
                "goal": task.goal,
                "success_rule": task.success_rule,
                "success_url": urljoin(url, task.success_url),
            }
            for repeat in range(1, config.repeat + 1):
                for name, variant in config.variants.items():
                    run_id += 1
                    for persona in personas:
                        jobs.append(
                            Job(
                                run_id=run_id,
                                variant=name,
                                observation=variant.observation,
                                body_text=variant.body_text,
                                guard=variant.guard,
                                site=site.name,
                                url=url,
                                hosts=hosts,
                                task_no=task_no,
                                task=snapshot,
                                repeat=repeat,
                                persona=persona,
                            )
                        )
    return jobs


class _WithoutBodyText:
    """변형 body_text=false — 관측에서 본문 글만 뺀다. 나머지는 감싼 드라이버 그대로다."""

    def __init__(self, driver: DomDriver) -> None:
        self._driver = driver

    def __getattr__(self, name: str):
        return getattr(self._driver, name)

    async def observe(self) -> Observation:
        return replace(await self._driver.observe(), text="")


async def run_persona(
    job: Job,
    decider: Decider,
    prices: PriceTable,
    config: BenchConfig,
    shadow: list[dict] | None = None,
) -> tuple[dict, list[dict]]:
    """Persona 실행 하나. (Persona 기록, step 로그 줄들)을 돌려준다.

    운영 Watcher 의 Persona 하나(_drive_persona)와 같은 순서로 돈다. 브라우저를 띄우고 시간 상한을
    건 뒤 step 마다 토큰 한도 확인 → observe · decide · act → step 로그 · 비용 → 끝낼지 판정.
    브라우저 닫기도 운영과 같다. Persona 시간 상한 밖에서 닫고 닫기 상한을 따로 둔다.
    닫기가 실패해도 정해진 결과를 덮지 않는다.
    화면 그림은 저장하지 않는다 (step 로그의 screenshot 은 null).
    그림자 변형이고 shadow 를 주면 그림자 기록(guard_lines 줄)을 거기에 더한다 (GACA-180).
    decider 는 이 실행의 가드 모드(job.guard)로 만든 것이어야 한다.
    그림자 변형이 있는 benchmark 면 집행 변형도 엄격 요청 차단으로 돈다(두 조건을 같게).
    """
    persona_id = job.persona["persona_id"]
    steps: list[dict] = []
    guards: list[dict] = []  # 가드가 걸린 것 (guard_lines). 집행이면 막은 것이다
    cost: float | None = 0.0  # 이 실행의 LLM 비용(USD). 단가 없는 step 이 하나라도 있으면 None
    outcome, error, seconds = "max_steps", None, 0.0
    strict = config.has_shadow
    driver = DRIVERS[job.observation](allowed_hosts=job.hosts, strict_requests=strict)
    if not job.body_text:
        driver = _WithoutBodyText(driver)
    deadline = asyncio.timeout(config.max_seconds)
    try:
        async with deadline:
            await driver.start(job.url)
            agent = PersonaAgent(job.persona, job.task, driver, decider, job.hosts, job.guard)
            started, tokens = time.monotonic(), 0
            try:
                for step_no in range(1, config.max_steps + 1):
                    if config.max_tokens and tokens >= config.max_tokens:
                        break
                    step = await agent.step()
                    steps.append(
                        to_step_log(
                            job.run_id, persona_id, step_no, step, job.task, driver.mode, None
                        )
                    )
                    guards += guard_lines(job, step_no, step)
                    tokens += step.decision.prompt_tokens + step.decision.completion_tokens
                    step_cost = step_cost_usd(step.decision, prices)
                    cost = None if cost is None or step_cost is None else cost + step_cost
                    if ended := persona_outcome(agent.history):
                        outcome = ended
                        break
            finally:
                seconds = time.monotonic() - started
    except TimeoutError as e:
        # 시간 상한이 아닌 시간 초과(step 안의 상한)는 운영처럼 실행 오류(fail)다.
        outcome, error = ("timeout", None) if deadline.expired() else ("fail", _error_text(e))
    except Exception as e:  # 브라우저 실행 · 시작 URL 접근 실패 등 — 운영도 fail 로 끝낸다
        outcome, error = "fail", _error_text(e)
    finally:
        with contextlib.suppress(Exception):
            await asyncio.wait_for(driver.close(), BROWSER_CLOSE_TIMEOUT_SECONDS)
    if shadow is not None and job.guard == "shadow":
        shadow += guards
    record = {
        "run_id": job.run_id,
        "variant": job.variant,
        "site": job.site,
        "task": job.task_no,
        "repeat": job.repeat,
        "persona_id": persona_id,
        "model": next((s["model"] for s in steps if s["model"]), None),
        "outcome": outcome,
        "error": error,
        "seconds": round(seconds, 3),
        "cost_usd": cost,
        **bench_metrics.persona_measures(steps),
        **bench_metrics.guard_measures(
            guards, driver.blocked_requests, driver.blocked_subrequests if strict else None
        ),
    }
    return record, steps


def guard_lines(job: Job, step_no: int, step: StepResult) -> list[dict]:
    """이 step 에서 가드가 걸린 것. 하나가 shadow.jsonl 한 줄이다 (GACA-180).

    - 지시문 표시(page_text): 프롬프트 페이지 글에 붙인(그림자면 붙였을) 조각 수(marks)와 걸린
      패턴 이름(reason). 글 원문은 남기지 않는다. 관측 전 되돌린 step 은 LLM 을 부르지 않아 없다.
    - 행동 가드(domain · destructive): 집행이면 막은, 그림자면 막았을 결과. reason 은 집행이면
      step 로그 result.error 에 남는 문구이고, destination 은 계정 · 쿼리를 뺀 목적지다.
      http(s) 가 아닌 목적지는 둘 다 scheme 만 남긴다("data:"). data: · javascript: · mailto:
      주소에는 페이지 글 · 코드 · 메일 주소가 그대로 들어 있다. 집행 step 로그 문구는 그대로다.
    """
    base = {"run_id": job.run_id, "persona_id": job.persona["persona_id"], "step": step_no}
    action = action_log(step.action)
    lines = []
    if not step.observation.blocked:
        marks, patterns = instruction_marks(step.observation)
        if marks:
            lines.append(
                {
                    **base,
                    "guard": "page_text",
                    "reason": ",".join(patterns),
                    "action": action,
                    "destination": None,
                    "marks": marks,
                }
            )
    if (block := step.guard_block) is not None:
        destination, reason = block.destination, block.error
        scheme = urlsplit(destination or "").scheme
        if destination and scheme not in ("http", "https"):
            reason = reason.replace(destination, f"{scheme}:")
            destination = f"{scheme}:"
        lines.append(
            {
                **base,
                "guard": BLOCK_REASONS[block.error_code],
                "reason": reason,
                "action": action,
                "destination": destination,
                "marks": None,
            }
        )
    return lines


async def run_bench(
    config: BenchConfig,
    personas: list[dict],
    out: Path,
    make_decider: Callable[..., Decider],
    prices: PriceTable,
    serve_dirs: dict[str, Path],
) -> tuple[list[dict], list[dict]]:
    """모든 Persona 실행을 돌려 out 에 원자료를 쓴다.

    (표의 행들, Persona 기록들)을 돌려준다. 표의 한 행은 변형 × 사이트다.
    판단기는 make_decider(run_id) 로 만든다. 그림자 변형만 make_decider(run_id, guard="shadow") 다.
    """
    out.mkdir(parents=True, exist_ok=True)
    # 벤치 호출은 운영 사용량 기록(비용 리포트)과 섞지 않는다 (bakeoff 와 같다).
    usage_env = os.environ.get("LLM_USAGE_LOG")
    os.environ["LLM_USAGE_LOG"] = str(out / "usage.jsonl")
    try:
        with contextlib.ExitStack() as stack:
            served = {name: stack.enter_context(serve(d)) for name, d in serve_dirs.items()}
            # --serve 로 띄운 사이트의 url 은 경로다 (main 이 확인한다).
            urls = site_urls(config, served)
            # main 을 거치지 않고 불러도 그림자 변형은 사본에서만 돈다. 실제 주소로 여기서 본다.
            check_shadow_sites(config, served, urls)
            jobs = plan(config, personas, urls)
            records = await _run_jobs(jobs, config, make_decider, prices, out)
    finally:
        if usage_env is None:
            os.environ.pop("LLM_USAGE_LOG", None)
        else:
            os.environ["LLM_USAGE_LOG"] = usage_env
    rows = []
    for name, variant in config.variants.items():
        for site in config.sites:
            findings_file = site.findings.get(name)
            rows.append(
                bench_metrics.summarize(
                    name,
                    variant.model_dump(),
                    site.name,
                    [r for r in records if r["variant"] == name and r["site"] == site.name],
                    original=site.original,
                    findings=_read_json(findings_file) if findings_file else None,
                    answers=_read_json(site.answers) if site.answers else None,
                )
            )
    return rows, records


async def _run_jobs(
    jobs: list[Job],
    config: BenchConfig,
    make_decider: Callable[..., Decider],
    prices: PriceTable,
    out: Path,
) -> list[dict]:
    slots = asyncio.Semaphore(config.concurrency)
    records: list[dict] = []

    async def one(job: Job) -> None:
        shadow: list[dict] = []
        # 집행 변형은 예전처럼 make_decider(run_id) 로 만든다 — 시험 · 데모 판단기를 그대로 쓰게.
        mode = {"guard": job.guard} if job.guard == "shadow" else {}
        async with slots:
            decider = make_decider(job.run_id, **mode)
            record, steps = await run_persona(job, decider, prices, config, shadow)
        # 끝난 실행부터 바로 쓴다 — 도중에 멈춰도 그때까지의 원자료는 남는다.
        _append_jsonl(out / "personas.jsonl", [record])
        _append_jsonl(out / "steps.jsonl", steps)
        if job.guard == "shadow":
            _append_jsonl(out / "shadow.jsonl", shadow)
        records.append(record)
        print(
            f"[{len(records)}/{len(jobs)}] {job.variant} · {job.site} · Task {job.task_no} · "
            f"{record['persona_id']} → {record['outcome']} ({record['steps']} step, "
            f"{record['seconds']:.1f}s){' ' + record['error'] if record['error'] else ''}",
            flush=True,
        )

    await asyncio.gather(*(one(job) for job in jobs))
    return records


def render_summary(
    config: BenchConfig,
    config_text: str,
    serve_dirs: dict[str, Path],
    rows: list[dict],
    records: list[dict],
    meta: dict,
    prices: PriceTable,
) -> str:
    """summary.md — 머리(날짜 · 커밋 · 모델 · 조건 · 합계) + 표 + 설정 파일."""
    price = "{} (단가 입력 {:.2f} · 출력 {:.2f} · 캐시된 입력 {:.2f}, USD / 100만 토큰)"
    models = " · ".join(
        price.format(m, *prices[m]) if m in prices else f"{m} (단가표에 없음 — 비용 칸이 빈다)"
        for m in meta["models"]
    )
    costs = [r["cost_usd"] for r in records]
    total_cost = "—" if None in costs else f"${sum(costs):.4f}"
    errors = sum(1 for r in records if r["error"])
    variants = " / ".join(
        f"{name} = 관측 {v.observation} · 본문 {'on' if v.body_text else 'off'}"
        f" · 가드 {v.guard} · 진단 {v.diagnosis}"
        for name, v in config.variants.items()
    )
    sites = " / ".join(
        f"{s.name} = "
        + (f"--serve {serve_dirs[s.name].name}" if s.name in serve_dirs else s.url)
        + (" (원본 사본)" if s.original else " (정답 파일 있음)" if s.answers else "")
        for s in config.sites
    )
    lines = [
        f"# 성능 benchmark — {config.name}",
        "",
        f"- 날짜: {meta['date']} · 걸린 시간 {meta['elapsed']}",
        f"- 커밋: {meta['commit']}",
        f"- 모델: {models or '—'}",
        f"- 한도: step {config.max_steps} · 시간 {config.max_seconds}초 · 토큰 "
        f"{config.max_tokens or '없음'} · 반복 {config.repeat} · 동시 {config.concurrency}",
        f"- Persona {len(config.personas)}명 ({', '.join(config.personas)}) · "
        f"Task {len(config.tasks)}개",
        f"- 변형: {variants}",
        f"- 사이트: {sites}",
        f"- 합계: Persona 실행 {len(records)} · step {sum(r['steps'] for r in records)} · "
        f"비용 {total_cost} · 실행 오류 {errors}",
        "- 칸: 실행 = Persona 실행 수(Persona × Task × 반복). 오류 = 실행 오류로 끝난 실행 수"
        "(평균에도 들어간다). step · 시간 · 토큰 · 비용은 Persona 실행 하나의 평균. "
        "성공률 = 성공 URL 에 닿은 실행의 비율. 정의는 uxight_agent/bench_metrics.py",
        "",
        bench_metrics.render_md(rows),
        "",
        "- 가드 칸(행의 합계): 도메인 가드 · 파괴 가드 = 가드가 걸린 행동 수(가드 on 은 막은 수, "
        "shadow 는 막지 않고 기록한 수). 지시문 표시 = 프롬프트 페이지 글의 표시 조각 수"
        "(shadow 는 붙이지 않았다).",
        "- 요청 끊김 = 드라이버가 요청 단계에서 끊은 허용 밖 이동 요청 수(주 창 · 새 창). "
        "하위 요청 끊김 = 엄격 요청 차단이 route 에서 끊은 허용 밖 하위 요청 · iframe 이동 · "
        "WebSocket 수(닫힌 프록시가 막은 연결은 세지 못한다). "
        "엄격 차단은 그림자 변형이 있는 benchmark 에서만 모든 변형에 켜고, 아니면 '—'.",
        "- CuP = 성공했고 행동 가드(도메인 · 파괴)가 한 번도 걸리지 않은 실행의 비율. "
        "지시문 표시는 넣지 않는다 — 행동이 아니라 페이지 글에 붙는 것이다.",
        "",
        "## 설정 파일",
        "",
        "```json",
        config_text.strip(),
        "```",
        "",
    ]
    return "\n".join(lines)


def commit() -> str:
    """이 코드의 커밋. 컨테이너에는 git 이 없어 BENCH_COMMIT env 로 받는다."""
    if sha := os.environ.get("BENCH_COMMIT"):
        return sha
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=Path(__file__).parent,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return "?"
    return result.stdout.strip() or "?"


def main(argv: list[str] | None = None, make_decider: Callable[..., Decider] | None = None) -> int:
    """make_decider 를 주면 LLM 대신 그것을 쓴다 (시험 · 데모). 안 주면 운영과 같은 LLMDecider.

    make_decider(run_id) 로 부른다. 그림자 변형은 make_decider(run_id, guard="shadow") 다.
    """
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("config", type=Path, help="설정 파일 (JSON)")
    ap.add_argument("--out", type=Path, required=True, help="결과 폴더 (없거나 비어 있어야 한다)")
    ap.add_argument(
        "--serve",
        action="append",
        default=[],
        metavar="이름=폴더",
        help="로컬 폴더의 사본을 127.0.0.1 에 띄워 그 이름의 사이트 주소로 쓴다",
    )
    args = ap.parse_args(argv)

    # 브라우저를 띄우기 전에 입력을 모두 확인한다.
    try:
        config_text = args.config.read_text(encoding="utf-8")
        config = load_config(args.config)
        personas = load_personas(config.personas_file, config.personas)
        prices = price_table()
    except (OSError, ValueError) as e:
        ap.error(str(e))
    names = {s.name for s in config.sites}
    serve_dirs: dict[str, Path] = {}
    for value in args.serve:
        name, sep, folder = value.partition("=")
        # 폴더를 빠뜨리면 Path("") 가 지금 폴더라 엉뚱한 곳을 띄운다.
        if not (sep and folder and Path(folder).is_dir()) or name not in names:
            ap.error(f"--serve {value}: 설정에 있는 사이트 이름=있는 폴더 로 준다")
        serve_dirs[name] = Path(folder)
    for site in config.sites:
        if bool(urlsplit(site.url).netloc) == (site.name in serve_dirs):
            ap.error(
                f"{site.name}: --serve 로 띄우는 사이트는 url 에 경로만, 아니면 주소 전체를 쓴다"
            )
    # 그림자 변형의 사본 검사. run_bench 가 띄운 사본 주소로 다시 보지만, 브라우저를 띄우기 전에
    # 알리려고 여기서 먼저 본다. 사본 주소는 아직 모르니 포트 없는 자리 주소로 본다.
    placeholder = {name: "http://127.0.0.1" for name in serve_dirs}
    try:
        check_shadow_sites(config, placeholder, site_urls(config, placeholder))
    except ValueError as e:
        ap.error(str(e))
    if args.out.exists() and any(args.out.iterdir()):
        ap.error(f"--out {args.out} 이 비어 있지 않다")
    if make_decider is None:
        try:
            make_decider = functools.partial(LLMDecider, LLMClient(max_retries=STEP_MAX_RETRIES))
        except KeyError:
            ap.error("LLM 설정(LLM_BASE_URL · LLM_API_KEY · LLM_MODEL)이 없다")

    started = datetime.now().astimezone()
    clock = time.monotonic()
    rows, records = asyncio.run(
        run_bench(config, personas, args.out, make_decider, prices, serve_dirs)
    )
    elapsed = int(time.monotonic() - clock)
    models = sorted({r["model"] for r in records if r["model"]})
    meta = {
        "config": config.name,
        "commit": commit(),
        "model": ", ".join(models) or "—",
        "date": started.isoformat(timespec="seconds"),
    }
    summary = render_summary(
        config,
        config_text,
        serve_dirs,
        rows,
        records,
        {**meta, "models": models, "elapsed": f"{elapsed // 60}분 {elapsed % 60}초"},
        prices,
    )
    (args.out / "summary.md").write_text(summary, encoding="utf-8")
    (args.out / "summary.csv").write_text(bench_metrics.render_csv(rows, meta), encoding="utf-8")
    print(bench_metrics.render_md(rows))
    print(f"결과: {args.out}")
    return 0


def _error_text(e: BaseException) -> str:
    # 이름만으로는 원인을 가리지 못한다 (asyncio · Playwright 의 TimeoutError 등).
    # 메시지 첫 줄을 붙인다.
    first = str(e).splitlines()[0] if str(e) else ""
    return f"{type(e).__name__}: {first}"[:200] if first else type(e).__name__


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _append_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("a", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
