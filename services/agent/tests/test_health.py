from fastapi.testclient import TestClient

from uxight_agent.main import app
from uxight_agent.schemas import Action

client = TestClient(app)


def test_health() -> None:
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok", "service": "agent"}


def test_start_run_returns_202() -> None:
    res = client.post("/runs", json={"run_id": 1, "target_url": "https://example.com", "task": "t"})
    assert res.status_code == 202
    assert res.json()["run_id"] == 1


def test_action_schema_rejects_unknown_action() -> None:
    assert Action(action="click", element=3).element == 3
    try:
        Action(action="execute_js")  # type: ignore[arg-type]
    except ValueError:
        return
    raise AssertionError("unknown action must be rejected")
