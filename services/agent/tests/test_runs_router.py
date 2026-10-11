"""POST /runs 계약 (내부 API 1). DB 는 대역으로 바꾼다.

수락 202, 이미 받은 회차 200 + status, 없는 회차 404.
"""

import pytest
from fastapi.testclient import TestClient

from uxight_agent.main import app
from uxight_agent.repositories.run_repository import RunSnapshot
from uxight_agent.routers import runs

client = TestClient(app)

SNAPSHOT = RunSnapshot(
    target_url="https://example.com",
    allowed_domains=["example.com"],
    task={"task_id": 1, "goal": "g"},
    personas=[{"persona_id": 1, "name": "p", "profile": {}}],
    policy={"max_steps": 3},
)


@pytest.fixture
def started(monkeypatch: pytest.MonkeyPatch) -> list:
    calls: list = []

    async def fake_run_personas(run_id: int, snapshot: RunSnapshot) -> None:
        calls.append((run_id, snapshot))

    monkeypatch.setattr(runs.run_orchestrator, "run_personas", fake_run_personas)
    return calls


def test_accepts_queued_run(monkeypatch: pytest.MonkeyPatch, started: list) -> None:
    monkeypatch.setattr(runs.run_orchestrator, "try_accept_and_start", lambda run_id: SNAPSHOT)

    res = client.post("/runs", json={"run_id": 7})

    assert res.status_code == 202
    assert res.json() == {"run_id": 7}
    assert started == [(7, SNAPSHOT)]


def test_already_accepted_run_is_idempotent(monkeypatch: pytest.MonkeyPatch, started: list) -> None:
    monkeypatch.setattr(runs.run_orchestrator, "try_accept_and_start", lambda run_id: None)
    monkeypatch.setattr(runs.run_repository, "get_status", lambda run_id: "running")

    res = client.post("/runs", json={"run_id": 7})

    assert res.status_code == 200
    assert res.json() == {"run_id": 7, "status": "running"}
    assert started == []


def test_unknown_run_is_404(monkeypatch: pytest.MonkeyPatch, started: list) -> None:
    monkeypatch.setattr(runs.run_orchestrator, "try_accept_and_start", lambda run_id: None)
    monkeypatch.setattr(runs.run_repository, "get_status", lambda run_id: None)

    res = client.post("/runs", json={"run_id": 404})

    assert res.status_code == 404
    assert started == []
