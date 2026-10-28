"""재시작 정리 · 수락 직후 예외 (GACA-110 후속). 가짜 저장소로 DB 없이 돈다.

시작 정리: accepted · running 회차는 failed, 그 running 페르소나는 fail, queued 는 그대로.
취소 요청된 accepted · running 회차는 cancelled, 그 running 페르소나도 cancelled.
회차 하나에서 오류가 나도 나머지 회차는 정리한다.
수락 직후 예외: 회차를 accepted · running 으로 남기지 않고, 응답에 예외 문구를 싣지 않는다.
"""

import pytest
from fastapi.testclient import TestClient

from uxight_agent import main
from uxight_agent.repositories.run_repository import RunSnapshot
from uxight_agent.routers import runs as runs_router
from uxight_agent.watcher import run_orchestrator as orchestrator_module
from uxight_agent.watcher.run_orchestrator import RunOrchestrator

UNFINISHED = ("accepted", "running")
# DB 오류 문구에는 SQL · 주소가 섞인다 — 응답과 runs.error 에 실리면 안 된다.
DB_ERROR = "(pymysql.err.OperationalError) SELECT task_snapshot FROM runs @ 10.0.0.5:3306"

SNAPSHOT = RunSnapshot(
    target_url="https://example.com",
    allowed_domains=["example.com"],
    task={"task_id": 1, "goal": "g"},
    personas=[{"persona_id": 1, "name": "p", "profile": {}}],
    policy={"max_steps": 3},
)


class FakeRunRepository:
    """runs 여러 행을 메모리에 둔다. 상태 전이 조건은 실제 SQL 과 같다."""

    def __init__(self, statuses: dict[int, str], cancel_requested: set[int]) -> None:
        self.statuses = dict(statuses)
        self.errors: dict[int, str] = {}
        self.cancel_requested = set(cancel_requested)
        self.daily_left: int | None = None  # 하루 예산 남은 토큰 (None = 예산 없음)

    def daily_tokens_left(self) -> int | None:
        return self.daily_left

    def accept_if_queued(self, run_id: int) -> bool:
        if self.statuses.get(run_id) != "queued":
            return False
        self.statuses[run_id] = "accepted"
        return True

    def get_snapshot(self, run_id: int) -> RunSnapshot:
        return SNAPSHOT

    def mark_running(self, run_id: int) -> None:
        if self.statuses[run_id] == "accepted":
            self.statuses[run_id] = "running"

    def get_status(self, run_id: int) -> str | None:
        return self.statuses.get(run_id)

    def get_unfinished_run_ids(self) -> list[int]:
        return [run_id for run_id, status in self.statuses.items() if status in UNFINISHED]

    def fail_unfinished(self, run_id: int, error: str) -> None:
        if self.statuses[run_id] in UNFINISHED:
            self.statuses[run_id] = "failed"
            self.errors[run_id] = error

    def is_cancel_requested(self, run_id: int) -> bool:
        return run_id in self.cancel_requested

    def cancel_unfinished(self, run_id: int) -> None:
        if self.statuses[run_id] in UNFINISHED:
            self.statuses[run_id] = "cancelled"


class FakeRunPersonaRepository:
    """run_personas 행을 회차별로 메모리에 둔다. running 인 행만 종료 상태로 바뀐다."""

    def __init__(self, rows: dict[int, dict[int, str]]) -> None:
        self.rows = {run_id: dict(personas) for run_id, personas in rows.items()}

    def create_for_persona(self, run_id: int, log_paths: dict[int, str]) -> None:
        self.rows[run_id] = dict.fromkeys(log_paths, "running")

    def get_statuses(self, run_id: int) -> dict[int, str]:
        return dict(self.rows.get(run_id, {}))

    def mark_finished(self, run_id: int, persona_id: int, status: str) -> None:
        if self.rows[run_id][persona_id] == "running":
            self.rows[run_id][persona_id] = status


def install(
    monkeypatch: pytest.MonkeyPatch,
    run_statuses: dict[int, str],
    persona_rows: dict[int, dict[int, str]] | None = None,
    cancel_requested: set[int] | None = None,
) -> tuple[FakeRunRepository, FakeRunPersonaRepository]:
    runs = FakeRunRepository(run_statuses, cancel_requested or set())
    personas = FakeRunPersonaRepository(persona_rows or {})
    monkeypatch.setattr(orchestrator_module, "run_repository", runs)
    monkeypatch.setattr(orchestrator_module, "run_persona_repository", personas)
    monkeypatch.setattr(runs_router, "run_repository", runs)
    return runs, personas


def test_startup_cleanup_fails_accepted_and_running_runs(monkeypatch: pytest.MonkeyPatch) -> None:
    runs, personas = install(
        monkeypatch,
        {1: "running", 2: "accepted", 3: "queued", 4: "done"},
        {1: {10: "running", 11: "max_steps"}, 4: {12: "done"}},
    )

    RunOrchestrator().close_interrupted_runs()

    # queued 는 Spring 재전송이 맡는다 — 건드리지 않는다.
    assert runs.statuses == {1: "failed", 2: "failed", 3: "queued", 4: "done"}
    assert runs.errors == {1: "interrupted", 2: "interrupted"}
    assert personas.rows == {1: {10: "fail", 11: "max_steps"}, 4: {12: "done"}}


def test_startup_cleanup_cancels_runs_with_cancel_request(monkeypatch: pytest.MonkeyPatch) -> None:
    # 취소 요청 뒤 재시작으로 끊긴 회차는 실패가 아니라 취소다
    # (V1__init_schema.sql runs.status 주석).
    runs, personas = install(
        monkeypatch,
        {1: "running", 2: "accepted", 3: "running", 4: "queued", 5: "done"},
        {1: {10: "running", 11: "done"}, 3: {12: "running"}, 5: {13: "done"}},
        cancel_requested={1, 2, 4, 5},
    )

    RunOrchestrator().close_interrupted_runs()

    # 취소 요청이 없는 3 은 지금대로 failed. queued · done 은 취소 요청이 있어도 그대로.
    assert runs.statuses == {1: "cancelled", 2: "cancelled", 3: "failed", 4: "queued", 5: "done"}
    assert runs.errors == {3: "interrupted"}
    assert personas.rows == {1: {10: "cancelled", 11: "done"}, 3: {12: "fail"}, 5: {13: "done"}}


def test_startup_cleanup_continues_after_error_in_one_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # 회차 하나에서 DB 오류가 나도 나머지 회차는 정리한다. 오류 난 회차는 다음 기동 때 정리된다.
    runs, personas = install(
        monkeypatch,
        {1: "running", 2: "running", 3: "running"},
        {1: {10: "running"}, 2: {11: "running"}, 3: {12: "running"}},
    )
    is_cancel_requested = runs.is_cancel_requested

    def db_error_on_run_1(run_id: int) -> bool:
        if run_id == 1:
            raise RuntimeError(DB_ERROR)
        return is_cancel_requested(run_id)

    runs.is_cancel_requested = db_error_on_run_1

    RunOrchestrator().close_interrupted_runs()

    assert runs.statuses == {1: "running", 2: "failed", 3: "failed"}
    assert personas.rows == {1: {10: "running"}, 2: {11: "fail"}, 3: {12: "fail"}}


def test_app_startup_runs_cleanup_once(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []
    monkeypatch.setattr(main.run_orchestrator, "close_interrupted_runs", lambda: calls.append(1))

    with TestClient(main.app) as client:
        assert client.get("/health").status_code == 200

    assert calls == [1]


def test_app_starts_even_if_cleanup_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    def db_down() -> None:
        raise RuntimeError(DB_ERROR)

    monkeypatch.setattr(main.run_orchestrator, "close_interrupted_runs", db_down)

    with TestClient(main.app) as client:
        assert client.get("/health").status_code == 200


@pytest.mark.parametrize("failing_step", ["get_snapshot", "mark_running", "create_for_persona"])
def test_error_right_after_accept_closes_run_as_failed(
    monkeypatch: pytest.MonkeyPatch, failing_step: str
) -> None:
    runs, personas = install(monkeypatch, {7: "queued"})
    started: list = []

    async def fake_run_personas(run_id: int, snapshot: RunSnapshot) -> None:
        started.append(run_id)

    def db_error(*args) -> None:
        raise RuntimeError(DB_ERROR)

    monkeypatch.setattr(runs_router.run_orchestrator, "run_personas", fake_run_personas)
    monkeypatch.setattr(
        personas if failing_step == "create_for_persona" else runs, failing_step, db_error
    )

    res = TestClient(main.app).post("/runs", json={"run_id": 7})

    # 수락한 회차라 200 + 현재 상태. 예외 문구(SQL · 주소)는 응답에도 runs.error 에도 없다.
    assert res.status_code == 200
    assert res.json() == {"run_id": 7, "status": "failed"}
    assert runs.statuses[7] == "failed"
    assert runs.errors[7] == "실행 오류로 중단: RuntimeError"
    assert "running" not in personas.get_statuses(7).values()
    assert started == []


def test_missing_llm_settings_close_run_before_browsers(monkeypatch: pytest.MonkeyPatch) -> None:
    # LLM 설정이 비면 브라우저를 띄우기 전에 짧은 사유로 마감한다.
    runs, personas = install(monkeypatch, {7: "queued"})
    started: list = []

    async def fake_run_personas(run_id: int, snapshot: RunSnapshot) -> None:
        started.append(run_id)

    monkeypatch.setattr(runs_router.run_orchestrator, "run_personas", fake_run_personas)
    monkeypatch.setattr(orchestrator_module, "_llm", None)
    for name in ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL"):
        monkeypatch.delenv(name, raising=False)

    res = TestClient(main.app).post("/runs", json={"run_id": 7})

    assert res.json() == {"run_id": 7, "status": "failed"}
    assert runs.errors[7] == "LLM 설정 없음"
    assert "running" not in personas.get_statuses(7).values()
    assert started == []


def test_spent_daily_budget_does_not_start_new_run(monkeypatch: pytest.MonkeyPatch) -> None:
    runs, personas = install(monkeypatch, {7: "queued"})
    runs.daily_left = -5
    started: list = []

    async def fake_run_personas(run_id: int, snapshot: RunSnapshot) -> None:
        started.append(run_id)

    monkeypatch.setattr(runs_router.run_orchestrator, "run_personas", fake_run_personas)

    res = TestClient(main.app).post("/runs", json={"run_id": 7})

    assert res.json() == {"run_id": 7, "status": "failed"}
    assert runs.errors[7] == "하루 토큰 예산 초과"
    assert started == []
