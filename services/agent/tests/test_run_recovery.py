"""재시작 정리 · 수락 직후 예외 (GACA-110 후속). 가짜 저장소로 DB 없이 돈다.

시작 정리: accepted · running 회차는 failed, 그 running 페르소나는 fail, queued 는 그대로.
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

    def __init__(self, statuses: dict[int, str]) -> None:
        self.statuses = dict(statuses)
        self.errors: dict[int, str] = {}

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
) -> tuple[FakeRunRepository, FakeRunPersonaRepository]:
    runs = FakeRunRepository(run_statuses)
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
