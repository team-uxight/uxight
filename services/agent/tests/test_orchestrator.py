"""Watcher 실행 통제 (GACA-110). 가짜 Driver · 가짜 저장소로 LLM · DB 없이 돈다.

동시 상한 · 시간 상한 · 취소 10초 · 정책 기본값 · 실패 정리 · heartbeat.
"""

import asyncio
import time
from types import SimpleNamespace

import pytest

from uxight_agent.driver.base import ActionResult, Driver, Observation
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

    def get_statuses(self, run_id: int) -> dict[int, str]:
        return dict(self.statuses)

    def increment_steps(self, run_id: int, persona_id: int) -> None:
        self.steps[persona_id] = self.steps.get(persona_id, 0) + 1

    def mark_finished(self, run_id: int, persona_id: int, status: str) -> None:
        if self.statuses[persona_id] == "running":
            self.statuses[persona_id] = status


class FakeAuditLogRepository:
    def __init__(self) -> None:
        self.rows: list[tuple[int, int, dict]] = []

    def add_blocked_action(self, run_id: int, persona_id: int, detail: dict) -> None:
        self.rows.append((run_id, persona_id, detail))


class Browsers:
    """가짜 브라우저 집계 — 띄운 수 · 지금 열린 수 · 동시에 열린 최대 수."""

    def __init__(self) -> None:
        self.started = 0
        self.open = 0
        self.peak = 0
        self.close_seconds = 0.0  # 브라우저를 닫는 데 걸리는 시간
        self.close_error: Exception | None = None  # 닫은 뒤 낼 예외 (드라이버 연결 끊김 등)


def fake_driver_class(browsers: Browsers) -> type[Driver]:
    class FakeDriver(Driver):
        def __init__(self, allowed_hosts: frozenset[str] = frozenset()) -> None:
            super().__init__(allowed_hosts)
            self._started = False

        async def start(self, url: str) -> None:
            self._started = True
            browsers.started += 1
            browsers.open += 1
            browsers.peak = max(browsers.peak, browsers.open)

        async def observe(self) -> Observation:
            return Observation(url="https://example.com", title="t", dom="")

        async def act(self, action: Action) -> ActionResult:
            return ActionResult(ok=True)

        async def close(self) -> None:
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


async def run(fakes: SimpleNamespace, run_id: int, snap: RunSnapshot) -> None:
    # try_accept_and_start 가 만든 running 행에서 시작한다.
    fakes.personas.statuses.update({p["persona_id"]: "running" for p in snap.personas})
    await asyncio.wait_for(RunOrchestrator().run_personas(run_id, snap), timeout=5)


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
