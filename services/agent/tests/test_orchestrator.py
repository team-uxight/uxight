"""Watcher 실행 통제 (GACA-110). 가짜 Driver · 가짜 저장소로 LLM · DB 없이 돈다.

동시 상한 · 시간 상한 · 취소 10초 · 정책 기본값 · 실패 정리 · heartbeat.
"""

import asyncio
import itertools
import json
import time
from types import SimpleNamespace

import pytest

from uxight_agent import usage_report
from uxight_agent.driver.base import ActionResult, Driver, Observation
from uxight_agent.llm import record_usage
from uxight_agent.persona.llm_decider import LLMDecider
from uxight_agent.persona.persona_agent import Decider, Decision
from uxight_agent.repositories.run_repository import RunSnapshot
from uxight_agent.schemas import Action
from uxight_agent.watcher import run_orchestrator as orchestrator_module
from uxight_agent.watcher.run_orchestrator import RunOrchestrator
from uxight_agent.watcher.step_log_writer import StepLogWriter

RUN_ID = 1
# 실제 감시 간격(2초)을 줄인 값. 취소 계약 10초 = 감시 5주기라, 테스트는 10주기 안에 멈추는지 본다.
POLL_SECONDS = 0.1
# 실제 초를 테스트 초로 줄이는 비율 — 감시 간격을 줄인 만큼. 다른 상수도 이 비율로 줄여 계약을 본다.
SCALE = POLL_SECONDS / orchestrator_module.CANCEL_POLL_SECONDS
HANG_SECONDS = 60  # 끝나지 않는 스텝 (LLM 응답이 오지 않는 상황)


class FakeRunRepository:
    """runs 한 행을 메모리에 둔다. 상태 전이 조건(running 일 때만)은 실제 SQL 과 같다."""

    def __init__(self) -> None:
        self.status = "running"
        self.error: str | None = None
        self.cancel_requested = False
        self.cancel_checks = 0
        self.heartbeats = 0
        self.daily_left: int | None = None  # 하루 예산 남은 토큰 (None = 예산 없음)

    def daily_tokens_left(self) -> int | None:
        return self.daily_left

    def _finish(self, status: str) -> None:
        if self.status == "running":
            self.status = status

    def mark_done(self, run_id: int, success_rate: float) -> None:
        self._finish("done")

    def mark_failed(self, run_id: int, error: str) -> None:
        if self.status == "running":
            self.error = error
        self._finish("failed")

    def fail_unfinished(self, run_id: int, error: str) -> None:
        self.mark_failed(run_id, error)  # 이 가짜의 회차는 수락 뒤 running 에서 시작한다

    def mark_cancelled(self, run_id: int) -> None:
        self._finish("cancelled")

    def refresh_progress(self, run_id: int) -> None:
        pass

    def is_cancel_requested(self, run_id: int) -> bool:
        self.cancel_checks += 1
        return self.cancel_requested

    def touch_heartbeat(self, run_id: int) -> None:
        self.heartbeats += 1


class FakeRunPersonaRepository:
    """run_personas 행을 메모리에 둔다. running 인 행만 종료 상태로 바뀐다."""

    def __init__(self) -> None:
        self.statuses: dict[int, str] = {}
        self.steps: dict[int, int] = {}
        self.tokens: dict[int, int] = {}
        # 비용은 실제 SQL 처럼 None 이면 건드리지 않고, 처음 값이 오면 0 에서 시작해 더한다.
        self.costs: dict[int, float | None] = {}
        self.cost_added: dict[int, list[float | None]] = {}  # step 마다 더한 값
        self.run_cost: float | None = None  # runs 칸. Persona 행에 더한 값을 그대로 더한다

    def get_statuses(self, run_id: int) -> dict[int, str]:
        return dict(self.statuses)

    def increment_steps(
        self, run_id: int, persona_id: int, tokens: int = 0, cost_usd: float | None = None
    ) -> None:
        self.steps[persona_id] = self.steps.get(persona_id, 0) + 1
        self.tokens[persona_id] = self.tokens.get(persona_id, 0) + tokens
        self.cost_added.setdefault(persona_id, []).append(cost_usd)
        if cost_usd is not None:
            self.costs[persona_id] = (self.costs.get(persona_id) or 0.0) + cost_usd
            self.run_cost = (self.run_cost or 0.0) + cost_usd

    def mark_finished(self, run_id: int, persona_id: int, status: str) -> None:
        if self.statuses[persona_id] == "running":
            self.statuses[persona_id] = status


class FakeAuditLogRepository:
    def __init__(self) -> None:
        self.rows: list[tuple[int, int, dict]] = []
        self.limits: list[tuple[int, int, dict]] = []

    def add_blocked_action(self, run_id: int, persona_id: int, detail: dict) -> None:
        self.rows.append((run_id, persona_id, detail))

    def add_limit_reached(self, run_id: int, persona_id: int, detail: dict) -> None:
        self.limits.append((run_id, persona_id, detail))


class Browsers:
    """가짜 브라우저 집계 — 띄운 수 · 지금 열린 수 · 동시에 열린 최대 수 · 닫기를 부른 수."""

    def __init__(self) -> None:
        self.started = 0
        self.open = 0
        self.peak = 0
        self.closed = 0  # close() 를 부른 수. 띄우지 못한 브라우저도 센다
        self.start_seconds = 0.0  # 브라우저를 띄우는 데 걸리는 시간
        self.start_error: Exception | None = None  # 띄우다 낼 예외 (실행 파일 없음 등)
        self.close_seconds = 0.0  # 브라우저를 닫는 데 걸리는 시간
        self.close_error: Exception | None = None  # 닫은 뒤 낼 예외 (드라이버 연결 끊김 등)


def fake_driver_class(browsers: Browsers) -> type[Driver]:
    class FakeDriver(Driver):
        def __init__(self, allowed_hosts: frozenset[str] = frozenset()) -> None:
            super().__init__(allowed_hosts)
            self._started = False

        async def start(self, url: str) -> None:
            if browsers.start_seconds:
                await asyncio.sleep(browsers.start_seconds)
            if browsers.start_error:
                raise browsers.start_error
            self._started = True
            browsers.started += 1
            browsers.open += 1
            browsers.peak = max(browsers.peak, browsers.open)

        async def observe(self) -> Observation:
            return Observation(url="https://example.com", title="t", dom="")

        async def act(self, action: Action) -> ActionResult:
            return ActionResult(ok=True)

        async def close(self) -> None:
            browsers.closed += 1
            await asyncio.sleep(browsers.close_seconds)
            if self._started:
                browsers.open -= 1
            if browsers.close_error:
                raise browsers.close_error

    return FakeDriver


class SleepyDecider(Decider):
    """LLM 대역. 페르소나의 step_seconds 만큼 걸리고 scroll 만 낸다 (done 을 내지 않는다)."""

    async def decide(self, persona, task, observation, history) -> Decision:
        await asyncio.sleep(persona["step_seconds"])
        return Decision(Action(kind="scroll", value="down"))


class InnerTimeoutDecider(Decider):
    """LLM 호출 하나에 건 상한(asyncio.wait_for)이 먼저 끊긴다 — 시간 상한과는 다른 시간 초과."""

    async def decide(self, persona, task, observation, history) -> Decision:
        await asyncio.wait_for(asyncio.sleep(HANG_SECONDS), 0.01)
        return Decision(Action(kind="scroll", value="down"))


@pytest.fixture
def fakes(monkeypatch: pytest.MonkeyPatch, tmp_path) -> SimpleNamespace:
    browsers = Browsers()
    runs = FakeRunRepository()
    personas = FakeRunPersonaRepository()
    monkeypatch.delenv("LLM_PRICES", raising=False)  # 단가표는 코드의 기본표로
    monkeypatch.setattr(orchestrator_module, "DomDriver", fake_driver_class(browsers))
    use_decider(monkeypatch, SleepyDecider())
    monkeypatch.setattr(orchestrator_module, "step_log_writer", StepLogWriter(str(tmp_path)))
    monkeypatch.setattr(orchestrator_module, "run_repository", runs)
    monkeypatch.setattr(orchestrator_module, "run_persona_repository", personas)
    audits = FakeAuditLogRepository()
    monkeypatch.setattr(orchestrator_module, "audit_log_repository", audits)
    monkeypatch.setattr(orchestrator_module, "CANCEL_POLL_SECONDS", POLL_SECONDS)
    set_global_cap(monkeypatch, 3)
    return SimpleNamespace(
        browsers=browsers, runs=runs, personas=personas, audits=audits, log_dir=tmp_path
    )


def use_decider(monkeypatch: pytest.MonkeyPatch, decider: Decider) -> None:
    monkeypatch.setattr(orchestrator_module, "make_decider", lambda run_id: decider)


def set_global_cap(monkeypatch: pytest.MonkeyPatch, cap: int) -> None:
    # 전역 세마포어는 처음 기다린 이벤트 루프에 묶이므로 테스트마다 새로 만든다.
    monkeypatch.setattr(orchestrator_module, "persona_slots", asyncio.Semaphore(cap))


def free_global_slots() -> int:
    # 전역 자리는 모든 회차가 나눠 쓰므로, 어느 경로로 끝나든 쥔 자리를 돌려줘야 한다.
    return orchestrator_module.persona_slots._value


def persona(persona_id: int, step_seconds: float = 0.01) -> dict:
    return {
        "persona_id": persona_id,
        "name": f"p{persona_id}",
        "profile": {},
        "step_seconds": step_seconds,
    }


def snapshot(personas: list[dict], **policy) -> RunSnapshot:
    return RunSnapshot(
        target_url="https://example.com",
        allowed_domains=["example.com"],
        task={"task_id": 1, "goal": "g"},
        personas=personas,
        policy=policy,
    )


async def run(
    fakes: SimpleNamespace,
    run_id: int,
    snap: RunSnapshot,
    orchestrator: RunOrchestrator | None = None,
) -> None:
    # try_accept_and_start 가 만든 running 행에서 시작한다.
    fakes.personas.statuses.update({p["persona_id"]: "running" for p in snap.personas})
    await asyncio.wait_for(
        (orchestrator or RunOrchestrator()).run_personas(run_id, snap), timeout=5
    )


@pytest.mark.parametrize(
    ("global_cap", "policy"),
    [(2, {"max_steps": 3}), (3, {"max_steps": 3, "persona_concurrency": 2})],
    ids=["global-cap", "persona-concurrency"],
)
def test_at_most_two_personas_run_at_once(
    fakes: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, global_cap: int, policy: dict
) -> None:
    set_global_cap(monkeypatch, global_cap)
    snap = snapshot([persona(1, 0.02), persona(2, 0.02), persona(3, 0.02)], **policy)

    asyncio.run(run(fakes, RUN_ID, snap))

    assert fakes.browsers.peak == 2
    assert fakes.browsers.started == 3
    assert fakes.personas.statuses == {1: "max_steps", 2: "max_steps", 3: "max_steps"}
    assert fakes.runs.status == "done"


def test_global_cap_is_shared_across_runs(
    fakes: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    # 회차마다 세마포어를 만들던 때는 두 회차가 2명씩, 동시에 4개가 떴다.
    set_global_cap(monkeypatch, 2)
    first = snapshot([persona(1, 0.02), persona(2, 0.02)], max_steps=3)
    second = snapshot([persona(3, 0.02), persona(4, 0.02)], max_steps=3)

    async def both() -> None:
        await asyncio.gather(run(fakes, 1, first), run(fakes, 2, second))

    asyncio.run(both())

    assert fakes.browsers.peak == 2
    assert fakes.browsers.started == 4


def test_persona_over_max_seconds_times_out(fakes: SimpleNamespace) -> None:
    snap = snapshot([persona(1), persona(2, HANG_SECONDS)], max_steps=3, max_seconds=0.5)

    asyncio.run(run(fakes, RUN_ID, snap))

    assert fakes.personas.statuses == {1: "max_steps", 2: "timeout"}
    assert fakes.runs.status == "done"  # 일부 시간 초과는 회차 실패가 아니다
    assert fakes.browsers.open == 0  # 시간 상한에 걸린 브라우저도 닫혔다
    assert free_global_slots() == 3


def test_timeout_inside_step_is_fail_not_max_seconds(
    fakes: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    # 스텝 안에서 난 내장 TimeoutError 는 실행 오류다. 시간 상한(timeout)으로 세면
    # 모두 실패한 회차가 failed 가 아니라 done(성공률 0%)으로 보인다.
    use_decider(monkeypatch, InnerTimeoutDecider())
    snap = snapshot([persona(1), persona(2)], max_steps=3, max_seconds=HANG_SECONDS)

    asyncio.run(run(fakes, RUN_ID, snap))

    assert fakes.personas.statuses == {1: "fail", 2: "fail"}
    assert fakes.runs.status == "failed"
    assert fakes.browsers.open == 0
    assert free_global_slots() == 3


def test_browser_close_is_outside_max_seconds(fakes: SimpleNamespace) -> None:
    # 스텝은 상한 안에 끝났고 닫는 데 상한을 넘겨 걸린다 — 닫기가 끊기면 브라우저가 남는다.
    fakes.browsers.close_seconds = 0.5
    snap = snapshot([persona(1, 0)], max_steps=1, max_seconds=0.2)

    asyncio.run(run(fakes, RUN_ID, snap))

    assert fakes.personas.statuses == {1: "max_steps"}
    assert fakes.browsers.open == 0


@pytest.mark.parametrize(
    ("step_seconds", "outcome", "run_status"),
    [(0, "max_steps", "done"), (HANG_SECONDS, "timeout", "done")],
    ids=["after-steps", "after-max-seconds"],
)
def test_hung_browser_close_does_not_block_result(
    fakes: SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
    step_seconds: float,
    outcome: str,
    run_status: str,
) -> None:
    # 닫기가 끝나지 않는다 — 닫기 상한 뒤 진행해 결과를 기록하고 자리를 돌려준다.
    # 시간 상한에 걸린 뒤라도 닫기 상한이 페르소나 결과(timeout)를 바꾸지 않는다.
    monkeypatch.setattr(orchestrator_module, "BROWSER_CLOSE_TIMEOUT_SECONDS", 0.2)
    fakes.browsers.close_seconds = HANG_SECONDS
    snap = snapshot([persona(1, step_seconds)], max_steps=1, max_seconds=0.2)

    asyncio.run(run(fakes, RUN_ID, snap))

    assert fakes.personas.statuses == {1: outcome}
    assert fakes.runs.status == run_status
    assert free_global_slots() == 3


@pytest.mark.parametrize(
    ("step_seconds", "max_seconds", "cancel", "outcome", "run_status"),
    [
        (0, HANG_SECONDS, False, "max_steps", "done"),
        (HANG_SECONDS, 0.2, False, "timeout", "done"),
        (HANG_SECONDS, HANG_SECONDS, True, "cancelled", "cancelled"),
    ],
    ids=["after-steps", "after-max-seconds", "after-cancel"],
)
def test_browser_close_error_does_not_change_result(
    fakes: SimpleNamespace,
    step_seconds: float,
    max_seconds: float,
    cancel: bool,
    outcome: str,
    run_status: str,
) -> None:
    # 닫기가 시간 초과가 아닌 예외를 내도 이미 정해진 페르소나 결과를 덮지 않는다.
    # 덮이면 셋 다 fail · failed 가 된다 — 취소한 회차도 '실패' 로 보인다.
    fakes.browsers.close_error = RuntimeError("Connection closed while reading from the driver")
    snap = snapshot([persona(1, step_seconds)], max_steps=1, max_seconds=max_seconds)

    async def run_and_cancel() -> None:
        task = asyncio.create_task(run(fakes, RUN_ID, snap))
        if cancel:
            await asyncio.sleep(POLL_SECONDS * 2)
            fakes.runs.cancel_requested = True
        await task

    asyncio.run(run_and_cancel())

    assert fakes.personas.statuses == {1: outcome}
    assert fakes.runs.status == run_status
    assert fakes.browsers.open == 0
    assert free_global_slots() == 3


def test_browser_start_failure_closes_once_and_fails_persona(fakes: SimpleNamespace) -> None:
    # 브라우저를 띄우지 못한다 — 예외가 올라가도 닫기를 한 번 부르고 자리를 돌려준다.
    fakes.browsers.start_error = RuntimeError("Executable doesn't exist at /ms-playwright/chromium")
    snap = snapshot([persona(1)], max_steps=3)

    asyncio.run(run(fakes, RUN_ID, snap))

    assert fakes.personas.statuses == {1: "fail"}
    assert fakes.runs.status == "failed"
    assert fakes.browsers.closed == 1
    assert free_global_slots() == 3


def test_cancel_during_browser_start_closes_once(fakes: SimpleNamespace) -> None:
    # 브라우저를 띄우는 중 취소 요청이 온다 — 띄우기를 멈추고 닫기를 한 번 부르고 자리를 돌려준다.
    fakes.browsers.start_seconds = HANG_SECONDS
    snap = snapshot([persona(1)], max_steps=3, max_seconds=HANG_SECONDS)

    async def cancel_midway() -> float:
        task = asyncio.create_task(run(fakes, RUN_ID, snap))
        await asyncio.sleep(POLL_SECONDS * 2)
        fakes.runs.cancel_requested = True
        requested_at = time.monotonic()
        await task
        return time.monotonic() - requested_at

    elapsed = asyncio.run(cancel_midway())

    assert elapsed < POLL_SECONDS * 10
    assert fakes.personas.statuses == {1: "cancelled"}
    assert fakes.runs.status == "cancelled"
    assert fakes.browsers.started == 0  # 띄우기를 끝내지 못했다
    assert fakes.browsers.closed == 1
    assert free_global_slots() == 3


@pytest.mark.parametrize(
    ("persona_statuses", "run_status", "error"),
    [
        ({1: "max_steps", 2: "max_steps", 3: "max_steps", 4: "timeout"}, "done", None),
        ({1: "done", 2: "fail"}, "done", None),
        ({1: "fail", 2: "fail"}, "failed", "실패한 페르소나: 1(fail), 2(fail)"),
        ({1: "timeout", 2: "timeout"}, "done", None),
        ({1: "done", 2: "fail", 3: "cancelled"}, "cancelled", None),
    ],
    ids=["some-timeout", "done-and-fail", "all-fail", "all-timeout", "with-cancelled"],
)
def test_run_status_from_persona_statuses(
    fakes: SimpleNamespace,
    persona_statuses: dict[int, str],
    run_status: str,
    error: str | None,
) -> None:
    # Persona 일부가 fail · timeout 이어도 회차는 실패가 아니다 (architecture §3.3, PM 결정 10/13).
    # 취소가 섞이면 cancelled, 모두 fail 이면 failed, 그 밖은 done.
    fakes.personas.statuses.update(persona_statuses)

    RunOrchestrator()._finish_run(RUN_ID)

    assert fakes.runs.status == run_status
    assert fakes.runs.error == error


@pytest.mark.parametrize(
    ("slots_held_by_other_runs", "persona_concurrency", "started"),
    [(0, None, 2), (2, None, 0), (0, 1, 1)],
    ids=["running", "waiting-for-slot", "waiting-for-run-slot"],
)
def test_cancel_stops_all_personas_quickly(
    fakes: SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
    slots_held_by_other_runs: int,
    persona_concurrency: int | None,
    started: int,
) -> None:
    # 전역 상한 2 · 페르소나 3명. running: 2명은 스텝 중 · 1명은 대기.
    # waiting-for-slot: 다른 회차가 전역 자리를 다 쥐고 있어 3명 모두 대기.
    # waiting-for-run-slot: 회차 안 상한 1 — 1명은 스텝 중, 2명은 회차 자리를 기다린다.
    set_global_cap(monkeypatch, 2)
    snap = snapshot(
        [persona(1, HANG_SECONDS), persona(2, HANG_SECONDS), persona(3, HANG_SECONDS)],
        max_steps=3,
        max_seconds=HANG_SECONDS,
        persona_concurrency=persona_concurrency,
    )

    async def cancel_midway() -> float:
        for _ in range(slots_held_by_other_runs):
            await orchestrator_module.persona_slots.acquire()
        task = asyncio.create_task(run(fakes, RUN_ID, snap))
        await asyncio.sleep(POLL_SECONDS * 2)
        fakes.runs.cancel_requested = True
        requested_at = time.monotonic()
        await task
        return time.monotonic() - requested_at

    elapsed = asyncio.run(cancel_midway())

    assert elapsed < POLL_SECONDS * 10
    assert fakes.personas.statuses == {1: "cancelled", 2: "cancelled", 3: "cancelled"}
    assert fakes.runs.status == "cancelled"
    assert fakes.browsers.open == 0
    assert fakes.browsers.started == started
    assert free_global_slots() == 2 - slots_held_by_other_runs


def test_cancel_with_hung_browser_close_finishes_within_10_seconds(
    fakes: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    # 닫기가 끝나지 않아도 취소 요청부터 종료 기록까지 10초 안 — 감시 한 주기 + 닫기 상한.
    # 실제 닫기 상한을 감시 간격과 같은 비율로 줄인다. 상한이 10초 계약을 넘기면 실패한다.
    close_timeout = orchestrator_module.BROWSER_CLOSE_TIMEOUT_SECONDS * SCALE
    monkeypatch.setattr(orchestrator_module, "BROWSER_CLOSE_TIMEOUT_SECONDS", close_timeout)
    fakes.browsers.close_seconds = HANG_SECONDS
    snap = snapshot(
        [persona(1, HANG_SECONDS), persona(2, HANG_SECONDS)],
        max_steps=3,
        max_seconds=HANG_SECONDS,
    )

    async def cancel_midway() -> float:
        task = asyncio.create_task(run(fakes, RUN_ID, snap))
        await asyncio.sleep(POLL_SECONDS * 2)
        fakes.runs.cancel_requested = True
        requested_at = time.monotonic()
        await task
        return time.monotonic() - requested_at

    elapsed = asyncio.run(cancel_midway())

    assert elapsed < 10 * SCALE
    assert fakes.personas.statuses == {1: "cancelled", 2: "cancelled"}
    assert fakes.runs.status == "cancelled"
    assert free_global_slots() == 3


def test_missing_policy_values_fall_back_to_defaults(
    fakes: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Spring 은 null 인 정책 항목을 스냅샷에서 뺀다 — 시작 전 실패가 아니라 기본값으로 돈다.
    monkeypatch.setattr(orchestrator_module, "DEFAULT_MAX_SECONDS", 1)
    snap = snapshot([persona(1, 0), persona(2, HANG_SECONDS)])

    asyncio.run(run(fakes, RUN_ID, snap))

    assert fakes.personas.steps[1] == orchestrator_module.DEFAULT_MAX_STEPS
    assert fakes.personas.statuses == {1: "max_steps", 2: "timeout"}


def test_exception_during_run_does_not_leave_run_running(fakes: SimpleNamespace) -> None:
    # 첫 종료 기록이 DB 오류로 실패한다 — 그 페르소나는 running 으로 남는다.
    mark_finished = fakes.personas.mark_finished
    calls = []

    def flaky_mark_finished(run_id: int, persona_id: int, status: str) -> None:
        calls.append(persona_id)
        if len(calls) == 1:
            raise RuntimeError("db down")
        mark_finished(run_id, persona_id, status)

    fakes.personas.mark_finished = flaky_mark_finished
    snap = snapshot([persona(1), persona(2)], max_steps=3)

    asyncio.run(run(fakes, RUN_ID, snap))

    assert fakes.runs.status == "failed"
    assert fakes.runs.error == "실행 오류로 중단: RuntimeError"
    assert "running" not in fakes.personas.statuses.values()
    assert free_global_slots() == 3


def test_progress_refresh_error_does_not_fail_run(fakes: SimpleNamespace) -> None:
    # 진행률 갱신이 DB 오류로 한 번 실패해도 회차는 실패가 아니다. 마지막 페르소나의 갱신이
    # 실패하는 경우라, 회차를 마감할 때 다시 세어 맞춰야 진행률이 3 이 된다.
    progress: list[int] = []
    failures: list[int] = []

    def refresh_fails_once_at_three(run_id: int) -> None:
        count = sum(s in ("done", "max_steps") for s in fakes.personas.statuses.values())
        if count == 3 and not failures:
            failures.append(count)
            raise RuntimeError("db down")
        progress.append(count)

    fakes.runs.refresh_progress = refresh_fails_once_at_three
    snap = snapshot([persona(1), persona(2), persona(3)], max_steps=2)

    asyncio.run(run(fakes, RUN_ID, snap))

    assert fakes.personas.statuses == {1: "max_steps", 2: "max_steps", 3: "max_steps"}
    assert fakes.runs.status == "done"
    assert fakes.runs.error is None
    assert failures == [3]
    assert progress == [1, 2, 3]


def test_heartbeat_written_every_watch_cycle(fakes: SimpleNamespace) -> None:
    runs = fakes.runs
    original = runs.is_cancel_requested

    def cancel_on_third_check(run_id: int) -> bool:
        runs.cancel_requested = runs.cancel_checks == 2  # 세 번째 확인에서 취소 요청이 보인다
        return original(run_id)

    runs.is_cancel_requested = cancel_on_third_check

    async def watch() -> asyncio.Event:
        cancel_event = asyncio.Event()
        await asyncio.wait_for(RunOrchestrator()._watch_cancel(RUN_ID, cancel_event), timeout=5)
        return cancel_event

    assert asyncio.run(watch()).is_set()
    assert runs.cancel_checks == 3
    assert runs.heartbeats == 3


class ScriptedDecider(Decider):
    """정해 둔 Decision 을 차례로 낸다. 다 쓰면 scroll 을 낸다."""

    def __init__(self, *decisions: Decision) -> None:
        self.decisions = list(decisions)

    async def decide(self, persona, task, observation, history) -> Decision:
        if self.decisions:
            return self.decisions.pop(0)
        return Decision(Action(kind="scroll", value="down"))


def parse_failure(code: str = "PARSE_FAILED") -> Decision:
    return Decision(None, error_code=code, error="Action JSON parsing failed")


def test_three_consecutive_steps_without_action_fail_persona(
    fakes: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    # 성공한 step 이 끼면 다시 센다. 2 + (성공 1) + 3 → 6번째 step 에서 실패로 끝난다.
    use_decider(
        monkeypatch,
        ScriptedDecider(
            parse_failure(),
            parse_failure("INVALID_ACTION"),
            Decision(Action(kind="scroll", value="down")),
            parse_failure(),
            parse_failure("LLM_REQUEST_FAILED"),  # LLM 호출 실패도 센다 (키 만료 등)
            parse_failure("LLM_REQUEST_TIMEOUT"),
        ),
    )
    snap = snapshot([persona(1)], max_steps=20)

    asyncio.run(run(fakes, RUN_ID, snap))

    assert fakes.personas.statuses == {1: "fail"}
    assert fakes.personas.steps[1] == 6


def test_outside_link_click_is_blocked_logged_and_audited(
    fakes: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    acted: list[Action] = []

    class LinkPageDriver(Driver):
        async def start(self, url: str) -> None:
            pass

        async def observe(self) -> Observation:
            return Observation(
                url="https://example.com/",
                title="t",
                dom='[1] <a href="https://evil.example/"> "밖"',
                element_map={1: {"tag": "a", "url": "https://evil.example/"}},
            )

        async def act(self, action: Action) -> ActionResult:
            acted.append(action)
            return ActionResult(ok=True)

        async def close(self) -> None:
            pass

    monkeypatch.setattr(orchestrator_module, "DomDriver", LinkPageDriver)
    use_decider(
        monkeypatch,
        ScriptedDecider(
            Decision(Action(kind="click", element_id=1)), Decision(Action(kind="done"))
        ),
    )

    asyncio.run(run(fakes, RUN_ID, snapshot([persona(1)], max_steps=5)))

    assert acted == [Action(kind="done")]  # 차단된 click 은 브라우저에 가지 않았다
    assert fakes.personas.statuses == {1: "done"}
    ((run_id, persona_id, detail),) = fakes.audits.rows
    assert (run_id, persona_id) == (RUN_ID, 1)
    assert detail["reason"] == "domain"
    assert detail["step"] == 1
    assert detail["destination"] == "https://evil.example/"
    assert isinstance(detail, dict)


def test_destructive_click_is_blocked_and_audited(
    fakes: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    acted: list[Action] = []

    class ButtonPageDriver(Driver):
        async def start(self, url: str) -> None:
            pass

        async def observe(self) -> Observation:
            element = {"tag": "button", "type": "button", "text": "회원 탈퇴"}
            return Observation(
                url="https://example.com/", title="t", dom="", element_map={1: element}
            )

        async def act(self, action: Action) -> ActionResult:
            acted.append(action)
            return ActionResult(ok=True)

        async def close(self) -> None:
            pass

    monkeypatch.setattr(orchestrator_module, "DomDriver", ButtonPageDriver)
    use_decider(
        monkeypatch,
        ScriptedDecider(
            Decision(Action(kind="click", element_id=1)), Decision(Action(kind="done"))
        ),
    )

    asyncio.run(run(fakes, RUN_ID, snapshot([persona(1)], max_steps=5)))

    assert acted == [Action(kind="done")]
    ((_, _, detail),) = fakes.audits.rows
    assert detail["reason"] == "destructive"
    assert "탈퇴" in detail["error"]


def test_page_returned_before_observation_is_logged_and_audited(
    fakes: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    # 첫 관측 전에 주 창이 늦게 허용 밖으로 가 있어 드라이버가 되돌렸다 (GACA-224).
    decided: list[Observation] = []

    class LateRedirectDriver(Driver):
        observes = 0

        async def start(self, url: str) -> None:
            pass

        async def observe(self) -> Observation:
            self.observes += 1
            blocked = "https://evil.example/" if self.observes == 1 else None
            return Observation(url="https://example.com/", title="t", dom="", blocked=blocked)

        async def act(self, action: Action) -> ActionResult:
            return ActionResult(ok=True)

        async def close(self) -> None:
            pass

    class DoneDecider(Decider):
        async def decide(self, persona, task, observation, history) -> Decision:
            decided.append(observation)
            return Decision(Action(kind="done"))

    monkeypatch.setattr(orchestrator_module, "DomDriver", LateRedirectDriver)
    use_decider(monkeypatch, DoneDecider())

    asyncio.run(run(fakes, RUN_ID, snapshot([persona(1)], max_steps=5)))

    assert fakes.personas.statuses == {1: "done"}
    assert len(decided) == 1  # 되돌린 step 은 LLM 을 부르지 않았다
    lines = (persona_folder(fakes) / "steps.jsonl").read_text(encoding="utf-8").splitlines()
    first = json.loads(lines[0])
    assert set(first["result"]) == {"ok", "url_after", "error", "error_code"}  # late 는 안 쓴다
    assert first["action"] is None
    assert first["result"]["error_code"] == "DOMAIN_BLOCKED"
    assert first["blocked"] == {"is": True, "reason": "domain"}
    ((_, _, detail),) = fakes.audits.rows
    assert detail["step"] == 1
    assert detail["reason"] == "domain"
    assert detail["destination"] == "https://evil.example/"
    assert detail["action"] is None


def scroll_with_tokens(prompt: int, completion: int) -> Decision:
    return Decision(
        Action(kind="scroll", value="down"), prompt_tokens=prompt, completion_tokens=completion
    )


def test_run_token_cap_ends_personas_with_reason(
    fakes: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    # 회차 당 상한 250. step 마다 100 토큰 → 3 step 뒤(300) 다음 호출 전에 끝난다.
    use_decider(monkeypatch, ScriptedDecider(*[scroll_with_tokens(80, 20) for _ in range(10)]))

    asyncio.run(run(fakes, RUN_ID, snapshot([persona(1)], max_steps=10, max_tokens=250)))

    assert fakes.personas.steps[1] == 3
    assert fakes.personas.tokens[1] == 300
    assert fakes.personas.statuses == {1: "max_steps"}
    ((_, persona_id, detail),) = fakes.audits.limits
    assert persona_id == 1
    assert detail == {"persona_id": 1, "step": 4, "reason": "max_tokens", "limit": 250, "used": 300}


def luna_step(prompt: int, completion: int, cached: int = 0, model: str = "gpt-6-luna") -> Decision:
    return Decision(
        Action(kind="scroll", value="down"),
        prompt_tokens=prompt,
        completion_tokens=completion,
        cached_tokens=cached,
        model=model,
    )


def test_step_cost_is_added_every_step_without_rounding_drift(
    fakes: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    # step 하나가 $0.00064 (입력 5,000 × $0.10 + 출력 280 × $0.50, 100만 토큰당). DB 칸은 소수
    # 4자리라 step 마다 반올림해 더하면 10 step 이 $0.0060 이 된다 — 실제 합계는 $0.0064 다.
    use_decider(monkeypatch, ScriptedDecider(*[luna_step(5_000, 280) for _ in range(10)]))

    asyncio.run(run(fakes, RUN_ID, snapshot([persona(1)], max_steps=10)))

    added = fakes.personas.cost_added[1]
    assert len(added) == 10  # step 마다 한 번씩 더한다
    # 더한 값은 소수 4자리이고, 그때까지의 합은 그 시점 실제 합계를 4자리로 반올림한 값이다.
    assert all(round(x, 4) == pytest.approx(x) for x in added)
    expected = [round(0.00064 * n, 4) for n in range(1, 11)]
    assert list(itertools.accumulate(added)) == pytest.approx(expected)
    assert fakes.personas.costs[1] == pytest.approx(0.0064)


def test_step_cost_bills_cached_tokens_at_cache_price(
    fakes: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    # 캐시된 40만 × $0.01 + 나머지 입력 60만 × $0.10 + 출력 100만 × $0.50 = $0.564
    use_decider(monkeypatch, ScriptedDecider(luna_step(1_000_000, 1_000_000, cached=400_000)))

    asyncio.run(run(fakes, RUN_ID, snapshot([persona(1)], max_steps=1)))

    assert fakes.personas.costs[1] == pytest.approx(0.564)


def test_unpriced_model_counts_tokens_but_leaves_cost_empty(
    fakes: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    use_decider(
        monkeypatch,
        ScriptedDecider(*[luna_step(80, 20, model="other/model") for _ in range(2)]),
    )

    asyncio.run(run(fakes, RUN_ID, snapshot([persona(1)], max_steps=2)))

    assert fakes.personas.tokens[1] == 200
    assert fakes.personas.cost_added[1] == [None, None]
    assert 1 not in fakes.personas.costs


def usage_llm(usages: dict[str, list[tuple[int, int, int]]]) -> LLMDecider:
    """Persona 마다 정해 둔 (입력, 출력, 캐시된 입력)을 차례로 쓰는 판단기.

    실제 LLMClient 처럼 호출마다 사용량 기록(llm-usage.jsonl)을 남긴다. 사용량은 Persona 별로
    정해 두므로 Persona 들의 step 이 어떻게 섞여도 같은 값이 나온다.
    """
    queues = {persona_id: iter(calls) for persona_id, calls in usages.items()}
    reply = '{"reasoning": "r", "action": {"kind": "scroll", "element_id": null, "value": "down"}}'

    class UsageLLM:
        model = "openai/gpt-6-luna"

        async def chat(self, messages, *, role, run_id=None, persona_id=None, **kwargs):
            inp, out, cached = next(queues[persona_id])
            response = SimpleNamespace(
                usage=SimpleNamespace(
                    prompt_tokens=inp,
                    completion_tokens=out,
                    completion_tokens_details=SimpleNamespace(reasoning_tokens=int(out * 0.9)),
                    prompt_tokens_details=SimpleNamespace(cached_tokens=cached),
                ),
                choices=[
                    SimpleNamespace(message=SimpleNamespace(content=reply), finish_reason="stop")
                ],
            )
            record_usage(
                response,
                role=role,
                model=self.model,
                latency_ms=1,
                run_id=run_id,
                persona_id=persona_id,
            )
            return response

    return LLMDecider(UsageLLM(), run_id=RUN_ID)


def test_cost_added_to_db_equals_cost_from_usage_log(
    fakes: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    # 한 응답에서 두 값이 나온다 — 사용량 기록(llm-usage.jsonl)으로 계산한 비용과 DB 에 더한 비용.
    # 둘이 같아야 한다.
    log = tmp_path / "llm-usage.jsonl"
    monkeypatch.setenv("LLM_USAGE_LOG", str(log))
    # (입력, 출력, 캐시된 입력) — 입력 47,080 · 출력 4,588 인 dev 회차 9 의 모양에 캐시를 섞었다.
    calls = [(1_900, 410, 0), (3_100, 520, 0), (3_800, 380, 1_000), (4_400, 450, 2_000),
             (4_900, 470, 0), (5_300, 500, 3_000), (5_600, 440, 0), (5_800, 460, 4_000),
             (5_900, 480, 0), (6_380, 478, 5_000)]  # fmt: skip
    use_decider(monkeypatch, usage_llm({"1": calls}))

    asyncio.run(run(fakes, RUN_ID, snapshot([persona(1)], max_steps=10)))

    rows = usage_report.load(log)
    from_log = sum(usage_report.cost_usd(row, usage_report.price_table()) for row in rows)
    assert len(rows) == 10
    assert fakes.personas.costs[1] == pytest.approx(round(from_log, 4))
    assert fakes.personas.run_cost == pytest.approx(round(from_log, 4))


def test_two_personas_cost_rows_are_rounded_each_and_run_is_their_sum(
    fakes: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    # PM 이 정한 기준: Persona 행 = 그 Persona 사용량 합계의 4자리 반올림,
    # 회차(runs) = Persona 행의 합. 그래서 Persona 가 여럿이면 회차 값이 사용량 기록 전체 합을
    # 반올림한 값과 0.0001 다를 수 있다.
    log = tmp_path / "llm-usage.jsonl"
    monkeypatch.setenv("LLM_USAGE_LOG", str(log))
    use_decider(
        monkeypatch,
        usage_llm(
            {
                "1": [(5_000, 240, 0)] * 2,  # step 하나 $0.00062 → 합계 $0.00124
                "2": [(5_200, 300, 0)] * 2,  # step 하나 $0.00067 → 합계 $0.00134
            }
        ),
    )

    asyncio.run(run(fakes, RUN_ID, snapshot([persona(1), persona(2)], max_steps=2)))

    table = usage_report.price_table()
    rows = usage_report.load(log)
    assert len(rows) == 4
    from_log = {
        pid: sum(usage_report.cost_usd(r, table) for r in rows if r["persona_id"] == str(pid))
        for pid in (1, 2)
    }
    for pid in (1, 2):
        assert fakes.personas.costs[pid] == pytest.approx(round(from_log[pid], 4))
    assert fakes.personas.costs[1] == pytest.approx(0.0012)
    assert fakes.personas.costs[2] == pytest.approx(0.0013)
    assert fakes.personas.run_cost == pytest.approx(sum(fakes.personas.costs.values()))
    # 로그 전체 합은 $0.00258 → 4자리 0.0026. 회차 값은 Persona 행의 합 0.0025 라서 0.0001 낮다.
    assert round(sum(from_log.values()), 4) == pytest.approx(0.0026)
    assert fakes.personas.run_cost == pytest.approx(0.0025)


def test_steps_use_the_price_table_made_at_accept_not_the_env(
    fakes: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    # 수락할 때 만든 단가표를 쓴다 — step 마다 env 를 다시 읽으면 아래 깨진 값에서 실패한다.
    orchestrator = RunOrchestrator()
    orchestrator._run_prices[RUN_ID] = {"example/model": (1.0, 2.0, 0.5)}
    monkeypatch.setenv("LLM_PRICES", "not json")
    use_decider(monkeypatch, ScriptedDecider(*[luna_step(1_000, 500, model="example/model")] * 2))

    asyncio.run(run(fakes, RUN_ID, snapshot([persona(1)], max_steps=2), orchestrator))

    assert fakes.personas.statuses == {1: "max_steps"}
    assert fakes.personas.costs[1] == pytest.approx(2 * (1_000 * 1.0 + 500 * 2.0) / 1_000_000)
    assert orchestrator._run_prices == {}  # 회차가 끝나면 비운다


def test_daily_budget_spent_stops_before_llm_call(fakes: SimpleNamespace) -> None:
    fakes.runs.daily_left = 0

    asyncio.run(run(fakes, RUN_ID, snapshot([persona(1)], max_steps=10)))

    assert fakes.personas.steps.get(1, 0) == 0
    assert fakes.personas.statuses == {1: "max_steps"}
    assert fakes.audits.limits[0][2]["reason"] == "daily_token_budget"


# 가드가 막는 요소 둘 — 1 은 허용 밖으로 가는 링크, 2 는 되돌릴 수 없는 버튼
GUARDED_ELEMENTS = {
    1: {"tag": "a", "url": "https://evil.example/"},
    2: {"tag": "button", "type": "button", "text": "회원 탈퇴"},
}


def screen_driver_class(final_call: int | None = None, final: str = "") -> type[Driver]:
    """화면이 행동마다 바뀌는 가짜 브라우저. observe() 가 'after-<행동 수>' 를 그림으로 낸다.

    final_call 번째 observe() — 마지막 step 이 끝난 뒤 마지막 화면을 얻는 호출 — 만 final 에 따라
    다르다.
    - "error": 예외
    - "hang": 끝나지 않음
    - "slow": 시간 상한을 넘겨 걸림
    - "no-image": 그림 없음
    """

    class ScreenDriver(Driver):
        def __init__(self, allowed_hosts: frozenset[str] = frozenset()) -> None:
            super().__init__(allowed_hosts)
            self.observes = 0
            self.acts = 0

        async def start(self, url: str) -> None:
            pass

        async def observe(self) -> Observation:
            self.observes += 1
            screenshot: bytes | None = f"after-{self.acts}".encode()
            if self.observes == final_call:
                if final == "error":
                    raise RuntimeError("Target page, context or browser has been closed")
                if final == "hang":
                    await asyncio.sleep(HANG_SECONDS)
                if final == "slow":
                    await asyncio.sleep(0.4)
                if final == "no-image":
                    screenshot = None
            return Observation(
                url="https://example.com/",
                title="t",
                dom="",
                element_map=GUARDED_ELEMENTS,
                screenshot=screenshot,
            )

        async def act(self, action: Action) -> ActionResult:
            self.acts += 1
            return ActionResult(ok=True)

        async def close(self) -> None:
            pass

    return ScreenDriver


class HangAfterDecider(Decider):
    """처음 count 번은 scroll 을 내고 그다음부터는 응답이 오지 않는다."""

    def __init__(self, count: int) -> None:
        self.count = count

    async def decide(self, persona, task, observation, history) -> Decision:
        if len(history) >= self.count:
            await asyncio.sleep(HANG_SECONDS)
        return Decision(Action(kind="scroll", value="down"))


def persona_folder(fakes: SimpleNamespace):
    return fakes.log_dir / str(RUN_ID) / "1"


def saved_files(fakes: SimpleNamespace) -> list[str]:
    """Persona 폴더의 파일 이름들 — step-<n>.png 와 steps.jsonl. 임시 파일이 남았는지도 보인다."""
    return sorted(p.name for p in persona_folder(fakes).iterdir())


def logged_steps(fakes: SimpleNamespace) -> list[int]:
    lines = (persona_folder(fakes) / "steps.jsonl").read_text(encoding="utf-8").splitlines()
    return [json.loads(line)["step"] for line in lines]


def screens(fakes: SimpleNamespace, count: int) -> list[bytes]:
    return [(persona_folder(fakes) / f"step-{n}.png").read_bytes() for n in range(1, count + 1)]


def test_max_steps_saves_screen_after_last_action(
    fakes: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    # step 3 개가 모두 scroll. step-1~3 은 각 step 을 시작할 때 화면, step-4 는 세 번째 행동 뒤
    # 화면이다. 로그 줄은 3 개 그대로다.
    monkeypatch.setattr(orchestrator_module, "DomDriver", screen_driver_class())

    asyncio.run(run(fakes, RUN_ID, snapshot([persona(1)], max_steps=3)))

    assert fakes.personas.statuses == {1: "max_steps"}
    assert fakes.runs.status == "done"
    assert saved_files(fakes) == [f"step-{n}.png" for n in (1, 2, 3, 4)] + ["steps.jsonl"]
    assert screens(fakes, 4) == [b"after-0", b"after-1", b"after-2", b"after-3"]
    assert logged_steps(fakes) == [1, 2, 3]
    assert fakes.personas.steps[1] == 3  # 마지막 화면은 step 으로 세지 않는다
    assert free_global_slots() == 3


@pytest.mark.parametrize("limit", ["max_tokens", "daily_budget"])
def test_token_limits_save_screen_after_last_action(
    fakes: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, limit: str
) -> None:
    # 3 step 뒤 다음 LLM 호출 전에 끝난다 — 회차당 상한 250(step 마다 100 토큰)이거나 하루 예산이
    # 바닥난다.
    monkeypatch.setattr(orchestrator_module, "DomDriver", screen_driver_class())
    use_decider(monkeypatch, ScriptedDecider(*[scroll_with_tokens(80, 20) for _ in range(10)]))
    policy = {"max_tokens": 250} if limit == "max_tokens" else {}
    if limit == "daily_budget":
        left = iter([None, None, None])  # 처음 세 번은 예산이 남아 있다
        fakes.runs.daily_tokens_left = lambda: next(left, 0)

    asyncio.run(run(fakes, RUN_ID, snapshot([persona(1)], max_steps=10, **policy)))

    assert fakes.personas.statuses == {1: "max_steps"}
    assert fakes.audits.limits[0][2]["step"] == 4
    assert saved_files(fakes) == [f"step-{n}.png" for n in (1, 2, 3, 4)] + ["steps.jsonl"]
    assert screens(fakes, 4)[-1] == b"after-3"
    assert logged_steps(fakes) == [1, 2, 3]


def test_max_seconds_saves_screen_after_last_logged_action(
    fakes: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    # step 2 개를 마치고 세 번째 step 의 LLM 응답을 기다리다 시간 상한에 걸린다.
    monkeypatch.setattr(orchestrator_module, "DomDriver", screen_driver_class())
    use_decider(monkeypatch, HangAfterDecider(2))

    asyncio.run(run(fakes, RUN_ID, snapshot([persona(1)], max_steps=10, max_seconds=0.5)))

    assert fakes.personas.statuses == {1: "timeout"}
    assert saved_files(fakes) == [f"step-{n}.png" for n in (1, 2, 3)] + ["steps.jsonl"]
    assert screens(fakes, 3) == [b"after-0", b"after-1", b"after-2"]
    assert logged_steps(fakes) == [1, 2]


def test_done_saves_no_extra_screen(
    fakes: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    # done 은 행동이 없어 마지막 step 의 화면이 곧 마지막 화면이다.
    monkeypatch.setattr(orchestrator_module, "DomDriver", screen_driver_class())
    use_decider(
        monkeypatch,
        ScriptedDecider(
            Decision(Action(kind="scroll", value="down")), Decision(Action(kind="done"))
        ),
    )

    asyncio.run(run(fakes, RUN_ID, snapshot([persona(1)], max_steps=5)))

    assert fakes.personas.statuses == {1: "done"}
    assert saved_files(fakes) == ["step-1.png", "step-2.png", "steps.jsonl"]


@pytest.mark.parametrize(
    "last",
    [
        parse_failure(),
        parse_failure("LLM_REQUEST_FAILED"),
        Decision(Action(kind="click", element_id=1)),  # 허용 밖으로 가는 링크
        Decision(Action(kind="click", element_id=2)),  # 되돌릴 수 없는 버튼
    ],
    ids=["parse-failed", "llm-failed", "domain-blocked", "destructive-blocked"],
)
def test_last_action_not_executed_saves_no_extra_screen(
    fakes: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, last: Decision
) -> None:
    # 첫 step 은 실행됐고 마지막 step 은 실행되지 않았다. 화면이 그대로라 step-2 가 마지막 화면이다.
    monkeypatch.setattr(orchestrator_module, "DomDriver", screen_driver_class())
    use_decider(monkeypatch, ScriptedDecider(Decision(Action(kind="scroll", value="down")), last))

    asyncio.run(run(fakes, RUN_ID, snapshot([persona(1)], max_steps=2)))

    assert fakes.personas.statuses == {1: "max_steps"}
    assert saved_files(fakes) == ["step-1.png", "step-2.png", "steps.jsonl"]


def test_failed_persona_saves_no_extra_screen(
    fakes: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    # 행동을 얻지 못한 step 이 3 번 이어져 실패로 끝난다.
    monkeypatch.setattr(orchestrator_module, "DomDriver", screen_driver_class())
    use_decider(
        monkeypatch,
        ScriptedDecider(
            Decision(Action(kind="scroll", value="down")),
            parse_failure(),
            parse_failure(),
            parse_failure(),
        ),
    )

    asyncio.run(run(fakes, RUN_ID, snapshot([persona(1)], max_steps=10)))

    assert fakes.personas.statuses == {1: "fail"}
    assert saved_files(fakes) == [f"step-{n}.png" for n in (1, 2, 3, 4)] + ["steps.jsonl"]


def test_cancelled_persona_saves_no_extra_screen(
    fakes: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    # 세 번째 step 의 LLM 응답을 기다리는 중 취소된다 — 끝난 이유가 한도가 아니다.
    monkeypatch.setattr(orchestrator_module, "DomDriver", screen_driver_class())
    use_decider(monkeypatch, HangAfterDecider(2))
    snap = snapshot([persona(1)], max_steps=10, max_seconds=HANG_SECONDS)

    async def cancel_midway() -> None:
        task = asyncio.create_task(run(fakes, RUN_ID, snap))
        await asyncio.sleep(POLL_SECONDS * 3)
        fakes.runs.cancel_requested = True
        await task

    asyncio.run(cancel_midway())

    assert fakes.personas.statuses == {1: "cancelled"}
    assert saved_files(fakes) == ["step-1.png", "step-2.png", "steps.jsonl"]


@pytest.mark.parametrize("failure", ["error", "hang", "no-image", "write-error"])
def test_failing_last_screen_does_not_change_result(
    fakes: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    # 마지막 화면을 얻거나 쓰지 못해도 Persona 결과 · 회차 상태 · 로그는 그대로고 파일만 없다.
    monkeypatch.setattr(orchestrator_module, "LAST_SCREENSHOT_TIMEOUT_SECONDS", 0.2)
    monkeypatch.setattr(orchestrator_module, "DomDriver", screen_driver_class(4, failure))
    if failure == "write-error":
        writer = orchestrator_module.step_log_writer
        write = writer.write_screenshot

        def write_unless_last(run_id: int, persona_id: int, step: int, png: bytes) -> str:
            if step == 4:
                raise OSError("No space left on device")
            return write(run_id, persona_id, step, png)

        monkeypatch.setattr(writer, "write_screenshot", write_unless_last)

    asyncio.run(run(fakes, RUN_ID, snapshot([persona(1)], max_steps=3)))

    assert fakes.personas.statuses == {1: "max_steps"}
    assert fakes.runs.status == "done"
    assert saved_files(fakes) == [f"step-{n}.png" for n in (1, 2, 3)] + ["steps.jsonl"]
    assert logged_steps(fakes) == [1, 2, 3]
    assert free_global_slots() == 3


def test_last_screen_is_outside_max_seconds(
    fakes: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    # step 은 시간 상한 안에 끝났고, 마지막 화면은 그 시간 상한을 넘겨서 얻는다.
    # 마지막 화면이 시간 상한에 끊기면 결과가 timeout 으로 바뀌고 그림도 남지 않는다.
    monkeypatch.setattr(orchestrator_module, "DomDriver", screen_driver_class(3, "slow"))

    asyncio.run(run(fakes, RUN_ID, snapshot([persona(1)], max_steps=2, max_seconds=0.3)))

    assert fakes.personas.statuses == {1: "max_steps"}
    assert saved_files(fakes) == [f"step-{n}.png" for n in (1, 2, 3)] + ["steps.jsonl"]


def test_cancel_stops_last_screen_quickly(
    fakes: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    # 마지막 화면을 얻는 중 취소 요청이 오면 상한(3초)을 기다리지 않고 멈춘다 — 취소 10초 약속.
    monkeypatch.setattr(orchestrator_module, "LAST_SCREENSHOT_TIMEOUT_SECONDS", 3)
    monkeypatch.setattr(orchestrator_module, "DomDriver", screen_driver_class(3, "hang"))
    snap = snapshot([persona(1)], max_steps=2)

    async def cancel_midway() -> float:
        task = asyncio.create_task(run(fakes, RUN_ID, snap))
        await asyncio.sleep(POLL_SECONDS * 2)
        fakes.runs.cancel_requested = True
        requested_at = time.monotonic()
        await task
        return time.monotonic() - requested_at

    elapsed = asyncio.run(cancel_midway())

    assert elapsed < POLL_SECONDS * 10
    assert fakes.personas.statuses == {1: "max_steps"}  # 이미 정해진 결과는 그대로
    # 취소 요청은 마지막 화면만 멈춘다. Persona 결과가 이미 정해져 있어 회차는 done 이다.
    assert fakes.runs.status == "done"
    assert saved_files(fakes) == ["step-1.png", "step-2.png", "steps.jsonl"]
    assert free_global_slots() == 3
